"""Check a published run's numbers, with no API calls and no dependencies.

For every question it recomputes the score from the verdicts saved with it,
using the published scoring rules, then recomputes each category and the
headline and compares them with summary.json:

- rubric questions: each judge verdict's raw score rounds to 1 (from 0.75),
  0.5 (from 0.25) or 0; the question scores the mean of its rounded verdicts;
- event ordering: the answer's order is compared with the reference order by
  Kendall tau-b, mapped to 0-1, a topic missing from one order ranked after
  everything in it (as scipy.stats.kendalltau(variant="b") computes it);
- the headline is the mean over all questions.

    python3 scripts/verify.py results/beam-100k/jelly-v1

Python 3.8 or newer, standard library only.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def rounded(raw: float) -> float:
    return 1.0 if raw >= 0.75 else 0.5 if raw >= 0.25 else 0.0


def tau_b(x: list[int], y: list[int]) -> float | None:
    concordant = discordant = x_ties = y_ties = total = 0
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            total += 1
            dx, dy = x[i] - x[j], y[i] - y[j]
            x_ties += dx == 0
            y_ties += dy == 0
            if dx and dy:
                if (dx > 0) == (dy > 0):
                    concordant += 1
                else:
                    discordant += 1
    denominator = math.sqrt((total - x_ties) * (total - y_ties))
    return None if denominator == 0 else (concordant - discordant) / denominator


def ordering_score(reference: list[str], answer: list[str]) -> float:
    if not reference or not answer:
        return 0.0
    topics = list(dict.fromkeys(reference + answer))
    missing = len(topics) + 1

    def ranks(order):
        position = {topic: i + 1 for i, topic in enumerate(order)}
        return [position.get(topic, missing) for topic in topics]

    tau = tau_b(ranks(reference), ranks(answer))
    return 0.0 if tau is None else (tau + 1) / 2


def main(run: Path) -> int:
    verdicts = [json.loads(line) for line in (run / "verdicts.jsonl").read_text().splitlines() if line.strip()]
    answers = {json.loads(line)["id"] for line in (run / "answers.jsonl").read_text().splitlines() if line.strip()}
    summary = json.loads((run / "summary.json").read_text())
    problems = []

    ids = [v["id"] for v in verdicts]
    if len(ids) != len(set(ids)):
        problems.append("a question is scored more than once")
    if set(ids) != answers:
        problems.append("answers and verdicts cover different questions")

    by_category = defaultdict(list)
    for v in verdicts:
        if v["method"] == "event_ordering":
            score = ordering_score(v["reference"], v["answer_order"])
        else:
            items = v["items"]
            for item in items:
                if abs(rounded(item["raw_score"]) - item["score"]) > 1e-9:
                    problems.append(f"{v['id']}: a verdict is rounded wrongly")
            score = sum(rounded(i["raw_score"]) for i in items) / len(items) if items else 0.0
        if abs(score - v["score"]) > 1e-9:
            problems.append(f"{v['id']}: saved score {v['score']} but the verdicts give {score}")
        by_category[v["id"].split("/")[2]].append(score)

    overall = sum(s for scores in by_category.values() for s in scores) / len(verdicts) * 100
    print(f"{summary['system']}: {len(verdicts)} questions")
    for category, scores in sorted(by_category.items()):
        mine = sum(scores) / len(scores) * 100
        published = summary["by_category"][category]
        flag = "" if abs(mine - published) < 0.006 else "   <-- differs"
        print(f"  {category:<26} {mine:6.2f}%   published {published:6.2f}%{flag}")
        if flag:
            problems.append(f"{category}: {mine:.2f} against published {published:.2f}")
    print(f"  {'overall':<26} {overall:6.2f}%   published {summary['overall']:6.2f}%")
    if abs(overall - summary["overall"]) >= 0.006:
        problems.append(f"overall {overall:.2f} against published {summary['overall']:.2f}")

    if problems:
        print("\nPROBLEMS:")
        for p in problems[:50]:
            print("  " + p)
        return 1
    print("\nEvery score follows from its verdicts, and the summary is their mean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "results/beam-100k/jelly-v1")))
