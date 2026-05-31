from pathlib import Path

from ml.pipeline.component_dataset import (
    COMPONENT_CLASSES,
    load_board_annotation,
    normalize_component_label,
    split_boards,
)


def test_normalize_component_label_maps_known_aliases() -> None:
    assert normalize_component_label('"electrolytic capacitor" unknown') == "capacitor"
    assert normalize_component_label("ferrite bead FB1") == "ferrite_bead"
    assert normalize_component_label("emi filter FL1") == "emi_filter"
    assert normalize_component_label("zener D5") == "diode"
    assert normalize_component_label("switch reset") == "button"


def test_normalize_component_label_drops_non_component_noise() -> None:
    assert normalize_component_label("text GND") is None
    assert normalize_component_label('"component text" 103') is None
    assert normalize_component_label("pads unknown") is None
    assert normalize_component_label("test point TP1") is None


def test_split_boards_keeps_board_ids_disjoint() -> None:
    splits = split_boards(["a", "b", "c", "d", "e", "f"], seed=7)
    assert sum(len(ids) for ids in splits.values()) == 6
    assert splits["train"].isdisjoint(splits["val"])
    assert splits["train"].isdisjoint(splits["test"])
    assert splits["val"].isdisjoint(splits["test"])


def test_load_board_annotation_filters_to_supported_component_classes(tmp_path: Path) -> None:
    board_dir = tmp_path / "BoardA"
    board_dir.mkdir()
    image_path = board_dir / "BoardA.png"
    image_path.write_bytes(b"fake image payload")
    xml_path = board_dir / "BoardA.xml"
    xml_path.write_text(
        """
<annotation>
  <filename>BoardA.png</filename>
  <size><width>100</width><height>50</height><depth>3</depth></size>
  <object>
    <name>resistor R1</name>
    <bndbox><xmin>10</xmin><ymin>5</ymin><xmax>30</xmax><ymax>20</ymax></bndbox>
  </object>
  <object>
    <name>text GND</name>
    <bndbox><xmin>40</xmin><ymin>5</ymin><xmax>50</xmax><ymax>10</ymax></bndbox>
  </object>
</annotation>
        """.strip(),
        encoding="utf-8",
    )

    annotation = load_board_annotation(xml_path)

    assert annotation.board_id == "BoardA"
    assert annotation.image_path == image_path
    assert annotation.width == 100
    assert annotation.height == 50
    assert len(annotation.boxes) == 1
    assert annotation.boxes[0].class_name in COMPONENT_CLASSES
    assert annotation.boxes[0].class_name == "resistor"
