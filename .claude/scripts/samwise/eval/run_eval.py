#!/usr/bin/env python3
# Comparative eval: grep (status quo without Samwise) vs semantic vs hybrid,
# plus semantic threshold calibration — the core deliverable of Samwise's
# Part 3 (see IMPLEMENTATION.md Step 3 and the plan this was built from).
#
# Loads the private golden set from brain/ (hand-labeled query -> expected
# file(s)) — a mix of single-answer point-lookup queries and genuinely
# multi-file topical queries — runs all three ../search.py strategies
# IN-PROCESS (single model load for the whole run, not one subprocess per
# query x strategy), and reports:
#   - per-strategy hit@1/3/5, MRR, precision@5, recall@5, full-recall@5
#     (recall/precision are set-based: they credit partial matches on
#     multi-file queries rather than assuming one relevant document)
#   - a per-query table: how many of the expected files each strategy found
#     in its top-5, plus the top-1 pick
#   - the score distribution of correct vs incorrect semantic hits, and the
#     F1-optimal cosine threshold over that distribution
#   - a recommended default strategy + --min-score for search.py / samwise.md
#
# Eval v2 additions (Index v2, phase A — IMPLEMENTATION.md Step 9):
#   - section_hit@5: an expected file's chunk under an expected heading in the
#     top 5 (queries with `expected_sections` only; grep has no headings)
#   - answer@5: the query's `answer_snippet` appears in the text of the top-5
#     chunks — whether the answer reaches the reader, not just its file
#   - ctx_chars@5: characters of chunk text those top 5 hand over
#   - hit@5 / MRR per query `type`, query latency p50/p95, peak RSS
#   - --index to evaluate an experimental index built with `index.py --db`;
#     --json-out to keep a run for comparison across variants

import argparse
import json
import os
import re
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import search  # noqa: E402

TOP_K = 10
PRECISION_RECALL_K = 5
# The golden set lives in brain/, not here: every entry pairs a real question
# with the real file that answers it, which together describe brain/'s
# contents — that does not belong in a public repo. This directory keeps only
# `golden.example.jsonl`, a synthetic illustration of the format.
GOLDEN_RELATIVE_TO_BRAIN = Path("_meta/eval/samwise-golden.jsonl")
EXAMPLE_PATH = Path(__file__).resolve().parent / "golden.example.jsonl"


def resolve_golden_path(brain_dir: Path) -> Path:
    """SAMWISE_GOLDEN (absolute or relative to brain/) wins; otherwise the
    conventional location inside brain/."""
    override = os.environ.get("SAMWISE_GOLDEN")
    if override:
        path = Path(override).expanduser()
        return path if path.is_absolute() else brain_dir / path
    return brain_dir / GOLDEN_RELATIVE_TO_BRAIN


def load_golden(golden_path: Path) -> list[dict]:
    if not golden_path.exists():
        sys.exit(
            f"SAMWISE eval: no golden set at {golden_path}\n"
            f"  The golden set is private and lives in brain/ — see\n"
            f"  {EXAMPLE_PATH.name} for the format, or set SAMWISE_GOLDEN to\n"
            f"  point somewhere else."
        )
    rows = []
    with golden_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def rank_of_first_relevant(results: list[dict], expected_paths: list[str]) -> int | None:
    """1-based rank of the first hit whose path is in expected_paths, else None."""
    for i, r in enumerate(results):
        if r["path"] in expected_paths:
            return i + 1
    return None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _chunk_text(idx: "search.SamwiseIndex", result: dict) -> str:
    i = result.get("chunk")
    return idx.texts[i] if i is not None else ""


