from pathlib import Path

from ml.pipeline.component_dataset import (
    REDUCED_COMPONENT_CLASSES,
    _load_roboflow_board_annotations,
    _roboflow_board_id_from_name,
    load_board_annotation,
    normalize_component_label,
    split_boards,
)


def test_normalize_component_label_maps_known_aliases() -> None:
    assert normalize_component_label('"electrolytic capacitor" unknown', profile="full") == "capacitor"
    assert normalize_component_label("ferrite bead FB1", profile="full") == "ferrite_bead"
    assert normalize_component_label("emi filter FL1", profile="full") == "emi_filter"
    assert normalize_component_label("zener D5", profile="full") == "diode"
    assert normalize_component_label("switch reset", profile="full") == "button"


def test_normalize_component_label_drops_non_component_noise() -> None:
    assert normalize_component_label("text GND", profile="reduced") is None
    assert normalize_component_label('"component text" 103', profile="reduced") is None
    assert normalize_component_label("pads unknown", profile="reduced") is None
    assert normalize_component_label("test point TP1", profile="reduced") is None


def test_normalize_component_label_collapses_reduced_profile_to_other() -> None:
    assert normalize_component_label("inductor L1", profile="reduced") == "other"
    assert normalize_component_label("button RESET", profile="reduced") == "other"
    assert normalize_component_label("Resistor Network", profile="reduced") == "resistor"
    assert normalize_component_label("Electrolytic Capacitor", profile="reduced") == "capacitor"
    assert "other" in REDUCED_COMPONENT_CLASSES


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
    <name>button RESET</name>
    <bndbox><xmin>35</xmin><ymin>5</ymin><xmax>55</xmax><ymax>20</ymax></bndbox>
  </object>
  <object>
    <name>text GND</name>
    <bndbox><xmin>40</xmin><ymin>5</ymin><xmax>50</xmax><ymax>10</ymax></bndbox>
  </object>
</annotation>
        """.strip(),
        encoding="utf-8",
    )

    annotation = load_board_annotation(xml_path, profile="reduced")

    assert annotation.board_id == "BoardA"
    assert annotation.image_path == image_path
    assert annotation.width == 100
    assert annotation.height == 50
    assert len(annotation.boxes) == 2
    assert annotation.boxes[0].class_name == "resistor"
    assert annotation.boxes[1].class_name == "other"


def test_roboflow_board_id_strips_augmented_suffixes() -> None:
    assert _roboflow_board_id_from_name("ACM-109_Top_jpg.rf.bb8e27c1888a9f6ba7c61ffef6c1dd0e") == "ACM-109_Top"
    assert _roboflow_board_id_from_name("ATTIOT_Top_JPG_jpg.rf.1c69fe2eb6cfe54c5f1e05eb8da5df50") == "ATTIOT_Top"


def test_load_roboflow_board_annotations_normalizes_yolo_labels(tmp_path: Path) -> None:
    root = tmp_path / "roboflow"
    (root / "train" / "images").mkdir(parents=True)
    (root / "train" / "labels").mkdir(parents=True)
    (root / "val" / "images").mkdir(parents=True)
    (root / "val" / "labels").mkdir(parents=True)
    (root / "test" / "images").mkdir(parents=True)
    (root / "test" / "labels").mkdir(parents=True)
    (root / "data.yaml").write_text(
        """
path: .
train: train/images
val: val/images
test: test/images
nc: 4
names: ['IC', 'Pads', 'Electrolytic Capacitor', 'Resistor Network']
        """.strip(),
        encoding="utf-8",
    )

    from PIL import Image

    image_path = root / "train" / "images" / "BoardA_jpg.rf.deadbeef.jpg"
    Image.new("RGB", (100, 50), color="white").save(image_path)
    (root / "train" / "labels" / "BoardA_jpg.rf.deadbeef.txt").write_text(
        "\n".join(
            [
                "0 0.500000 0.500000 0.200000 0.400000",
                "1 0.100000 0.100000 0.100000 0.100000",
                "2 0.250000 0.300000 0.100000 0.200000",
                "3 0.700000 0.600000 0.200000 0.200000",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    annotations = _load_roboflow_board_annotations(root, profile="reduced")

    assert len(annotations) == 1
    annotation = annotations[0]
    assert annotation.board_id == "BoardA"
    assert annotation.width == 100
    assert annotation.height == 50
    assert [box.class_name for box in annotation.boxes] == ["ic", "capacitor", "resistor"]
