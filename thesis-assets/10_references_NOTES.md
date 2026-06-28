# 10 — References: Problems & Additions

**Audit part:** Part 6 (References) · **Severity:** High
**Companion file:** [`10_references.bib`](10_references.bib) — **currently empty
(1 byte).**

## Problems in the current thesis

- The thesis still uses **14 manual `\bibitem` entries** in
  [`thesis_usth.tex`](../docs/paper/thesis_usth.tex); the prepared
  `10_references.bib` is empty and unused.
- **14 references is thin** for a bachelor thesis, and the distribution is
  lopsided:
  - **0** industrial-AOI references
  - **0** PCB-manufacturing references
  - **0** IPC standards (despite `docs/defects.md` claiming IPC-A-610 compliance)
  - **0** technology-comparison / benchmark references
  - **0** CNCF / OpenTelemetry references
- Several primary claims are cited only to **vendor self-documentation**
  (`[loki]`, `[fastapi]`, Netflix Mantis, Triton) with no independent or
  comparative source.

Target: **~30–40 references**. Verify exact volume/page/DOI before submission.

## Additions to make (BibTeX-ready list)

### Industrial AOI / PCB (highest priority — currently none)
- Ebayyeh & Mousavi, "A Review and Analysis of Automatic Optical Inspection…,"
  *IEEE Access* 8 (2020). https://doi.org/10.1109/ACCESS.2020.3029127
- Ling & Isa, "PCB Defect Detection Methods… A Survey," *IEEE Access* 11 (2023).
  https://doi.org/10.1109/ACCESS.2023.3245093
- Moganti et al., "Automatic PCB Inspection Algorithms: A Survey," *CVIU* 63(2),
  1996. https://doi.org/10.1006/cviu.1996.0017
- **IPC-A-610H**, *Acceptability of Electronic Assemblies*, IPC.
  https://www.electronics.org/ipc-610-acceptability-electronics-assemblies-endorsement-program
- Coombs & Holden, *Printed Circuits Handbook*, 7th ed., McGraw-Hill.

### Observability / SRE (strengthen)
- Majors, Fong-Jones, Miranda, *Observability Engineering*, O'Reilly, 2022.
- Sridharan, *Distributed Systems Observability*, O'Reilly, 2018.
- OpenTelemetry Specification (CNCF). https://opentelemetry.io/docs/specs/otel/
- Prometheus documentation (CNCF). https://prometheus.io/docs/

### ML deployment / drift / anomaly (fills experiment gaps)
- Paleyes, Urma, Lawrence, "Challenges in Deploying ML: A Survey of Case
  Studies," *ACM CSUR* 55(6), 2022. https://doi.org/10.1145/3533378
- Gama et al., "A Survey on Concept Drift Adaptation," *ACM CSUR* 46(4), 2014.
  https://doi.org/10.1145/2523813
- Lu et al., "Learning under Concept Drift: A Review," *IEEE TKDE* 31(12), 2019.
- Chandola, Banerjee, Kumar, "Anomaly Detection: A Survey," *ACM CSUR* 41(3),
  2009. https://doi.org/10.1145/1541880.1541882
- Blázquez-García et al., "A Review on Outlier/Anomaly Detection in Time Series
  Data," *ACM CSUR* 54(3), 2021.

### Technology choices (for Part 2 comparison tables)
- Gaffney et al., "SQLite: Past, Present, and Future," *PVLDB* 15(12), 2022.
  https://doi.org/10.14778/3554821.3554842
- Merkel, "Docker: Lightweight Linux Containers…," *Linux Journal* 2014(239).
- Bernstein, "Containers and Cloud: From LXC to Docker to Kubernetes," *IEEE
  Cloud Computing* 1(3), 2014. https://doi.org/10.1109/MCC.2014.51
- Fielding, *Architectural Styles… (REST)*, PhD dissertation, UC Irvine, 2000.
- TechEmpower Web Framework Benchmarks. https://www.techempower.com/benchmarks/

## Suggestions (worklist only)

- Populate `10_references.bib` and switch the thesis from manual `\bibitem` to
  **BibTeX** so entries stay consistent and reusable.
- Keep the existing 14 (they are fine for the MLOps/observability angle); the
  problem is **coverage**, not the current entries.

## Committee questions this pre-empts

- *"Only 14 references, none on AOI/PCB manufacturing — did you survey the
  domain you claim to work in?"*
- *"Your key tool claims cite only the vendors' own docs — any independent
  evidence?"*
