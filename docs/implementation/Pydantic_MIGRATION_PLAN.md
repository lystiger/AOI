# Pydantic Migration Plan

## Status

As of 2026-04-27, the migration is partially complete.

Completed:

- `POST /events` validates event payloads with Pydantic v2 models plus a thin compatibility adapter for legacy body shapes
- run creation and run update request bodies use shared Pydantic v2 request models
- manual fiducial and manual barcode request bodies use shared Pydantic v2 request models
- FastAPI validation failures now return the repository's standard error envelope with status `422`
- `src/aoi/service.py` reuses the shared Pydantic event payload adapter instead of maintaining a second handwritten parser
- `src/aoi/schema.py` no longer exposes `from_dict()` compatibility constructors; `create()` is now the authoritative domain entry point

Remaining:

- add response models only if response contracts need stricter typing later

## 1. Recommendation

Yes, moving more of the request validation to Pydantic is a good idea for this codebase.

Use **Pydantic v2** for this migration.

It is especially justified now because:

- the backend has already been migrated to FastAPI
- FastAPI works best when request validation is expressed as models instead of manual parsing
- the current code still duplicates validation logic across API handlers and domain dataclasses
- the event ingestion path in particular still does a large amount of manual shape-checking

The important constraint is scope:

- use Pydantic first at the API boundary
- do not rewrite the database layer and domain behavior at the same time
- preserve current response shapes and business logic while reducing manual parsing

Pydantic v1 should not be introduced for new code in this repository.

## 2. Current State

The current backend mixes two validation styles.

### 2.1 Domain Validation

In [src/aoi/schema.py](/home/lystiger/projects/AOI/src/aoi/schema.py):

- `InferenceEvent` is a dataclass
- `RunImageInput` is a dataclass
- validation happens in:
  - `InferenceEvent.create()`
  - `RunImageInput.create()`

This keeps domain validation centralized without maintaining duplicate dict-parsing entry points.

### 2.2 API Validation

In the FastAPI layer:

- some routes already use small Pydantic models
- other routes still manually parse JSON and then call domain validators

The biggest example is [src/aoi/api/routes/events.py](/home/lystiger/projects/AOI/src/aoi/api/routes/events.py), where:

- request bodies are manually loaded with `await request.json()`
- payload shape is manually inspected
- events and images are converted through `from_dict()` helpers

That is exactly the kind of code Pydantic should replace.

## 3. Migration Goal

After migration:

- FastAPI request bodies should be validated by Pydantic models
- route handlers should stop manually checking common field constraints
- domain objects should still be usable by the database layer
- existing behavior and tests should remain stable

The first goal is not "replace all dataclasses with Pydantic".

The first goal is:

- make the API layer declarative
- reduce hand-written validation code
- keep the domain stable while the migration is in progress

## 4. Recommended Strategy

Use a staged migration with three layers kept distinct:

1. API models
2. domain models
3. persistence logic

Recommended rule:

- Pydantic validates incoming HTTP payloads
- route handlers convert validated Pydantic models into existing domain dataclasses
- `DatabaseManager` continues to receive `InferenceEvent` and `RunImageInput` until later

This gives most of the value immediately without forcing a full rewrite.

Implementation standard:

- use Pydantic v2 APIs only
- use `BaseModel`, `ConfigDict`, `field_validator`, `model_validator`, and `model_dump()`
- do not introduce new v1-style `@validator`, `@root_validator`, or `.dict()` usage

## 5. What Should Change First

### Phase 1: API Boundary Only

Introduce Pydantic models for all FastAPI request bodies.

Priority order:

1. `POST /events`
2. image upload metadata if upload shape changes later
3. manual fiducial request
4. manual barcode request
5. create run / update run requests

The biggest win is `POST /events` because it still contains the most manual validation logic.

### Phase 2: Shared Conversion Helpers

Add explicit conversion functions from API models to domain dataclasses.

For example:

- `EventIn.model_dump()` should not be passed directly into the database layer everywhere
- use small helpers such as:
  - `to_inference_event()`
  - `to_run_image_input()`

This keeps the API layer from leaking into the domain layer.

### Phase 3: Decide Whether Domain Dataclasses Should Stay

Only after Phase 1 and 2 are stable should we decide whether to:

- keep `InferenceEvent` and `RunImageInput` as dataclasses, or
- replace them with Pydantic models too

My recommendation:

- keep the domain dataclasses for now
- do not convert the whole domain until there is a strong reason

## 6. Recommended Model Structure

Suggested new package:

```text
src/aoi/api/models/
  __init__.py
  common.py
  runs.py
  setup.py
  events.py
```

Suggested responsibilities:

- `common.py`
  - shared enums / normalized scalar types
- `runs.py`
  - `CreateRunRequest`
  - `UpdateRunRequest`
- `setup.py`
  - `ManualFiducialsRequest`
  - `ManualBarcodeRequest`
- `events.py`
  - `EventIn`
  - `RunImageInputIn`
  - `PostEventsRequest`
  - optional compatibility wrapper for list-style event payloads

## 7. Event Ingestion Migration Plan

This is the most important part of the Pydantic migration.

### 7.1 Current Problem

Current `POST /events` behavior in [src/aoi/api/routes/events.py](/home/lystiger/projects/AOI/src/aoi/api/routes/events.py) manually handles:

