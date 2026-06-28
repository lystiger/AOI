# Holly AOI Deck — Page Catalog (extracted from `hollymachine.pdf`)

**Source:** *Holly AOI Training Guideline*, Shanghai Holly Electronics Co., Ltd.
(38 slides). Rendered to `page-01.jpg … page-38.jpg` in this folder (print-grade,
~2048 px wide). **Confirm with FUYU that these images may be reproduced in a
public thesis, and cite the source under every figure.**

**What this deck proves:** Holly is a **modern rule-based AOI** — CAD-driven
programming + multi-angle RGB/White lighting + luminance/threshold/template
algorithms. There is **no machine learning** in it. This is primary evidence for
the rule-based vs AI-AOI contrast (see [../03_rule_based_vs_ai/](../03_rule_based_vs_ai/README.md)).

## Page-by-page index and suggested thesis use

| Page | Content | Suggested thesis use |
|---|---|---|
| 01 | Full machine photo (cabinet, monitor, light tower) | **F2 — AOI machine photo** (folder 01) |
| 02 | "What is AOI?" definition (replaces human eyes in SMT) | §1 background prose (cite) |
| 03 | **Real defect photo grid** (missing, hole, dry-joint, no-lead, bridge, wrong part, side-lift, wrong polarity, copper, tombstone, no-solder, lifted-lead) | **F3 + T2 — defect taxonomy** (folder 02); crop individual defects |
| 04 | Holly imaging system: color camera, telecentric lens, multi-angle R/G/B/W LEDs, TOP vs SIDE image | **AOI optics/lighting diagram** (folder 01) |
| 05 | RGB reflection on flat vs slope surface (red vs green/blue effect) | optics explanation |
| 06 | Luminance value definition (0–1, min/max examples) | rule-based principle |
| 07 | Light-source adjustment, histogram, computed luminance | rule-based principle |
| 08 | **CAD file format** (txt: location, X, Y, angle, part no.; board 50430B, 1204 components) | programming workflow (rule-based evidence) |
| 09–10 | Importing CAD file wizard (software screenshots) | programming workflow |
| 11 | Capture image + CAD general layout (green frames + component list) | programming workflow |
| 12 | Adjust rail width dialog | machine setup |
| 13 | **Capture entire PCB**: Shuttle-Capturing + DISP (Dynamic multi-frame Image Seamless Patchwork); lighting-system schematic + full PCB image | **AOI image-acquisition diagram** (folder 01) |
| 14 | FOV / shuttle-capturing / DISP (FOV grid, before/after DISP) | image-acquisition explanation |
| 15 | CAD layout: top layer (CAD frame) vs bottom layer (true-color photo) | programming workflow |
| 16–17 | CAD Adjust dialog; Translate/Scale/Rotate/flip functions | programming workflow |
| 18 | *(blank slide — skip)* | — |
| 19 | Two layers superposed (CAD frame matched to real components) | programming workflow |
| 20 | **Mark Tracing** algorithm (luminance filter, OK range, result histogram) | rule-based algorithm evidence |
| 21 | **Relative Offset** algorithm (mark coordinate matching) | rule-based algorithm evidence |
| 22 | **Bad Mark** / bad-block identification (logic-OR windows) | rule-based algorithm evidence |
| 23 | Block copy for multi-block panel | programming workflow |
| 24 | **Chip Tracing** (locate pad/component center; L/W/T params) | rule-based algorithm evidence |
| 25 | Relative Offset — shift alarm (max X/Y offset) | rule-based algorithm evidence |
| 26 | **Windows Generator** (auto inspection windows for IC/connector pins) | rule-based algorithm evidence |
| 27 | **HSV Extraction** (color extraction → detect missing) | rule-based algorithm evidence |
| 28 | **Luminance Extraction** (black-area ratio → missing) | rule-based algorithm evidence |
| 29 | **Luminance Pixel Matching (OCV)** (character/graphics similarity → polarity, wrong part) | rule-based algorithm evidence |
| 30 | **Luminance Projection Min-Span** (billboard/side-lift, shift, bridge) | rule-based algorithm evidence |
| 31 | **Luminance Mean** (average brightness → wrong part) | rule-based algorithm evidence |
| 32 | **Luminance Span** (max−min brightness → shift) | rule-based algorithm evidence |
| 33 | **Template Matching (RGB)** (locate by sample image) | rule-based algorithm evidence |
| 34 | Template Matching for polarity (reverse search, max rotation) | rule-based algorithm evidence |
| 35 | **Luminance Gradient Tracing** (boundary tracking → IC no-solder) | rule-based algorithm evidence |
| 36 | **Luminance Gradient Pairs Tracing** (→ IC bridge) | rule-based algorithm evidence |
| 37 | **Luminance Gradient Pairs Distance (mm)** (→ missing/wrong part) | rule-based algorithm evidence |
| 38 | **Luminance Gradient Pairs Distance (%)** (→ wrong part) | rule-based algorithm evidence |

## How to use in the thesis
- **Best single figure:** page 03 (defect grid) → defect taxonomy table/figure,
  cross-referenced to [`docs/defects.md`](../../docs/defects.md) and IPC-A-610.
- **Machine overview:** page 01 (photo) + page 04 or 13 (optics/lighting).
- **Rule-based evidence:** one representative algorithm slide (e.g. page 20 Mark
  Tracing or page 31 Luminance Mean) is enough to show Holly is threshold-based;
  cite the deck rather than reproducing all 19 algorithm slides.
- To crop a single defect or panel from a page, use any image editor on the
  corresponding `page-NN.jpg` (full resolution is preserved).
