import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image, ImageDraw

from aoi.vision_service import VisionService
from aoi.setup_service import SetupService
from aoi.database import DatabaseManager

@pytest.fixture
def temp_paths(tmp_path):
    db_path = tmp_path / "test.db"
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    return db_path, storage_path

@pytest.fixture
def vision_service(temp_paths):
    db_path, storage_path = temp_paths
    return VisionService(db_path=db_path, storage_path=storage_path)

@pytest.fixture
def setup_service(temp_paths):
    db_path, storage_path = temp_paths
    db_manager = DatabaseManager(db_path)
    vision_service = VisionService(db_path=db_path, storage_path=storage_path)
    return SetupService(db_manager, vision_service)

def test_vision_service_prepare_detection_image(vision_service):
    # Create a large image
    large_image = Image.new("RGB", (2000, 1000))
    resized, scale = vision_service._prepare_detection_image(large_image)
    
    assert resized.size == (1000, 500)
    assert scale == 2.0

def test_vision_service_build_fiducial_candidate_mask(vision_service):
    # Create a small image with a "gold" pixel
    image = Image.new("HSV", (10, 10), color=(0, 0, 0))
    # Hue 30, Sat 100, Val 100 is "gold-like" in the algorithm
    image.putpixel((5, 5), (30, 100, 100))
    
    mask = vision_service._build_fiducial_candidate_mask(image.convert("RGB"))
    
    # Check if our point is represented (might be slightly shifted due to filters)
    assert any(val == 1 for val in mask)


def test_vision_service_detect_components_returns_component_candidates(vision_service, tmp_path):
    image_path = tmp_path / "component-board.png"
    image = Image.new("RGB", (1200, 800), color=(28, 126, 82))
    draw = ImageDraw.Draw(image)
    draw.rectangle((160, 140, 320, 260), fill=(40, 40, 46), outline=(220, 220, 220), width=4)
    draw.rectangle((540, 220, 710, 380), fill=(182, 182, 182), outline=(245, 245, 245), width=3)
    draw.rectangle((860, 470, 1040, 610), fill=(62, 62, 68), outline=(205, 205, 205), width=4)
    image.save(image_path)

    components = vision_service.detect_components(
        {
            "id": "img-1",
            "image_path": str(image_path),
            "image_width": 1200,
            "image_height": 800,
        },
        "run-1",
    )

    assert len(components) >= 3
    assert all(component["run_image_id"] == "img-1" for component in components[:3])
    assert all(component["confidence"] >= 0.4 for component in components[:3])


def test_vision_service_detect_components_uses_reference_classifier_when_available(vision_service, tmp_path, monkeypatch):
    image_path = tmp_path / "component-board-labeled.png"
    image = Image.new("RGB", (600, 400), color=(28, 126, 82))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 100, 240, 200), fill=(40, 40, 46), outline=(220, 220, 220), width=4)
    image.save(image_path)

    class StubClassifier:
        def classify(self, image, candidate):
            return "resistor", 0.91

    monkeypatch.setattr(vision_service, "_load_reference_component_classifier", lambda: StubClassifier())

    components = vision_service.detect_components(
        {
            "id": "img-2",
            "image_path": str(image_path),
            "image_width": 600,
            "image_height": 400,
        },
        "run-2",
    )

    assert components
    assert components[0]["label"] == "resistor"
    assert components[0]["classification_confidence"] == 0.91


def test_vision_service_detect_components_marks_low_confidence_predictions_as_suspect(
    vision_service,
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "component-board-suspect.png"
    image = Image.new("RGB", (600, 400), color=(28, 126, 82))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 100, 240, 200), fill=(40, 40, 46), outline=(220, 220, 220), width=4)
    image.save(image_path)

    class StubClassifier:
        def classify(self, image, candidate):
            return "resistor", 0.56

    monkeypatch.setattr(vision_service, "_load_reference_component_classifier", lambda: StubClassifier())

    components = vision_service.detect_components(
        {
            "id": "img-3",
            "image_path": str(image_path),
            "image_width": 600,
            "image_height": 400,
        },
        "run-3",
    )

    assert components
    assert components[0]["label"] == "component_candidate"
    assert components[0]["predicted_label"] == "resistor"
    assert components[0]["label_quality"] == "suspect"

def test_setup_service_create_run(setup_service):
    run = setup_service.create_run(pcb_id="TEST-PCB")
    
    assert run["pcb_id"] == "TEST-PCB"
    assert run["status"] == "SETUP"
    assert run["setup_status"] == "not_ready"

def test_setup_service_calculate_setup_status_logic(setup_service):
    # Mocking some dependencies or using the actual DB
    run_id = "test-run"
    model_name = "MODEL-X"
    
    # 1. Not ready (no images)
    status = setup_service._calculate_setup_status(run_id, model_name, requires_fiducials=True, fiducial_status="ready")
    assert status == "in_progress" # because it has a model_name
    
    # 2. Review Ready logic
    # We'd need to mock fetch_run_images to return something
    setup_service.database.fetch_run_images = MagicMock(return_value=[{"id": "img1"}])
    
    status = setup_service._calculate_setup_status(
        run_id, 
        model_name, 
        requires_fiducials=True, 
        fiducial_status="confirmed",
        requires_barcode=False
    )
    assert status == "review_ready"


def test_setup_service_generate_run_fov_crops_refreshes_hybrid_component_detection(temp_paths, monkeypatch):
    db_path, storage_path = temp_paths
    database = DatabaseManager(db_path)
    vision_service = VisionService(db_path=db_path, storage_path=storage_path)
    service = SetupService(database, vision_service)

    run = database.create_run(pcb_id="PCB-HYBRID")
    image_path = storage_path / "hybrid-board.png"
    image = Image.new("RGB", (1200, 800), color=(28, 126, 82))
    draw = ImageDraw.Draw(image)
    draw.rectangle((160, 140, 320, 260), fill=(40, 40, 46), outline=(220, 220, 220), width=4)
    draw.rectangle((540, 220, 710, 380), fill=(182, 182, 182), outline=(245, 245, 245), width=3)
    image.save(image_path)

    with database._connect() as connection:
        connection.execute(
            """
            INSERT INTO run_images (id, run_id, image_path, image_role, image_width, image_height, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("img-1", run["id"], str(image_path), "full_board", 1200, 800, 0, run["timestamp"]),
        )

    database.update_run(run["id"], model_name="MODEL-HYBRID")
    database.save_model_fovs(
        "MODEL-HYBRID",
        [
            {"id": "fov-left", "label": "FOV Left", "x": 0.05, "y": 0.10, "width": 0.28, "height": 0.28},
            {"id": "fov-center", "label": "FOV Center", "x": 0.30, "y": 0.14, "width": 0.32, "height": 0.34},
        ],
    )

    def stub_detect_components(image, run_id):
        return [
            {
                "id": f"cmp-{image['id']}",
                "run_image_id": image["id"],
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.2,
                "confidence": 0.8,
                "label": "component_candidate",
            }
        ]

    monkeypatch.setattr(service.vision_service, "detect_components", stub_detect_components)

    refreshed_run = service.generate_run_fov_crops(run["id"])

    assert refreshed_run is not None
    fov_images = [entry for entry in database.fetch_run_images(run["id"]) if entry["image_role"].startswith("fov:")]
    assert len(fov_images) == 2
    component_image_ids = {component["run_image_id"] for component in refreshed_run["components"]}
    assert "img-1" in component_image_ids
    assert all(image["id"] in component_image_ids for image in fov_images)