def evaluate_strategy(strategy: str, golden: list[dict], brain_dir: Path,
                       idx: "search.SamwiseIndex") -> tuple[dict, list[dict]]:
    per_query = []
    for item in golden:
        start = time.perf_counter()
        results = search.search(brain_dir, item["query"], strategy, TOP_K, -1.0, idx=idx)
        latency_ms = (time.perf_counter() - start) * 1000
        expected = set(item["expected_paths"])
        rank = rank_of_first_relevant(results, item["expected_paths"])

        top_k_paths = [r["path"] for r in results[:PRECISION_RECALL_K]]
        # dedupe while preserving order (semantic results are per-chunk, so
        # the same file can appear more than once in a raw top-k slice)
        seen: set[str] = set()
        top_k_unique = [p for p in top_k_paths if not (p in seen or seen.add(p))]
        found = set(top_k_unique) & expected

        top_chunks = results[:PRECISION_RECALL_K]
        section_hit = None
        sections = item.get("expected_sections")
        if sections and strategy != "grep":
            wanted = [sec.lower() for sec in sections]
            section_hit = any(
                r["path"] in expected and any(w in (r.get("heading") or "").lower() for w in wanted)
                for r in top_chunks
            )
        answer_hit = None
        ctx_chars = None
        if strategy != "grep":
            context = "\n".join(_chunk_text(idx, r) for r in top_chunks)
            ctx_chars = len(context)
            if item.get("answer_snippet"):
                answer_hit = _norm(item["answer_snippet"]) in _norm(context)

        per_query.append({
            "query": item["query"],
            "type": item.get("type", "point"),
            "expected": item["expected_paths"],
            "rank": rank,
            "top1": results[0]["path"] if results else None,
            "found_at_5": found,
            "n_expected": len(expected),
            "section_hit": section_hit,
            "answer_hit": answer_hit,
            "ctx_chars": ctx_chars,
            "latency_ms": latency_ms,
        })

    n = len(golden)
    hit_at = lambda k: sum(
        1 for pq in per_query if pq["rank"] is not None and pq["rank"] <= k
    ) / n
    mrr = sum(1.0 / pq["rank"] if pq["rank"] else 0.0 for pq in per_query) / n

    # Set-based precision/recall @5, generalized for multi-file queries:
    # recall = |retrieved ∩ expected| / |expected|; precision = |retrieved ∩
    # expected| / 5. full_recall@5 = fraction of queries where ALL expected
    # files were retrieved within the top 5 (the strict multi-file bar).
    recall_vals = [len(pq["found_at_5"]) / pq["n_expected"] for pq in per_query]
    precision_vals = [len(pq["found_at_5"]) / PRECISION_RECALL_K for pq in per_query]
    full_recall = sum(
        1 for pq in per_query if len(pq["found_at_5"]) == pq["n_expected"]
    ) / n

    def rate(key):
        scored = [pq[key] for pq in per_query if pq[key] is not None]
        return (sum(scored) / len(scored), len(scored)) if scored else (None, 0)

    latencies = sorted(pq["latency_ms"] for pq in per_query)
    ctx = [pq["ctx_chars"] for pq in per_query if pq["ctx_chars"] is not None]
    metrics = {
        "hit@1": hit_at(1), "hit@3": hit_at(3), "hit@5": hit_at(5),
        "mrr": mrr,
        "precision@5": sum(precision_vals) / n,
        "recall@5": sum(recall_vals) / n,
        "full_recall@5": full_recall,
        "section_hit@5": rate("section_hit"),
        "answer@5": rate("answer_hit"),
        "ctx_chars@5": statistics.mean(ctx) if ctx else None,
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))],
        "by_type": {},
    }
    for qtype in sorted({pq["type"] for pq in per_query}):
        group = [pq for pq in per_query if pq["type"] == qtype]
        metrics["by_type"][qtype] = {
            "n": len(group),
            "hit@5": sum(1 for pq in group if pq["rank"] and pq["rank"] <= 5) / len(group),
            "mrr": sum(1.0 / pq["rank"] if pq["rank"] else 0.0 for pq in group) / len(group),
        }
    return metrics, per_query


