# Notices

**Results (`results/`) are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).** They contain questions from the BEAM benchmark, which is published under that licence, alongside Jelly's answers and the judge's verdicts.

**BEAM.** "Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs" by Mohammad Tavakoli, Alireza Salemi, Carrie Ye, Mohamed Abdalla, Hamed Zamani and J Ross Mitchell ([arXiv:2510.27246](https://arxiv.org/abs/2510.27246)). Dataset: [mohammadtavakoli78/BEAM](https://github.com/mohammadtavakoli78/BEAM), CC BY-SA 4.0. This repository ships none of the conversations; `scripts/rescore.py` downloads the questions from the authors' repository at a pinned commit.

**ExaBase's BEAM prompts.** The answer and judge prompts used for the run are ExaBase's published BEAM prompts ([source](https://fabric.so/p/beam-3VjBcqEVRofZyA5CeazeX)), as copied in past.dev's harness ([pastdotdev/benchmarks](https://github.com/pastdotdev/benchmarks), MIT). This repository does not include them; `scripts/rescore.py` downloads past.dev's copy at a pinned commit and checks it by SHA-256. The prompts remain ExaBase's work.

**Smart Jelly** is a product of Keystone Intelligence Technologies Inc. Jelly's memory and retrieval are proprietary and not included.
