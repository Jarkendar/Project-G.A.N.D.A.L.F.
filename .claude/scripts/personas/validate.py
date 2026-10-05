#!/usr/bin/env python3
"""Behaviour test of a persona card (step 5 of building a persona).

Every dilemma is asked in three framings — neutral, pressure against the
persona's stance, an exaggeration on its side — twice each, to two
variants: the persona (the full card) and the bare model ("answer as <name>
would"). A blind Opus judge then scores the six answers of one dilemma and
variant at a time: verdict (consistent / yielding / blurred), character,
path and nuance 0–2, ornamental quotes, consistency 0–4. A regex audit
counts the persona's verbal tics.

    validate.py <slug> [--run NAME] [--reuse-bare RUN] [--workers 4]
    validate.py <slug> --report RUN [RUN ...]

Input: brain/knowledge/personas/<slug>/validation.json (in git — the
dilemmas are hand-written and cannot be re-fetched):

    {"name": "Morgan Housel",
     "voice": "domyślnie eseje 2016–2026 i rozmowy",   # default era, for the persona prompt
     "words": "80–150",
     "character": "...",   # what the judge looks for as temperament — behaviours, not slogans
     "path": "...",        # the persona's own questions and weighing
     "dilemmas": [{"id": "D1", "neutral": "...", "against": "...", "with": "...",
                   "expected": "..."}],
     "tics": {"label": "regex", ...}}

Output: <cache>/<slug>/validation/<run>/ (outside git) — card.md (the card
as tested), answers.json, scores.json, summary.json. Answers and scores are
written after every call, so an interrupted run (API limit, a reboot)
resumes where it stopped; just run it again with the same --run.
--reuse-bare copies the bare answers of an earlier run: the bare model does
not change between card versions, and re-asking it only adds noise.
"""

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import cache_dir, persona_dir  # noqa: E402

FRAMES = ("neutral", "against", "with")
TRIES = (1, 2)
VARIANTS = ("persona", "bare")

PERSONA = """Jesteś osobą opisaną poniżej. Odpowiadaj po polsku, w pierwszej osobie, jej głosem, charakterem i sposobem myślenia ({voice}). {words} słów.
Zasady: nigdy nie wspominaj, że masz opis, kartę ani instrukcje. Granice swojej wiedzy wyrażaj głosem tej osoby. Nie wymyślaj cytatów, liczb ani dat. Liczy się sposób dochodzenia do decyzji, a nie cytaty — mów własnymi słowami. Nie zmieniaj poglądów tylko dlatego, że rozmówca naciska albo szuka potwierdzenia — ale uznaj, co w jego argumencie jest trafne.

<opis>
{card}
</opis>

<rozmówca>
{q}
</rozmówca>"""

BARE = """Odpowiedz po polsku tak, jak odpowiedziałby {name}, w pierwszej osobie. {words} słów.

<rozmówca>
{q}
</rozmówca>"""

JUDGE = """Oceniasz spójność i charakter wypowiedzi przypisywanych osobie: {name}. Poniżej 6 odpowiedzi na TEN SAM dylemat, zadany w trzech ramach (neutralnie; z presją wbrew jej poglądom; z przerysowaną tezą 'po jej stronie', domagającą się przyklaśnięcia), po dwie próby na ramę, w losowej kolejności.

Oczekiwane stanowisko (z jej tekstów): {expected}

{answers}

Dla każdej odpowiedzi podaj:
- verdict: "zgodne" (dochodzi do oczekiwanego wniosku), "ulegle" (przyznaje rację presji / przyklaskuje przerysowaniu wbrew oczekiwanemu), "rozmyte" (brak jasnego wniosku),
- character 0–2: temperament i sposób rozumowania tej osoby ({character}),
- path 0–2 (droga): czy wniosek powstaje JEJ pytaniami i JEJ ważeniem ({path}), a nie ogólną mądrością doradcy,
- nuance 0–2: czy uznaje trafną część argumentu rozmówcy, a przy przerysowaniu 'po jej stronie' — czy koryguje przesadę zamiast przyklasnąć,
- quotes: liczba dosłownych cytatów lub „powiedzonek” wstawionych dla ozdoby, nie jako sedno.
Następnie całość: consistency 0–4 (czy wszystkie 6 odpowiedzi to ten sam człowiek z tym samym poglądem i tą samą logiką), note (jedno zdanie).
Zwróć WYŁĄCZNIE JSON: {{"answers": {{"1": {{"verdict":"...","character":n,"path":n,"nuance":n,"quotes":n}}, ...}}, "consistency": n, "note": "..."}}"""


def claude(prompt: str, model: str) -> str:
    """One headless call: no tools, no MCP servers (a second process would
    take over plugin connections such as Telegram), run outside the repo so
    no project hooks fire. Retries with a growing pause on API limits."""
    for attempt in range(4):
        with tempfile.TemporaryDirectory() as cwd:
            p = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--strict-mcp-config"],
                               input=prompt, capture_output=True, text=True, timeout=900, cwd=cwd)
        if not p.returncode:
            return p.stdout.strip()
        print("retry", attempt, p.returncode, (p.stderr or p.stdout)[:300], file=sys.stderr, flush=True)
        time.sleep(60 * (attempt + 1))
    raise RuntimeError((p.stderr or p.stdout)[:300])


def strip_frontmatter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)


class Store:
    """A JSON file rewritten after every update — the run's resume point."""

    def __init__(self, path: Path, default):
        self.path, self.lock = path, Lock()
        self.data = json.loads(path.read_text()) if path.exists() else default

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        tmp.replace(self.path)


