"""Re-judge every published answer from scratch, with your own API key.

This does not trust our verdicts. It downloads, at pinned versions, and
checks by SHA-256:

- BEAM's probing questions, rubrics and annotations from the authors'
  repository (mohammadtavakoli78/BEAM);
- past.dev's copy of ExaBase's published BEAM prompts and its dataset helpers
  (pastdotdev/benchmarks, MIT), the protocol behind the published BEAM-100K
  numbers;

then judges each of our answers with those prompts and the same judge model,
applies the same scoring rules as scripts/verify.py, and prints the result
beside ours. A judge is a model, so a re-judged run lands near, not exactly
on, the published number -- expect well under a point either way.

    python3 scripts/rescore.py --check results/beam-100k/jelly-v1     # no API calls
    OPENAI_API_KEY=... python3 scripts/rescore.py results/beam-100k/jelly-v1
    OPENROUTER_API_KEY=... python3 scripts/rescore.py results/beam-100k/jelly-v1

--check downloads and verifies everything and confirms every published
question matches BEAM's, without judging. A full re-judge is about 1,000 calls;
with gpt-5.6-luna that costs roughly $0.15. Python 3.10 or newer, standard
library only.
"""
from __future__ import annotations

import sys

if sys.version_info < (3, 10):
    raise SystemExit("rescore.py needs Python 3.10 or newer (past.dev's dataset helpers it downloads use 3.10 syntax)")

import hashlib
import importlib.util
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from verify import ordering_score, rounded

BEAM = "https://raw.githubusercontent.com/mohammadtavakoli78/BEAM/b2da22eac88bb0874c64665f13457eb99835774a/chats/100K/{conversation}/probing_questions/probing_questions.json"
PASTDEV = "https://raw.githubusercontent.com/pastdotdev/benchmarks/307991eddc2e0ff9f68d11f1d79b1d9c60fe3309/beam/{file}"
PASTDEV_SHA256 = {
    "exabase_prompts.py": "dd4b903e3808a0a8207abedf43f30f906a96e0afd2446510ed4416fab0f8692a",
    "dataset.py": "4e7a02de3c68a25d984105447c88f939cb843ef2868a1a38df2d5ad2fb36e2f2",
}
CACHE = Path(os.environ.get("JELLY_BENCH_CACHE", Path.home() / ".cache" / "jelly-memory-benchmarks"))


def fetch(url: str, sha256: str | None = None) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as r:
            path.write_bytes(r.read())
    data = path.read_bytes()
    if sha256 and hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"{url} does not match its pinned SHA-256; refusing to use it")
    return data


