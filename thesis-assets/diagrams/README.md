# Thesis Diagrams (Mermaid source)

Editable Mermaid sources for the figures the audit flagged as ASCII boxes or
missing. They are **grounded in the real code** (`docker-compose.yml`, the
`aoi.db` schema, the FastAPI routes) — not invented.

| File | Replaces / adds | Thesis location |
|---|---|---|
| `scope_loop.mmd` | ASCII `fig:scope_loop` (Figure 1) | §1.3 |
| `architecture.mmd` | ASCII `fig:implemented_architecture` | §3.1.2 |
| `sequence_event.mmd` | ASCII `fig:experiment_workflow` | §3.3.3 |
| `smt_pipeline.mmd` | new SMT-line figure (F1) | §1 background (folder 02) |
| `hitl_loop.mmd` | new human-in-the-loop figure | §1 / §3.2 (folder 03) |
| `docker_topology.mmd` | new deployment figure (F7) | §3 deployment (folder 08) |
| `er_diagram.mmd` | new ER figure (F6) | §3 database (folder 08) |

## Shared color palette (keep all figures consistent)

Every `.mmd` file carries an **identical** `%%{init ...}%%` theme block so the
default node fill, line color, and font match across all diagrams. Roles use a
fixed two-tone scheme — matching the matplotlib performance charts
(`scripts/plot_performance.py`, bars `#3B6FB0` / `#9AA0A6`):

| Role | Fill | Border | Used for |
|---|---|---|---|
| Process / service (default) | `#DBE9FF` | `#3B6FB0` | API, app, web, Promtail, Grafana, pipeline stages, actors |
| Storage | `#EAECEF` | `#6B7682` | SQLite, JSONL, Loki, volumes, observability cylinder (`classDef store`) |
| Future / out-of-scope | `#F0F0F0` | `#9AA0A6` dashed | retraining, root-cause analysis (`classDef future`) |
| Subgraph background | `#F5F8FC` | `#9AA0A6` | cluster boxes |

Lines `#5A6B7B`, font Helvetica/Arial. **When adding a new diagram, copy the
`%%{init ...}%%` line verbatim** and reuse `classDef store` / `classDef future`
so it matches. Re-export all seven figures together after any palette change so
the set stays uniform.

## How to render

**Option A — fastest (no install):** open <https://mermaid.live>, paste a file's
contents, then **Export → SVG** (best for LaTeX) or **PNG**.

**Option B — CLI (batch, reproducible):**
```bash
npm install -g @mermaid-js/mermaid-cli
cd thesis-assets/diagrams
for f in *.mmd; do mmdc -i "$f" -o "${f%.mmd}.pdf"; done   # or .svg / .png
```

**Option C — VS Code:** install the "Markdown Preview Mermaid Support" or
"Mermaid Editor" extension and export.

## Using in the LaTeX thesis
- Export **SVG or PDF** (vector — stays crisp in print) into `docs/paper/` or an
  assets folder, then:
  ```latex
  \begin{figure}[h]\centering
    \includegraphics[width=0.9\columnwidth]{architecture.pdf}
    \caption{Implemented observability architecture.}
    \label{fig:implemented_architecture}
  \end{figure}
  ```
- Keep the existing `\label{...}` names so current `\ref` cross-references still
  resolve, and (per the Codex prompt) comment out the old ASCII version rather
  than deleting it.

## Editing notes
- Labels use `<br/>` for line breaks and are quoted where they contain special
  characters — keep that style or mermaid.live will error.
- If you prefer **draw.io**: import is manual (Mermaid import in draw.io is
  limited); easiest path is to render SVG here and refine in draw.io if needed.
