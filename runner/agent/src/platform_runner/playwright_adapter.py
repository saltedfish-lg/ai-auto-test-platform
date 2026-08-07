"""Real Playwright runtime adapter; it is not started by the P0 process check."""

from __future__ import annotations

from playwright.async_api import Playwright, async_playwright


class PlaywrightBrowserAdapter:
    def __init__(self) -> None:
        self._playwright: Playwright | None = None

    async def open(self) -> None:
        if self._playwright is not None:
            raise RuntimeError("Playwright adapter is already open")
        self._playwright = await async_playwright().start()

    async def close(self) -> None:
        if self._playwright is None:
            return
        await self._playwright.stop()
        self._playwright = None