def calibrate_threshold(golden: list[dict], idx: "search.SamwiseIndex") -> tuple[dict, list[tuple]]:
    """Sweep cosine thresholds over semantic top-20 hits, each labeled relevant
    (1) or irrelevant (0) by whether its path is in that query's
    expected_paths (single- or multi-file queries both contribute pairs).
    Returns the threshold maximizing F1."""
    pairs: list[tuple[float, int]] = []
    for item in golden:
        results = search.semantic_search(idx, item["query"], top_k=20, min_score=-1.0)
        for r in results:
            label = 1 if r["path"] in item["expected_paths"] else 0
            pairs.append((r["score"], label))

    total_positive = sum(label for _, label in pairs)
    thresholds = sorted({score for score, _ in pairs})
    best = {"threshold": 0.0, "f1": -1.0, "precision": 0.0, "recall": 0.0}
    for t in thresholds:
        tp = sum(1 for score, label in pairs if score >= t and label == 1)
        fp = sum(1 for score, label in pairs if score >= t and label == 0)
        fn = total_positive - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        if f1 > best["f1"]:
            best = {"threshold": round(t, 4), "f1": round(f1, 4),
                     "precision": round(precision, 4), "recall": round(recall, 4)}
    return best, pairs


def _fmt(value, width=6):
    if value is None:
        return f"{'—':>{width}}"
    if isinstance(value, tuple):  # (rate, n_scored)
        return _fmt(value[0], width)
    return f"{value:>{width}.2f}"


