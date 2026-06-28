# 01 — AOI Machine Overview

**Audit part:** Part 1 (Industrial Context) · **Severity:** High
**Asset to collect here:** one AOI-machine diagram or photograph.

## Problems in the current thesis

- §1 Introduction (lines 156–164) asserts *"AOI systems are widely used in
  electronics manufacturing… increasingly incorporate AI-based models"* but
  **never describes an actual AOI machine** — no cameras, lighting, conveyor,
  field-of-view, or inline placement. The claim *"increasingly incorporate AI"*
  (line 156) is **uncited**.
- The word **"AOI" in the title is unsupported** by any hardware or process
  description. A reader cannot tell this is about optical inspection hardware
  rather than a generic logging demo.
- "Latency" is treated abstractly (§3.1.2; scenario S03) with **no physical
  reason** for why it matters — i.e., that an inline AOI must keep pace with the
  line tact time, which is what makes the S03 latency signal operationally real.

## Suggestions (do not edit the paper here — this is the worklist)

- Add a background subsection **before §1.4 Related Work**, e.g.
  *"§1.x Background: AOI in PCB Manufacturing,"* with ~2 paragraphs + 1 figure:
  - AOI machine = camera(s) + multi-angle/multi-spectral lighting + conveyor +
    image-processing unit; 2D vs 3D AOI; inline vs offline; FOV stitching.
  - Inline tact-time constraint → this is the bound your "near real time" and
    S03 latency anomaly should be compared against.
- Connect explicitly to your work: the events you log (`inference_latency_ms`,
  `confidence_score`) originate from this machine's inference stage.
- If FUYU/Foxconn permits, use a **real factory photo** (strongest option) and
  caption it as the host-line AOI station.

## References & sources

- R. Ebayyeh & A. Mousavi, "A Review and Analysis of Automatic Optical
  Inspection and Quality Monitoring Methods in Electronics Industry," *IEEE
  Access* 8 (2020). https://doi.org/10.1109/ACCESS.2020.3029127
- Vendor documentation (machine diagrams, lighting, 3D AOI):
  Koh Young https://www.kohyoung.com · Omron VT-S series
  https://industrial.omron.com · CyberOptics https://www.cyberoptics.com ·
  Test Research Inc (TRI) https://www.tri.com.tw · ViTrox
  https://www.vitrox.com · Saki https://www.sakicorp.com · Mirtec
  https://www.mirtec.com

## Figures/tables to produce

- **F2:** AOI machine diagram or photo (own factory preferred; else vendor with
  permission/attribution). Insert in the new §1.x background subsection.

## Committee questions this pre-empts

- *"Where in this thesis is an actual AOI machine? Justify the word 'AOI' in the
  title."*
- *"You cite a rising trend of AI in AOI — source?"*

---

## UPDATE — asset now available (Holly AOI deck)

`hollymachine.pdf` (Holly AOI Training Guideline, Shanghai Holly Electronics) was
added and extracted to `page-01.jpg … page-38.jpg`. See [CATALOG.md](CATALOG.md)
for the page-by-page index.

- **Machine photo:** use `page-01.jpg` for **F2**.
- **Optics/lighting:** `page-04.jpg` (color camera, telecentric lens, multi-angle
  R/G/B/W LEDs, TOP vs SIDE) and `page-13.jpg` (Shuttle-Capturing + DISP).
- **Confirmed fact:** the Holly machine is **rule-based, not AI** — it uses
  CAD-driven programming + luminance/threshold/template algorithms. This is
  primary evidence for [folder 03](../03_rule_based_vs_ai/README.md).
- **Licensing:** confirm with FUYU that these slides may appear in a public
  thesis, and caption every figure "Source: Shanghai Holly Electronics Co., Ltd."
