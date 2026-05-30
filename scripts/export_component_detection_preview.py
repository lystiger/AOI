from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from aoi.vision_service import VisionService


QUALITY_COLORS = {
    "strong": ("#00c27a", "#07281c"),
    "accepted": ("#3b82f6", "#0f1d3a"),
    "suspect": ("#f59e0b", "#3a2706"),
    "rejected": ("#ef4444", "#3a1010"),
}


def export_preview(input_path: Path, output_path: Path) -> int:
    with Image.open(input_path) as source_image:
        width, height = source_image.size
        annotated = source_image.convert("RGB")

    service = VisionService(db_path=output_path.parent / "preview.db", storage_path=output_path.parent / "preview-assets")
    components = service.detect_components(
        {
            "id": "preview-image",
            "image_path": str(input_path),
            "image_width": width,
            "image_height": height,
        },
        "preview-run",
    )

    draw = ImageDraw.Draw(annotated)
    for component in components:
        x1 = int(float(component["x"]) * width)
        y1 = int(float(component["y"]) * height)
        x2 = int((float(component["x"]) + float(component["width"])) * width)
        y2 = int((float(component["y"]) + float(component["height"])) * height)
        quality = str(component.get("label_quality") or "accepted")
        outline, fill = QUALITY_COLORS.get(quality, QUALITY_COLORS["accepted"])
        label = str(component.get("label") or "component_candidate")
        predicted_label = str(component.get("predicted_label") or label)
        confidence = float(component.get("classification_confidence") or component.get("confidence") or 0.0)
        caption = f"{predicted_label} {confidence:.2f} {quality}"

        draw.rectangle((x1, y1, x2, y2), outline=outline, width=3)
        text_box = draw.textbbox((x1, max(0, y1 - 18)), caption)
        draw.rectangle(text_box, fill=fill)
        draw.text((text_box[0], text_box[1]), caption, fill=outline)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output_path)
    return len(components)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an annotated PCB component-detection preview image")
    parser.add_argument("--input", required=True, help="Path to the PCB image")
    parser.add_argument("--output", required=True, help="Path for the annotated preview image")
    args = parser.parse_args()

    count = export_preview(Path(args.input), Path(args.output))
    print(f"exported {count} component overlays to {args.output}")


if __name__ == "__main__":
    main()
