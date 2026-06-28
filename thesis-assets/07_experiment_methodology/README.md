# 07 — Experiment Methodology (S01–S09)

**Audit part:** Part 3 (Experiments) · **Severity:** Medium
**Status:** This is the **strongest** part of the thesis — §3.3.4 already answers
*why each scenario, how it maps to industry, how it was injected, what changed,
what is validated*, and honestly states it validates the pipeline, not detector
accuracy. The notes below are refinements, not a rewrite.

## Problems / gaps

1. **n = 1.** The suite was run **once** (June 25, 2026; §4.1.5). No repetition,
   no variance, no confidence interval. Values are reported as single numbers
   despite acknowledged jitter (lines 1006–1009).
2. **Arbitrary thresholds.** 0.60 fail rate / 500 ms / 0.60 confidence
   (lines 521–522) appear with **no derivation**. They look hand-tuned to make
   alerts fire.
3. **Detection latency is bounded from config, not measured** (§4.2.5,
   lines 1166–1174). For an observability thesis, onset→alert time is the
   headline metric and it is estimated, not instrumented.
4. **Scenario magnitudes are asserted as realistic but uncited** — e.g. "9:1
   fail ratio = bad material reel" (S02), "2000 ms = accelerator starvation"
   (S03).
5. **S09 (drift) lacks drift literature**, although it is called the "most
   analytically important" scenario (line 904).
6. **No baseline detector comparison.** Justifiably out of scope, but a one-line
   pre-emption citing an anomaly-detection survey would close the door.

## Suggestions (worklist only)

- Re-run the suite ≥5× and report **mean ± SD** for at least: end-to-end
  ingestion completeness and alert-firing latency. Or scope n=1 explicitly with
  justification.
- **Derive thresholds from the S01 baseline** (e.g., mean + 3σ) or cite a basis;
  add one sentence explaining the choice.
- **Measure detection latency**: timestamp injection, timestamp alert-state
  change, report the delta per threshold scenario (S02–S04). Highest-value
  single fix in the whole experiment chapter.
- Add citations for scenario realism (Paleyes 2022; Ebayyeh & Mousavi 2020) and
  for drift (Gama 2014; Lu 2019).

## References & sources

- A. Paleyes, R.-G. Urma, N. D. Lawrence, "Challenges in Deploying Machine
  Learning: A Survey of Case Studies," *ACM Computing Surveys* 55(6), 2022.
  https://doi.org/10.1145/3533378
- J. Gama et al., "A Survey on Concept Drift Adaptation," *ACM Computing
  Surveys* 46(4), 2014. https://doi.org/10.1145/2523813
- J. Lu et al., "Learning under Concept Drift: A Review," *IEEE TKDE* 31(12),
  2019.
- V. Chandola, A. Banerjee, V. Kumar, "Anomaly Detection: A Survey," *ACM
  Computing Surveys* 41(3), 2009. https://doi.org/10.1145/1541880.1541882
- A. Blázquez-García et al., "A Review on Outlier/Anomaly Detection in Time
  Series Data," *ACM Computing Surveys* 54(3), 2021.

## Figures/tables to produce

- Detection-latency table with **measured** onset→firing times (upgrade of
  `tab:detection_latency`).
- Multi-run variance table (mean ± SD) for ingestion completeness.
- **F9–F14:** embed the already-captured `s02, s04, s05, s06, s07, s08`
  screenshots from [`assets/readme/anomaly/`](../../assets/readme/anomaly/).

## Committee questions this pre-empts

- *"You ran this once — is it reproducible? What is the variance?"*
- *"Where do the alert thresholds come from?"*
- *"What is the actual onset-to-alert detection time?"*
- *"Are these injected magnitudes realistic? Source?"*
