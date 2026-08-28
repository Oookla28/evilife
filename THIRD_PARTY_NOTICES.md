# Third-party notices

This project uses small, attributed architectural adapters from the fixed
reference commits listed below. No model weights, corpora, indexes, databases,
or Git LFS artifacts are redistributed.

## medgroundAI

- Upstream: https://github.com/ArnaudTurn-pro/medgroundAI
- Reviewed commit: `a113b4b`
- Used concept/code: deterministic claim citation-envelope verification and
  rank-only reciprocal-rank fusion, adapted to EviLife's own schemas.
- License: MIT

```text
MIT License

Copyright (c) 2026 Arnaud Tauveron

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## MedRAG

- Upstream: https://github.com/gzxiong/MedRAG
- Reviewed commit: `7599a72`
- Used concept: retriever/channel separation and Reciprocal Rank Fusion. No
  MedCorp corpus, model, embedding, or index is included.
- Notice: United States Government Work / Public Domain Notice.
- Requested citation: Guangzhi Xiong, Qiao Jin, Zhiyong Lu, Aidong Zhang,
  “Benchmarking Retrieval-Augmented Generation for Medicine”.

## NutriNutri and NutriTrace

- NutriNutri reviewed commit: `4078165`, GPL-3.0.
- NutriTrace reviewed commit: `6977b48`, AGPL-3.0.
- No source code, styling, assets, or data from either project is included.
  EviLife independently implements only the general interaction ideas of
  “estimate → user correction → explicit confirmation” and objective fasting
  time recording, using the project's existing React/FastAPI architecture.

## Safety boundary

Citation existence and retrieval-envelope checks do not establish semantic
entailment or clinical correctness. Nutrition values remain estimates, and
fasting records never directly generate treatment, weight-loss, or metabolic
recommendations.
