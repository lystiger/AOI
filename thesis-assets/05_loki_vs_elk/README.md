# 05 — Loki vs ELK/OpenSearch · Grafana vs Kibana

**Audit part:** Part 2 (Technology Selection) · **Severity:** High
**Asset to collect here:** log-aggregation comparison table.

## Problems in the current thesis

- The defining architectural claim — Loki's **index-free, label-based** model vs
  Elasticsearch's **full-text inverted index** — is the reason Loki is
  lightweight, yet the thesis states only *"Lightweight local log aggregation and
  direct Grafana integration"* (`tab:design_decisions`, line 839) **with no
  citation and no comparison.**
- §1.4.2 (lines 249–255) describes Loki/Promtail/Grafana but cites only Loki's
  **own documentation** (`[loki]`) — no independent or comparative source.
- **OpenSearch** (the Apache-licensed Elasticsearch fork) is never mentioned,
  although it is the obvious open-source ELK alternative.
- **Grafana vs Kibana** is never discussed — you picked Grafana but never compare
  it to the ELK-native dashboard.
- The cardinality argument (line 389, "reduces label cardinality") is asserted
  but never quantified — this is exactly the Loki design constraint that should
  be cited and measured.

## Suggestions (worklist only)

- Add a **log-aggregation comparison table** (Loki vs Elasticsearch/ELK vs
  OpenSearch) across: indexing model, storage cost/footprint, query language
  (LogQL vs Lucene/DSL), operational weight, licensing, dashboarding.
- Add one paragraph on **label cardinality**: why `pcb_id`/`defect_type` are
  promoted to labels while `confidence_score`/`latency` stay as parsed JSON
  (§3.1.3 already hints at this — cite Loki's cardinality guidance and, ideally,
  measure label counts in your run).
- Add a **Grafana vs Kibana** sentence justifying Grafana (multi-source, alerting,
  provisioned-as-code).

## References & sources

- **Loki architecture** (index-free, labels): https://grafana.com/docs/loki/latest/get-started/architecture/
- **Loki label/cardinality best practices:** https://grafana.com/docs/loki/latest/get-started/labels/
- **LogQL reference:** https://grafana.com/docs/loki/latest/query/
- **Elasticsearch** (inverted index): https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- **OpenSearch docs:** https://opensearch.org/docs/latest/
- **Kibana docs:** https://www.elastic.co/kibana
- **Grafana docs:** https://grafana.com/docs/grafana/latest/

> Note: most rigorous Loki-vs-ELK comparisons are vendor sources. State this
> honestly and prefer primary architecture docs over marketing blog posts.

## Figures/tables to produce

- **T3:** Loki vs Elasticsearch/ELK vs OpenSearch comparison table (§2 or §3.1).
- Optional: measured label-cardinality count and Loki storage footprint from
  your own run (links to folder 09).

## Committee questions this pre-empts

- *"Why Loki and not the more mature ELK/OpenSearch? What is the actual
  trade-off?"*
- *"What is your label cardinality, and why does it matter for Loki?"*
- *"Why Grafana over Kibana?"*
