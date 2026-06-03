# Backend Release Readiness Review

Date: 2026-06-03

## Findings

### 1. Critical: `GET /runs/{run_id}/images/{image_id}` can serve arbitrary files from the server filesystem

A client can first create a run image record through `POST /events`, then use the image read path to fetch unintended files.

- `src/aoi/api/models/events.py` accepts any non-empty `image_path`
- `src/aoi/database.py` persists that path unchanged
- `src/aoi/api/routes/runs.py` returns absolute paths, existing relative paths, or resolved paths under `storage_path.parent`

Even for a thesis/demo deployment with no authentication requirement, this is still a release blocker because the backend should not expose arbitrary local files through image-path resolution.

### 2. High: repeated scan uploads corrupt image history and make image IDs unreliable

`upload_run_image` always overwrites `scan.{ext}` on disk but inserts a brand-new database image row with a new `image_id`.

- Old image records remain in the database
- The image fetch path ignores the stored logical image ID for `/runs/{run_id}/images/{image_id}` records and serves the latest matching `scan.png/jpg/jpeg`
- Older image entries can therefore point to the newest file instead of the original upload

This breaks traceability and makes image history unreliable for customer review and audit use.

### 3. High: the frontend FOV save flow is broken in the shipped dev/compose environment

The UI posts FOV data to `/models/{model}/fovs`, but the Vite proxy only forwards:

- `/health`
- `/runs`
- `/events`

In the provided Docker setup, the customer reaches the app through that Vite server. That means saving FOVs will hit the frontend origin and fail with `404` unless another reverse proxy exists outside this repo.

### 4. High: the frontend container is shipping a Vite development server, not a production build

The web container runs `npm run dev` and is exposed directly in `docker-compose.yml`.

Risks:

- dependency on dev-server proxy behavior
- HMR and dev middleware in customer-facing deployment
- non-production serving stack at release time

This is not a sound production shipping path.

### 5. Medium: the documented backend setup is incomplete and fails on a clean machine

The README backend quick start installs only `requirements-dev.txt`, while runtime dependencies live in `requirements.txt`.

Following the README as written will miss:

- `fastapi`
- `uvicorn`
- `pillow`

That means backend startup is not reproducible from the documented setup instructions.

## Assumptions

- This review assumes the project is being prepared for thesis/demo delivery rather than a hardened multi-user production deployment.
- No authentication or authorization is required for that thesis scope.
- This review assumes `docker-compose.yml` reflects the intended deployment path.
- If there is an external reverse proxy in front of `aoi-web`, the FOV route failure may already be masked, but the dev-server deployment risk still remains.
- A trusted internal/demo network reduces exposure, but it does not remove the unsafe filesystem path resolution issue.

## Verification

Executed checks:

- `venv/bin/pip install -r requirements.txt -r requirements-dev.txt && venv/bin/python -m pytest`
- `npm run lint`
- `npm run build`

Results:

- backend tests: `60 passed`
- frontend lint: passed
- frontend build: passed

## Residual Risk

There are no frontend integration or E2E tests in the repo. The main frontend issues above are runtime/configuration defects rather than unit-test failures.
