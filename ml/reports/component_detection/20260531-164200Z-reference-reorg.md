# Component Detection Reference Reorganization

Reorganized the downloaded Roboflow PCB dataset into a stable local reference path.

## Changes

- Renamed `docs/references/printed circuit board.v4-release-filtered.yolov8`
  to `docs/references/roboflow_printed_circuit_board_v4_yolov8`
- Renamed split folder `valid/` to `val/`
- Rewrote `data.yaml` to use local relative paths from the dataset root
- Added a dataset inventory note at `docs/references/roboflow_printed_circuit_board_v4_yolov8/README.md`

## Inventory

| Split | Images | Labels |
| --- | ---: | ---: |
| `train` | 548 | 548 |
| `val` | 80 | 80 |
| `test` | 44 | 44 |

## Observations

- The dataset is already in YOLOv8 format and can be imported directly.
- The class space contains 23 classes and still needs normalization for the reduced AOI taxonomy.
- Likely cleanup targets include `IC` vs `iC`, plus non-component categories such as `Pads`, `Pins`, and `Test Point`.
