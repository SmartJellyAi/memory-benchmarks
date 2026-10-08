# Jelly memory benchmarks

Published results for [Smart Jelly](https://smartjelly.ai/memory)'s memory on public long-term-memory benchmarks — every answer, every judge verdict, and scripts to check the numbers without trusting us.

## BEAM-100K: 87.57%

[BEAM](https://arxiv.org/abs/2510.27246) (Tavakoli et al., ICLR 2026) tests memory over long conversations. Its 100K split has 20 conversations of about 100,000 tokens and 400 questions across ten abilities. We ran all 400 once, on 29 September 2026.

| Ability | Jelly |
| --- | --- |
| Abstention | 98.75% |
| Contradiction resolution | 73.75% |
| Event ordering | 100.00% |
| Information extraction | 84.69% |
| Instruction following | 90.00% |
| Knowledge update | 75.62% |
| Multi-session reasoning | 61.09% |
| Preference following | 98.75% |
| Summarization | 96.82% |
| Temporal reasoning | 96.25% |
| **Overall** | **87.57%** |

### Every published BEAM-100K result

| System | BEAM-100K | Models | Source |
| --- | --- | --- | --- |
| past.dev | 91.84% | gpt-5.6-luna answers and judges | [past.dev/benchmarks](https://past.dev/benchmarks), runs of 16 and 19 Sep 2026 |
| **Jelly** | **87.57%** | gpt-5.6-luna answers and judges | this repository, 29 Sep 2026 |
| Exabase M-1 | 76.9% | Gemini 3 Flash answers | [exabase.io](https://exabase.io/blog/exabase-m1-achieves-state-of-the-art-on-beam-benchmark), 19 Sep 2026 |
| Hindsight | 75.0% | not stated | [benchmarks.hindsight.vectorize.io](https://benchmarks.hindsight.vectorize.io/) |
| Honcho | 63.0% | Claude Haiku 4.5 answers | [plasticlabs.ai](https://plasticlabs.ai/blog/research/Benchmarking-Honcho), 19 Dec 2025 |
| LIGHT (BEAM paper) | 35.8% | Llama-4-Maverick | [Tavakoli et al.](https://arxiv.org/abs/2510.27246) |
| RAG baseline (BEAM paper) | 32.3% | Llama-4-Maverick | [Tavakoli et al.](https://arxiv.org/abs/2510.27246) |

Each row is that team's own published run. Only past.dev's used the same protocol and answering model as ours; the others differ in models, judges and set-up. Checked against each source on 29 September 2026 (Hindsight's earlier post gave 73.4%; its benchmarks page gives 75.0%).

## How the run was done

- **Dataset.** BEAM's 100K split from the authors' repository, [`mohammadtavakoli78/BEAM`](https://github.com/mohammadtavakoli78/BEAM) at commit `b2da22e`, using each conversation's truncated chat file where one exists, as BEAM's own harness does.
- **Memory.** Each conversation was stored in Jelly the way the app stores a conversation, and each question was answered from what Jelly recalled: about 8,000 tokens of evidence per question (the per-question size is in `answers.jsonl`). Jelly's memory and retrieval are proprietary and not part of this repository.
- **Answering and judging.** `gpt-5.6-luna` with reasoning off for both, one user message per call — the same model and settings past.dev reports.
- **Protocol.** ExaBase's published BEAM answer and judge prompts, as past.dev uses them ([past.dev's copy](https://github.com/pastdotdev/benchmarks/tree/main/beam), commit `307991e`). Knowledge-update questions are asked as of the update the dataset cites; every other question at the end of the conversation.
- **Scoring.** Rubric questions: each rubric item is judged separately and scored 0, 0.5 or 1 (a raw score from 0.75 counts as 1, from 0.25 as 0.5), and the question scores their mean. Event ordering: the answer's list is matched to the reference topics by the judge and scored by Kendall tau-b, mapped to 0-1. The headline is the mean over all 400 questions.
- **Runs.** One. A repeat would move the headline by roughly two points either way.

## What you should know about the number

- **The protocol gives the answering model hints.** ExaBase's answer prompt passes parts of the dataset's own annotations to the answering model: the rubric points a summary should cover, the time points and a calculation hint for temporal questions, the topics to put in order, the preference or instruction being tested, and why a question may be unanswerable. Its judge sees the question. That is why event ordering and temporal reasoning score near 100% for every system run this way. We use it because it is how the published leaderboard numbers were produced, so ours compares with them.
- **Two retrieval changes were validated on this split.** We changed how Jelly ranks keyword matches and how much weight recency gets after measuring evidence recall on these 400 questions, and checked on LongMemEval-S that everyday recall did not get worse. They are general changes, not tuned to particular questions, but they were not validated on a held-out split.
- **Other teams' numbers are their own**, with their own models and settings.

## Check it yourself

```sh
# The numbers follow from the verdicts (no API calls, no dependencies)
python3 scripts/verify.py results/beam-100k/jelly-v1

# The published questions are BEAM's, and the prompts are the published ones
python3 scripts/rescore.py --check results/beam-100k/jelly-v1

# Re-judge every answer yourself (about 1,000 calls, roughly $0.15)
OPENAI_API_KEY=...     python3 scripts/rescore.py results/beam-100k/jelly-v1
OPENROUTER_API_KEY=... python3 scripts/rescore.py results/beam-100k/jelly-v1
```

`rescore.py` downloads BEAM's questions and past.dev's copy of the prompts at pinned commits, checks them by SHA-256, and judges our saved answers from scratch. A judge is a model, so a re-judged score lands near the published one rather than exactly on it.

## Files

| Path | What it holds |
| --- | --- |
| `results/beam-100k/<run>/answers.jsonl` | One line per question: id (`100K/<conversation>/<category>/<index>`), the question, Jelly's answer, and the evidence size in tokens |
| `results/beam-100k/<run>/verdicts.jsonl` | The judge's verdicts behind each score: per rubric item the raw and rounded score and the judge's reply; for event ordering the reference and the matched answer order |
| `results/beam-100k/<run>/summary.json` | Per-category and overall scores |
| `scripts/verify.py` | Recomputes every score from its verdicts |
| `scripts/rescore.py` | Re-judges every answer with the published prompts |

## What is not here

- **Jelly's code.** How Jelly stores and recalls memory is ours; the answers show what it recalled.
- **The evidence text** each answer was given. The published run did not keep it; runs from here on will record it.
- **The dataset and the third-party prompts.** The scripts download them from their authors.

## Licences and credit

- Code (`scripts/`): MIT, see `LICENSE`.
- Results (`results/`): CC BY-SA 4.0, because they contain BEAM's questions. See `NOTICE.md`.
- BEAM is by Mohammad Tavakoli, Alireza Salemi, Carrie Ye, Mohamed Abdalla, Hamed Zamani and J Ross Mitchell ([arXiv:2510.27246](https://arxiv.org/abs/2510.27246)), published under CC BY-SA 4.0. The answer and judge prompts are ExaBase's; the harness conventions follow past.dev's published BEAM harness.
