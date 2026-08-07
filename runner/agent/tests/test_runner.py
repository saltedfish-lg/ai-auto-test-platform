import asyncio
from pathlib import Path

from platform_runner import RunnerApplication, RunnerSettings
from platform_runner.adapters import ArtifactCollector, BrowserAdapter, PlatformTransport


class FakeBrowserAdapter:
    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakePlatformTransport:
    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None


class FakeArtifactCollector:
    async def collect(self, source: Path) -> Path:
        return source


def test_runner_starts_and_stops_without_platform_business_actions() -> None:
    async def scenario() -> None:
        settings = RunnerSettings(
            _env_file=None,
            environment="test",
            platform_url="http://127.0.0.1:8000",
            work_dir=Path(".runtime/runner-test"),
        )
        application = RunnerApplication(settings)

        await application.start()
        assert application.started is True
        await application.stop()
        assert application.started is False

    asyncio.run(scenario())


def test_runner_adapter_protocols_are_replaceable() -> None:
    assert isinstance(FakeBrowserAdapter(), BrowserAdapter)
    assert isinstance(FakePlatformTransport(), PlatformTransport)
    assert isinstance(FakeArtifactCollector(), ArtifactCollector)