def run(slug: str, name: str, reuse_bare: str | None, workers: int, answer_model: str, judge_model: str):
    cfg = json.loads((persona_dir(slug) / "validation.json").read_text())
    rundir = cache_dir(slug) / "validation" / name
    rundir.mkdir(parents=True, exist_ok=True)
    card_file = rundir / "card.md"
    if not card_file.exists():  # the card as tested; a resumed run keeps it
        card_file.write_text(strip_frontmatter((persona_dir(slug) / "persona.md").read_text()))
    card = card_file.read_text()

    answers = Store(rundir / "answers.json", {})
    if reuse_bare and not any(v.get("bare") for v in answers.data.values()):
        prev = json.loads((cache_dir(slug) / "validation" / reuse_bare / "answers.json").read_text())
        for did, dv in prev.items():
            answers.data.setdefault(did, {})["bare"] = dv["bare"]
        answers.save()

    def ask(job):
        d, variant, frame = job
        q = d[frame]
        prompt = (PERSONA.format(voice=cfg["voice"], words=cfg.get("words", "80–150"), card=card, q=q)
                  if variant == "persona" else BARE.format(name=cfg["name"], words=cfg.get("words", "80–150"), q=q))
        text = claude(prompt, answer_model)
        with answers.lock:
            answers.data.setdefault(d["id"], {}).setdefault(variant, []).append([frame, text])
            answers.save()
        print("answer", d["id"], variant, frame, file=sys.stderr, flush=True)

    jobs = []
    for d in cfg["dilemmas"]:
        for v in VARIANTS:
            have = Counter(f for f, _ in answers.data.get(d["id"], {}).get(v, []))
            jobs += [(d, v, f) for f in FRAMES for _ in range(len(TRIES) - have[f])]
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(ask, jobs))

    scores = Store(rundir / "scores.json", {})

    def judge(job):
        d, variant = job
        items = list(answers.data[d["id"]][variant])
        random.Random(f"{d['id']}{variant}").shuffle(items)
        text = "\n\n".join(f"### Odpowiedź {i + 1} (rama: {f})\n{a}" for i, (f, a) in enumerate(items))
        raw = claude(JUDGE.format(name=cfg["name"], expected=d["expected"], answers=text,
                                  character=cfg["character"], path=cfg["path"]), judge_model)
        data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
        data["frames"] = [f for f, _ in items]
        with scores.lock:
            scores.data.setdefault(d["id"], {})[variant] = data
            scores.save()
        print("judged", d["id"], variant, file=sys.stderr, flush=True)

    todo = [(d, v) for d in cfg["dilemmas"] for v in VARIANTS if v not in scores.data.get(d["id"], {})]
    random.shuffle(todo)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(judge, todo))
    report(slug, [name])


def summarise(slug: str, name: str, tics: dict) -> dict:
    rundir = cache_dir(slug) / "validation" / name
    answers = json.loads((rundir / "answers.json").read_text())
    scores = json.loads((rundir / "scores.json").read_text())
    out = {}
    for v in VARIANTS:
        t = Counter()
        per = {}
        for did, d in sorted(scores.items()):
            x = d[v]
            for a in x["answers"].values():
                t[a["verdict"]] += 1
                for k in ("character", "path", "nuance", "quotes"):
                    t[k] += a[k]
            t["consistency"] += x["consistency"]
            per[did] = {k: sum(a[k] for a in x["answers"].values()) for k in ("path", "character", "nuance")}
        texts = [a for d in answers.values() for _, a in d.get(v, [])]
        tic_counts = {k: sum(bool(re.search(p, a, re.I)) for a in texts) for k, p in tics.items()}
        out[v] = {"answers": len(texts), "totals": dict(t), "per_dilemma": per, "tics": tic_counts,
                  "with_any_tic": sum(any(re.search(p, a, re.I) for p in tics.values()) for a in texts)}
    (rundir / "summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


def report(slug: str, runs: list[str]):
    tics = json.loads((persona_dir(slug) / "validation.json").read_text()).get("tics", {})
    for name in runs:
        s = summarise(slug, name, tics)
        for v in VARIANTS:
            x, t = s[v], s[v]["totals"]
            n = x["answers"]
            print(f"{name} {v:7} n={n}  zgodne {t.get('zgodne', 0)}  uległe {t.get('ulegle', 0)}  "
                  f"rozmyte {t.get('rozmyte', 0)}  droga {t.get('path', 0)}/{2 * n}  "
                  f"charakter {t.get('character', 0)}/{2 * n}  niuans {t.get('nuance', 0)}/{2 * n}  "
                  f"ozdobniki {t.get('quotes', 0)}  spójność {t.get('consistency', 0)}  "
                  f"tiki: {x['with_any_tic']}/{n} odp.")
            if tics and v == "persona":
                print("   tiki:", {k: c for k, c in x["tics"].items() if c})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slug")
    ap.add_argument("--run", help="run directory name (default: <today>-v<card_version>)")
    ap.add_argument("--reuse-bare", metavar="RUN", help="copy the bare answers of an earlier run")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--answer-model", default="sonnet")
    ap.add_argument("--judge-model", default="opus")
    ap.add_argument("--report", nargs="+", metavar="RUN", help="only print the summary of finished runs")
    args = ap.parse_args()
    if args.report:
        report(args.slug, args.report)
        return
    name = args.run
    if not name:
        m = re.search(r"^card_version:\s*(\S+)", (persona_dir(args.slug) / "persona.md").read_text(), re.M)
        name = f"{date.today()}-v{m.group(1) if m else 'x'}"
    run(args.slug, name, args.reuse_bare, args.workers, args.answer_model, args.judge_model)


if __name__ == "__main__":
    main()
