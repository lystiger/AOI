### 3. `docs/defect_types.md`
# Defect Classification Schema (IPC-A-610 Compliant)

This schema defines the categories for `defect_type` in the log JSON.

## 1. Solder Joint Defects
- `SOLDER_BRIDGE`: Unintended connection between adjacent pads.
- `INSUFFICIENT_SOLDER`: Solder volume below IPC minimum.
- `SOLDER_BALL`: Excess solder particles on board surface.

## 2. Component Placement Defects
- `MISSING_COMPONENT`: Component not present at expected coordinates.
- `MISALIGNMENT`: Component offset exceeds allowable tolerance (±X, ±Y).
- `REVERSED_POLARITY`: Component oriented incorrectly (specifically for diodes/ICs).

## 3. Lead Defects
- `BENT_LEAD`: Pin deformation outside specified profile.
- `LIFTED_LEAD`: Lead not in contact with solder pad.