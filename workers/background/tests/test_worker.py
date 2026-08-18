import asyncio

from platform_worker import WorkerApplication, WorkerSettings


def test_background_worker_starts_and_stops_without_consuming_tasks() -> None:
    async def scenario() -> None:
        settings = WorkerSettings(
            _env_file=None,
            environment="test",
            database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        )
        application = WorkerApplication(settings)

        await application.start()
        assert application.started is True
        await application.stop()
        assert application.started is False

    asyncio.run(scenario())


def test_background_worker_uses_atp_database_url_before_legacy_alias(monkeypatch) -> None:
    governed = "mysql+pymysql://worker:local@127.0.0.1/worker_governed"
    monkeypatch.setenv("PLATFORM_ENVIRONMENT", "test")
    monkeypatch.setenv("ATP_DATABASE_URL", governed)
    monkeypatch.setenv(
        "PLATFORM_DATABASE_URL",
        "mysql+pymysql://legacy:local@127.0.0.1/worker_legacy",
    )
    assert WorkerSettings(_env_file=None).database_url == governed
