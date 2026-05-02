import pytest
from pathlib import Path
from unittest.mock import MagicMock
from PIL import Image

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
