"""Attention modules for YOLOv8 experiment variants."""
from __future__ import annotations

import torch
from torch import nn


class ChannelAttention(nn.Module):
    """Standard channel attention using avg/max pooled descriptors."""

    def __init__(self, channels: int, reduction: int = 16) -> None:
        super().__init__()
        hidden = max(1, channels // reduction)
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.mlp = nn.Sequential(
            nn.Conv2d(channels, hidden, kernel_size=1, bias=False),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, channels, kernel_size=1, bias=False),
        )
        self.gate = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        attention = self.mlp(self.avg_pool(x)) + self.mlp(self.max_pool(x))
        return x * self.gate(attention)


class SpatialAttention(nn.Module):
    """Spatial attention over pooled channel statistics."""

    def __init__(self, kernel_size: int = 7) -> None:
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv2d(2, 1, kernel_size=kernel_size, padding=padding, bias=False)
        self.gate = nn.Sigmoid()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg_map = torch.mean(x, dim=1, keepdim=True)
        max_map, _ = torch.max(x, dim=1, keepdim=True)
        attention = self.conv(torch.cat([avg_map, max_map], dim=1))
        return x * self.gate(attention)


class CBAM(nn.Module):
    """Convolutional Block Attention Module."""

    def __init__(self, channels: int, reduction: int = 16, spatial_kernel_size: int = 7) -> None:
        super().__init__()
        self.channel_attention = ChannelAttention(channels, reduction=reduction)
        self.spatial_attention = SpatialAttention(kernel_size=spatial_kernel_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.channel_attention(x)
        x = self.spatial_attention(x)
        return x


class AttentionWrappedBlock(nn.Module):
    """Wrap an existing block with post-block attention."""

    def __init__(self, block: nn.Module, attention: nn.Module) -> None:
        super().__init__()
        self.block = block
        self.attention = attention
        # Preserve Ultralytics graph metadata used during predict/val traversal.
        for attribute in ("i", "f", "type", "np"):
            if hasattr(block, attribute):
                setattr(self, attribute, getattr(block, attribute))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.attention(self.block(x))
