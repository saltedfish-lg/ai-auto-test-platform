"""Replaceable Runner adapter boundaries; P0 does not fake business success."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class BrowserAdapter(Protocol):
    async def open(self) -> None:
        """Initialize the browser automation runtime."""

    async def close(self) -> None:
        """Release browser automation resources."""


@runtime_checkable
class PlatformTransport(Protocol):
    async def connect(self) -> None:
        """Open the outbound platform channel."""

    async def disconnect(self) -> None:
        """Close the outbound platform channel."""


@runtime_checkable
class ArtifactCollector(Protocol):
    async def collect(self, source: Path) -> Path:
        """Collect an artifact without reporting or uploading it."""