- payload as object or list
- optional `model_version`
- optional `images`
- validation of each image
- validation of each event
- conversion to dataclasses

This is exactly where the handwritten validation cost is highest.

### 7.2 Target Design

Introduce models like:

- `EventIn`
- `RunImageInputIn`
- `PostEventsRequest`

Recommended fields for `EventIn`:

- `timestamp: str | None`
- `pcb_id: str`
- `component_id: str`
- `inspection_result: Literal["PASS", "FAIL"]` or enum
- `defect_type: str`
- `confidence_score: float`
- `inference_latency_ms: int`
- `run_image_index: int | None`
- `overlay_x: float | None`
- `overlay_y: float | None`
- `overlay_width: float | None`
- `overlay_height: float | None`
- `overlay_shape: str | None`

Use Pydantic field constraints and validators for:

- non-empty strings
- normalized float ranges
- non-negative integer checks
- timestamp validation

Use Pydantic v2 validation style for all of the above.

### 7.3 Compatibility Concern

The legacy parser currently accepts:

- a dict with `events`
- a dict containing a single event directly
- a list of events

Pydantic can support this, but the implementation should be deliberate.

Recommended approach:

- keep one compatibility parsing function at the route boundary
- inside that function, immediately validate through Pydantic models

In other words:

- use a small compatibility adapter
- do not keep the existing manual field validation logic

## 8. Domain Model Strategy

### 8.1 Keep For Now

Keep these in [src/aoi/schema.py](/home/lystiger/projects/AOI/src/aoi/schema.py) for the first pass:

- `InferenceEvent`
- `RunImageInput`
- `InspectionResult`

Reason:

- the database code already depends on them
- the tests already exercise them
- replacing them now adds migration risk without much immediate benefit

### 8.2 Reduce Duplicate Validation

Once Pydantic handles request validation, simplify the dataclass constructors.

Examples:

- `InferenceEvent.create()` is now the only domain constructor used by API-facing code
- `RunImageInput.create()` is now the only domain constructor used by API-facing code

Eventually these can be:

- kept as the stable domain constructors if every external path goes through Pydantic first

## 9. Response Model Plan

Do not force response models everywhere immediately.

Why:

- current response payloads are plain dicts coming largely from `DatabaseManager`
- forcing full response model coverage now would create a second broad migration

Recommended response strategy:

- start with request models only
- add response models later for stable endpoints if needed

Good candidates later:

- health response
- create run response
- list runs response
- run detail response

## 10. File-Level Refactor Plan

### 10.1 `src/aoi/api/routes/events.py`

Action:

- replace `await request.json()` plus `_parse_payload()` with Pydantic-backed parsing
- keep compatibility support for current payload shapes
- implement the models with Pydantic v2 APIs only

This is the first file to change.

### 10.2 `src/aoi/api/routes/runs.py`

Action:

- move inline request models out into `api/models/`
- keep route logic thin

### 10.3 `src/aoi/schema.py`

Action:

- keep the dataclasses initially
- remove duplicated parsing methods only after all FastAPI routes use Pydantic

### 10.4 Tests

Action:

- add focused tests for Pydantic validation behavior
- keep existing route tests unchanged wherever possible

## 11. Risks

### 11.1 Breaking Compatibility

Risk:

- the current event endpoint accepts more than one payload shape

Mitigation:

- preserve compatibility in a thin adapter layer
- add explicit tests for:
  - object with `events`
  - direct event object
  - list of events

### 11.2 Double Validation

Risk:

- inputs get validated by Pydantic and then again by dataclass constructors

Mitigation:

- accept temporary double validation during transition
- remove redundant parsing/validation only after route migration is complete

### 11.3 Over-Migration

Risk:

- turning this into a rewrite of domain and persistence code

Mitigation:

- keep the first milestone strictly at the FastAPI boundary
- do not move `DatabaseManager` to Pydantic-based persistence models

## 12. Recommended Delivery Phases

### Phase 1

Deliver:

- `api/models/events.py`
- Pydantic-backed validation for `POST /events`

Exit criteria:

- manual validation logic is substantially reduced in `events.py`
- event ingestion tests still pass

Status: complete

### Phase 2

Deliver:

- move run/setup request models into `api/models/`
- update route files to import shared models instead of inline definitions

Exit criteria:

- request validation is centralized

Status: complete

### Phase 3

Deliver:

- reduce redundant parsing methods in `schema.py`
- document which constructors remain authoritative

Exit criteria:

- no important API path depends on handwritten `from_dict()` parsing

Status: complete

## 13. Acceptance Criteria

This migration is successful when:

- `POST /events` no longer manually validates individual fields
- FastAPI routes rely on Pydantic request models instead of ad hoc parsing
- all existing tests still pass
- compatibility for current payload shapes is preserved
- `schema.py` contains less duplicated validation logic than it does today

## 14. Recommendation Summary

Yes, this migration is worth doing.

But the right version of the idea is:

- Pydantic at the FastAPI boundary first
- keep the current domain model stable
- migrate `POST /events` first because it gives the highest payoff
- do not turn it into a simultaneous domain + database rewrite
- standardize on **Pydantic v2**

That will give you the validation benefits you want without destabilizing the system you just migrated.