def main():
    parser = argparse.ArgumentParser(description="S.A.M.W.I.S.E. retrieval eval")
    parser.add_argument("--index", type=str, default=None,
                        help="evaluate this index instead of brain/index/bilbo.db")
    parser.add_argument("--strategies", type=str, default="grep,semantic,hybrid",
                        help="comma-separated subset of grep,semantic,hybrid")
    parser.add_argument("--json-out", type=str, default=None,
                        help="write summary + per-query results here (keep it inside "
                             "brain/ — queries are private)")
    parser.add_argument("--quiet", action="store_true", help="skip the per-query listing")
    args = parser.parse_args()
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    project_dir = search.default_project_dir()
    brain_dir = search.resolve_brain_path(project_dir)
    golden_path = resolve_golden_path(brain_dir)
    golden = load_golden(golden_path)
    idx = search.load_index(brain_dir, Path(args.index).resolve() if args.index else None)

    load_start = time.perf_counter()
    search.load_model(idx.spec)
    model_load_s = time.perf_counter() - load_start

    n_multi = sum(1 for item in golden if len(item["expected_paths"]) > 1)
    print(f"SAMWISE eval — {len(golden)} golden queries "
          f"({len(golden) - n_multi} single-file, {n_multi} multi-file), top-{TOP_K}")
    print(f"index: {idx.db_path} — {len(idx.texts)} chunks, "
          f"{idx.spec.name}@{idx.spec.revision[:7]}, model load {model_load_s:.1f}s\n")

    summary = {}
    details = {}
    for strategy in strategies:
        metrics, per_query = evaluate_strategy(strategy, golden, brain_dir, idx)
        summary[strategy] = metrics
        details[strategy] = per_query

    print("## Strategy comparison\n")
    header = (f"{'strategy':<10} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6} "
              f"{'P@5':>6} {'R@5':>6} {'fullR@5':>8} {'sec@5':>6} {'ans@5':>6} "
              f"{'ctx@5':>7} {'p50ms':>6} {'p95ms':>6}")
    print(header)
    print("-" * len(header))
    for strategy, m in summary.items():
        ctx = f"{m['ctx_chars@5']:>7.0f}" if m["ctx_chars@5"] is not None else f"{'—':>7}"
        print(f"{strategy:<10} {m['hit@1']:>6.2f} {m['hit@3']:>6.2f} {m['hit@5']:>6.2f} "
              f"{m['mrr']:>6.2f} {m['precision@5']:>6.2f} {m['recall@5']:>6.2f} "
              f"{m['full_recall@5']:>8.2f} {_fmt(m['section_hit@5'])} {_fmt(m['answer@5'])} "
              f"{ctx} {m['latency_p50_ms']:>6.0f} {m['latency_p95_ms']:>6.0f}")
    scored = {k: v for k, v in summary[strategies[-1]].items() if k in ("section_hit@5", "answer@5")}
    print("\n(sec@5 over " + str(scored.get("section_hit@5", (None, 0))[1]) +
          " queries with expected_sections; ans@5 over " +
          str(scored.get("answer@5", (None, 0))[1]) + " with answer_snippet; ctx@5 in characters)")

    print("\n## By query type (hit@5 / MRR)\n")
    types = sorted({t for m in summary.values() for t in m["by_type"]})
    print(f"{'type':<8} {'n':>3} " + " ".join(f"{s:>15}" for s in strategies))
    for t in types:
        n = next(m["by_type"][t]["n"] for m in summary.values() if t in m["by_type"])
        cells = []
        for strategy in strategies:
            bt = summary[strategy]["by_type"].get(t)
            cells.append(f"{bt['hit@5']:>7.2f} / {bt['mrr']:.2f}" if bt else f"{'—':>15}")
        print(f"{t:<8} {n:>3} " + " ".join(f"{c:>15}" for c in cells))

    if not args.quiet:
        print("\n## Per-query top-1 pick + found/expected@5\n")
        for i, item in enumerate(golden):
            expected = item["expected_paths"]
            n_exp = len(expected)
            marker = " [multi]" if n_exp > 1 else ""
            print(f"Q: {item['query']}{marker}")
            print(f"   expected:  {expected}")
            for strategy in strategies:
                pq = details[strategy][i]
                top1_ok = " OK" if pq["top1"] == expected[0] else ""
                extra = ""
                if pq["answer_hit"] is not None:
                    extra = "  answer " + ("yes" if pq["answer_hit"] else "no")
                print(f"   {strategy:<10} top1={pq['top1']}{top1_ok}  "
                      f"found {len(pq['found_at_5'])}/{n_exp} in top-5{extra}")
            print()

    best = None
    if "semantic" in strategies:
        print("## Semantic threshold calibration (F1-optimal over golden set)\n")
        best, pairs = calibrate_threshold(golden, idx)
        correct = sorted((s for s, l in pairs if l == 1), reverse=True)
        incorrect = sorted((s for s, l in pairs if l == 0), reverse=True)
        if correct:
            print(f"Correct-hit scores:   min={min(correct):.4f} max={max(correct):.4f} (n={len(correct)})")
        else:
            print("Correct-hit scores: none found in top-20 for any query")
        if incorrect:
            print(f"Incorrect-hit scores: min={min(incorrect):.4f} max={max(incorrect):.4f} (n={len(incorrect)})")
        print(f"\nBest threshold: {best['threshold']} "
              f"(F1={best['f1']}, precision={best['precision']}, recall={best['recall']})")

    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"\nPeak RSS: {peak_rss_mb:.0f} MB")

    print("\n## Recommendation")
    best_strategy = max(summary.items(), key=lambda kv: (kv[1]["mrr"], kv[1]["hit@1"]))[0]
    print(f"Default strategy: {best_strategy} (highest MRR / hit@1 on this golden set)")
    if best:
        print(f"Default --min-score: {best['threshold']}")

    if args.json_out:
        out = {
            "index": str(idx.db_path),
            "model": f"{idx.spec.name}@{idx.spec.revision}",
            "chunks": len(idx.texts),
            "golden": str(golden_path),
            "n_queries": len(golden),
            "model_load_s": model_load_s,
            "peak_rss_mb": peak_rss_mb,
            "threshold": best,
            "summary": summary,
            "per_query": {
                strategy: [{**pq, "found_at_5": sorted(pq["found_at_5"])} for pq in rows]
                for strategy, rows in details.items()
            },
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
        print(f"\nWrote {args.json_out}")


if __name__ == "__main__":
    main()