def load_pastdev():
    folder = CACHE / "pastdev"
    folder.mkdir(parents=True, exist_ok=True)
    for name, sha in PASTDEV_SHA256.items():
        (folder / name).write_bytes(fetch(PASTDEV.format(file=name), sha))
    sys.path.insert(0, str(folder))
    modules = {}
    for name in ("exabase_prompts", "dataset"):
        spec = importlib.util.spec_from_file_location(name, folder / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    return modules["exabase_prompts"], modules["dataset"]


class Judge:
    """gpt-5.6-luna, reasoning off, replies held to the prompt's JSON schema."""

    def __init__(self):
        if os.environ.get("OPENAI_API_KEY"):
            self.url, self.key, self.model, self.openrouter = "https://api.openai.com/v1/chat/completions", os.environ["OPENAI_API_KEY"], "gpt-5.6-luna", False
        elif os.environ.get("OPENROUTER_API_KEY"):
            self.url, self.key, self.model, self.openrouter = "https://openrouter.ai/api/v1/chat/completions", os.environ["OPENROUTER_API_KEY"], "openai/gpt-5.6-luna", True
        else:
            raise SystemExit("set OPENAI_API_KEY or OPENROUTER_API_KEY")

    def json(self, prompt: str, schema: dict) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "benchmark_response", "strict": True, "schema": {
                "type": "object", "properties": schema["properties"], "required": schema["required"], "additionalProperties": False}}},
        }
        if self.openrouter:
            body["reasoning"] = {"effort": "none"}
            body["provider"] = {"require_parameters": True}
        else:
            body["reasoning_effort"] = "none"
        for attempt in range(4):
            try:
                request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers={
                    "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=90) as r:
                    text = json.loads(r.read())["choices"][0]["message"]["content"]
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return json.loads(text[text.find("{"): text.rfind("}") + 1])
            except urllib.error.HTTPError as e:
                if e.code in (401, 402, 403):
                    raise SystemExit(f"the API refused the key: HTTP {e.code}")
                if attempt == 3:
                    raise
            except Exception:
                if attempt == 3:
                    raise
            time.sleep(2 ** attempt)


def score_one(judge, prompts, dataset, question_text, category, item, answer):
    notes = dataset.annotations(category, item)
    gold = dataset.gold_answers(item)
    if category == "event_ordering":
        reference = notes.get("ordering_tested") or (list_items(gold[0]) if gold else [])
        items = list_items(answer)
        if not reference or not items:
            return 0.0
        matched, renamed = set(), []
        for it in items:
            hit = None
            for i, topic in enumerate(reference):
                if i not in matched:
                    reply = judge.json(prompts.equivalence_prompt(topic, it), prompts.EQUIVALENCE_SCHEMA)
                    if str(reply.get("answer", "")).strip().upper().startswith("YES"):
                        hit = i
                        break
            renamed.append(it if hit is None else reference[hit])
            if hit is not None:
                matched.add(hit)
        return ordering_score(reference, renamed)
    rubric = notes.get("rubric") or ([f"LLM response should contain: {gold[0]}"] if gold else [])
    if not rubric:
        return 0.0
    scores = []
    for r in rubric:
        try:
            raw = float(judge.json(prompts.rubric_item_prompt(question_text, answer, r), prompts.RUBRIC_SCHEMA).get("score", 0))
        except SystemExit:
            raise
        except Exception:
            raw = 0.0  # as ExaBase's adapter does: a verdict the judge could not give scores 0
        scores.append(rounded(raw))
    return sum(scores) / len(scores)


def list_items(text: str) -> list[str]:
    import re
    return [s for s in (re.sub(r"^\s*(?:\d+[.)]\s*|[-*]\s*)", "", line).strip() for line in text.strip().splitlines()) if s]


def main(run: Path, check_only: bool) -> None:
    prompts, dataset = load_pastdev()
    judge = None if check_only else Judge()
    answers = [json.loads(line) for line in (run / "answers.jsonl").read_text().splitlines() if line.strip()]
    published = json.loads((run / "summary.json").read_text())
    probing = {c: json.loads(fetch(BEAM.format(conversation=c))) for c in sorted({a["conversation"] for a in answers})}

    def work(a):
        item = probing[a["conversation"]][a["category"]][a["index"]]
        if item.get("question", "") != a["question"]:
            raise SystemExit(f"{a['id']}: the question does not match BEAM's")
        if check_only:
            return a["id"], a["category"], None
        return a["id"], a["category"], score_one(judge, prompts, dataset, a["question"], a["category"], item, a["answer"])

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, answers))
    if check_only:
        print(f"Downloads verified; all {len(results)} published questions match BEAM's, word for word.")
        return
    out = run / "rescored.jsonl"
    with out.open("w") as f:
        for qid, category, score in results:
            f.write(json.dumps({"id": qid, "category": category, "score": score}) + "\n")
    by = {}
    for _, category, score in results:
        by.setdefault(category, []).append(score)
    print(f"{published['system']}, re-judged: {len(results)} questions")
    for category, scores in sorted(by.items()):
        print(f"  {category:<26} {sum(scores) / len(scores) * 100:6.2f}%   published {published['by_category'][category]:6.2f}%")
    overall = sum(s for _, _, s in results) / len(results) * 100
    print(f"  {'overall':<26} {overall:6.2f}%   published {published['overall']:6.2f}%")
    print(f"\nPer-question scores written to {out}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--check"]
    main(Path(args[0] if args else "results/beam-100k/jelly-v1"), "--check" in sys.argv)
