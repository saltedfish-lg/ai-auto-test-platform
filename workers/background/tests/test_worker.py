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
