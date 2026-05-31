"""Variant loading and backbone injection for component-detection experiments."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from torch import nn

from ml.pipeline.attention_modules import AttentionWrappedBlock, CBAM, ChannelAttention

DEFAULT_BACKBONE_C2F_INDICES = (2, 4, 6)
SUPPORTED_VARIANTS = ("baseline", "channel_attention", "full_cbam")


@dataclass(frozen=True, slots=True)
class VariantConfig:
    name: str
    attention_type: str
    target_indices: tuple[int, ...]


def get_variant_config(variant: str) -> VariantConfig:
    if variant == "baseline":
        return VariantConfig(name=variant, attention_type="none", target_indices=())
    if variant == "channel_attention":
        return VariantConfig(name=variant, attention_type="channel", target_indices=DEFAULT_BACKBONE_C2F_INDICES)
    if variant == "full_cbam":
        return VariantConfig(name=variant, attention_type="cbam", target_indices=DEFAULT_BACKBONE_C2F_INDICES)
    raise ValueError(f"Unsupported model variant: {variant}")


def build_component_model(*, base_model: str | Path, variant: str):
    """Load YOLO and inject the requested attention variant into backbone C2f blocks."""
    from ultralytics import YOLO

    model = YOLO(str(base_model))
    config = get_variant_config(variant)
    if config.attention_type == "none":
        return model

    sequential = model.model.model
    for index in config.target_indices:
        try:
            block = sequential[index]
        except IndexError as exc:
            raise IndexError(f"Target block index {index} does not exist in YOLO backbone") from exc

        if type(block).__name__ != "C2f":
            raise TypeError(f"Expected C2f at index {index}, found {type(block).__name__}")

        channels = _infer_output_channels(block)
        attention = _make_attention(config.attention_type, channels)
        sequential[index] = AttentionWrappedBlock(block, attention)

    return model


def _infer_output_channels(block: nn.Module) -> int:
    cv2 = getattr(block, "cv2", None)
    conv = getattr(cv2, "conv", None)
    out_channels = getattr(conv, "out_channels", None)
    if isinstance(out_channels, int) and out_channels > 0:
        return out_channels

    value = getattr(block, "c2", None)
    if isinstance(value, int) and value > 0:
        return value

    value = getattr(block, "c", None)
    if isinstance(value, int) and value > 0:
        return value

    for module in reversed(list(block.modules())):
        out_channels = getattr(module, "out_channels", None)
        if isinstance(out_channels, int) and out_channels > 0:
            return out_channels

    raise ValueError(f"Unable to infer output channels for block {block!r}")


def _make_attention(attention_type: str, channels: int) -> nn.Module:
    if attention_type == "channel":
        return ChannelAttention(channels)
    if attention_type == "cbam":
        return CBAM(channels)
    raise ValueError(f"Unsupported attention type: {attention_type}")
