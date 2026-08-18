import asyncio

from platform_scheduler import SchedulerApplication, SchedulerSettings


def test_scheduler_starts_and_stops_without_scheduling_business_work() -> None:
    async def scenario() -> None:
        settings = SchedulerSettings(
            _env_file=None,
            environment="test",
            database_url="mysql+pymysql://platform:local@127.0.0.1/platform_test",
        )
        application = SchedulerApplication(settings)

        await application.start()
        assert application.started is True
        await application.stop()
        assert application.started is False

    asyncio.run(scenario())


def test_scheduler_uses_atp_database_url_before_legacy_alias(monkeypatch) -> None:
    governed = "mysql+pymysql://scheduler:local@127.0.0.1/scheduler_governed"
    monkeypatch.setenv("PLATFORM_ENVIRONMENT", "test")
    monkeypatch.setenv("ATP_DATABASE_URL", governed)
    monkeypatch.setenv(
        "PLATFORM_DATABASE_URL",
        "mysql+pymysql://legacy:local@127.0.0.1/scheduler_legacy",
    )
    assert SchedulerSettings(_env_file=None).database_url == governed
