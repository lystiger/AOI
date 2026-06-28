# 08 — Engineering Depth: API, Database, Frontend, Docker

**Audit part:** Part 4 (Engineering Depth) · **Severity:** High
**Assets to collect here:** API endpoint table, ER diagram, component diagram,
Docker topology, Pydantic schema listing.

## Problems in the current thesis

For a thesis titled *"Design and Evaluation of an Observability **Framework**,"*
the system is **named but never designed**:

- **REST API:** only `POST /events`, health, runs are name-dropped (line 354).
  No endpoint table, no request/response schema, no status codes, no OpenAPI
  view. You already have [`docs/api_spec.md`](../../docs/api_spec.md) to promote.
- **JSON / event schema:** fields are listed (§3.1.3) but the actual
  `InferenceEvent` Pydantic model, types, constraints, enums, and rejection
  behavior are never shown — yet "schema as contract" is a stated principle
  (line 466).
- **Database design:** "SQLite is used for persistence" is one line (§3.2.1).
  No ER diagram, no table definitions, no run/event/defect relationships. You
  have [`docs/database.md`](../../docs/database.md) and [`aoi.db`](../../aoi.db).
- **Frontend architecture:** "React workstation" + one screenshot. No component
  tree, state management, or canvas/overlay rendering pipeline. You have an
  unused class diagram at [`docs/pics/class.png`](../../docs/pics/class.png).
- **Docker deployment:** Compose is mentioned (§3.3.6) but there is no
  service-topology diagram, no volumes (shared `/var/log/aoi`), no network
  description. Derive from [`docker-compose.yml`](../../docker-compose.yml).
- **Structured-logging design:** JSONL append is described, but rotation/layout/
  retention are not — you have [`docs/data_retention_policy.md`](../../docs/data_retention_policy.md).

## Suggestions (worklist only)

Promote these to **dedicated subsections** in §3 (Materials & Methods):
- §3.2.x **REST API design** — endpoint table + OpenAPI/Swagger screenshot.
- §3.2.x **Event schema** — show the `InferenceEvent` Pydantic model + validation
  rules table (ties to the safe-emission listing already in §3.2.5).
- §3.2.x **Database design** — ER diagram + table definitions.
- §3.2.x **Frontend architecture** — component tree + overlay-rendering pipeline.
- §3.x **Deployment** — Docker Compose topology diagram.

## References & sources

- FastAPI / Pydantic / OpenAPI: https://fastapi.tiangolo.com ·
  https://docs.pydantic.dev · https://www.openapis.org
- SQLite (peer-reviewed): K. P. Gaffney et al., "SQLite: Past, Present, and
  Future," *PVLDB* 15(12), 2022. https://doi.org/10.14778/3554821.3554842
- Docker: D. Merkel, *Linux Journal* 2014(239); D. Bernstein, *IEEE Cloud
  Computing* 1(3), 2014. https://doi.org/10.1109/MCC.2014.51
- REST: R. T. Fielding, *Architectural Styles and the Design of Network-based
  Software Architectures*, PhD dissertation, UC Irvine, 2000.
- React: https://react.dev

## Figures/tables to produce

- **T5:** REST API endpoint table (from `docs/api_spec.md`).
- **F4 (real):** system architecture diagram — replace ASCII
  `fig:implemented_architecture`.
- **F5:** sequence diagram POST /events → Loki → Grafana — reuse
  [`docs/pics/seq.png`](../../docs/pics/seq.png), replace ASCII
  `fig:experiment_workflow`.
- **F6:** ER diagram (SQLite) from [`aoi.db`](../../aoi.db).
- **F7:** Docker Compose topology from
  [`docker-compose.yml`](../../docker-compose.yml).
- Listing: `InferenceEvent` Pydantic model.

## Committee questions this pre-empts

- *"Show me the API contract, the database schema, and the deployment topology."*
- *"You call schema a contract — where is the schema and its validation rules?"*
- *"How does the frontend render overlays and manage state?"*
