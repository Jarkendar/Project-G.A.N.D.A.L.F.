#!/usr/bin/env python3
# Comparative eval: grep (status quo without Samwise) vs semantic vs hybrid,
# plus semantic threshold calibration — the core deliverable of Samwise's
# Part 3 (see IMPLEMENTATION.md Step 3 and the plan this was built from).
#
# Loads eval/golden.jsonl (hand-labeled query -> expected file), runs all
# three ../search.py strategies IN-PROCESS (single model load for the whole
# run, not one subprocess per query x strategy), and reports:
#   - per-strategy hit@1 / hit@3 / hit@5 / MRR / precision@5 / recall@5
#   - a per-query "who picked what" table (grep vs semantic vs hybrid top-1)
#   - the score distribution of correct vs incorrect semantic hits, and the
#     F1-optimal cosine threshold over that distribution
#   - a recommended default strategy + --min-score for search.py / samwise.md

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import search  # noqa: E402

TOP_K = 10
GOLDEN_PATH = Path(__file__).resolve().parent / "golden.jsonl"


def load_golden() -> list[dict]:
    rows = []
    with GOLDEN_PATH.open(encoding="utf-8") as f:
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


def evaluate_strategy(strategy: str, golden: list[dict], brain_dir: Path,
                       idx: "search.SamwiseIndex") -> tuple[dict, list[dict]]:
    per_query = []
    for item in golden:
        results = search.search(brain_dir, item["query"], strategy, TOP_K, -1.0, idx=idx)
        rank = rank_of_first_relevant(results, item["expected_paths"])
        per_query.append({
            "query": item["query"],
            "expected": item["expected_paths"],
            "rank": rank,
            "top1": results[0]["path"] if results else None,
        })
    n = len(golden)
    hit_at = lambda k: sum(1 for pq in per_query if pq["rank"] is not None and pq["rank"] <= k) / n
    mrr = sum(1.0 / pq["rank"] if pq["rank"] else 0.0 for pq in per_query) / n
    # This golden set has exactly one relevant file per query, so recall@5 is
    # just hit@5, and precision@5 = hit@5 / 5 (one relevant item retrieved
    # out of 5 slots, if found at all within the top 5).
    hit5 = hit_at(5)
    metrics = {
        "hit@1": hit_at(1), "hit@3": hit_at(3), "hit@5": hit5,
        "mrr": mrr, "precision@5": hit5 / 5, "recall@5": hit5,
    }
    return metrics, per_query


def calibrate_threshold(golden: list[dict], idx: "search.SamwiseIndex") -> tuple[dict, list[tuple]]:
    """Sweep cosine thresholds over semantic top-20 hits, each labeled relevant
    (1) or irrelevant (0) by whether its path is in that query's
    expected_paths. Returns the threshold maximizing F1."""
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


def main():
    project_dir = search.default_project_dir()
    brain_dir = search.resolve_brain_path(project_dir)
    golden = load_golden()
    idx = search.load_index(brain_dir)

    print(f"SAMWISE eval — {len(golden)} golden queries, top-{TOP_K}\n")

    summary = {}
    details = {}
    for strategy in ("grep", "semantic", "hybrid"):
        metrics, per_query = evaluate_strategy(strategy, golden, brain_dir, idx)
        summary[strategy] = metrics
        details[strategy] = per_query

    print("## Strategy comparison\n")
    header = f"{'strategy':<10} {'hit@1':>6} {'hit@3':>6} {'hit@5':>6} {'MRR':>6} {'P@5':>6} {'R@5':>6}"
    print(header)
    print("-" * len(header))
    for strategy, m in summary.items():
        print(f"{strategy:<10} {m['hit@1']:>6.2f} {m['hit@3']:>6.2f} {m['hit@5']:>6.2f} "
              f"{m['mrr']:>6.2f} {m['precision@5']:>6.2f} {m['recall@5']:>6.2f}")

    print("\n## Per-query top-1 pick (grep vs semantic vs hybrid)\n")
    for i, item in enumerate(golden):
        expected = item["expected_paths"][0]
        grep_top1 = details["grep"][i]["top1"]
        sem_top1 = details["semantic"][i]["top1"]
        hyb_top1 = details["hybrid"][i]["top1"]
        print(f"Q: {item['query']}")
        print(f"   expected:  {expected}")
        print(f"   grep:      {grep_top1}{'  OK' if grep_top1 == expected else ''}")
        print(f"   semantic:  {sem_top1}{'  OK' if sem_top1 == expected else ''}")
        print(f"   hybrid:    {hyb_top1}{'  OK' if hyb_top1 == expected else ''}")
        print()

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

    print("\n## Recommendation")
    best_strategy = max(summary.items(), key=lambda kv: (kv[1]["mrr"], kv[1]["hit@1"]))[0]
    print(f"Default strategy: {best_strategy} (highest MRR / hit@1 on this golden set)")
    print(f"Default --min-score: {best['threshold']}")


if __name__ == "__main__":
    main()
