import asyncio

from platform_api import ApiSettings, create_app
from platform_runner import RunnerApplication, RunnerSettings
from platform_scheduler import SchedulerApplication, SchedulerSettings
from platform_worker import WorkerApplication, WorkerSettings


def test_all_python_processes_assemble_from_installed_packages() -> None:
    database_url = "mysql+pymysql://platform:local@127.0.0.1/platform_test"
    api_settings = ApiSettings(
        _env_file=None,
        environment="test",
        database_url=database_url,
    )
    assert create_app(api_settings).state.settings.service_name == "platform-api"

    async def scenario() -> None:
        scheduler = SchedulerApplication(
            SchedulerSettings(
                _env_file=None,
                environment="test",
                database_url=database_url,
            )
        )
        worker = WorkerApplication(
            WorkerSettings(
                _env_file=None,
                environment="test",
                database_url=database_url,
            )
        )
        runner = RunnerApplication(
            RunnerSettings(
                _env_file=None,
                environment="test",
                platform_url="http://127.0.0.1:8000",
                work_dir=".runtime/runner-integration",
            )
        )

        await scheduler.start()
        await worker.start()
        await runner.start()
        assert scheduler.started and worker.started and runner.started
        await runner.stop()
        await worker.stop()
        await scheduler.stop()

    asyncio.run(scenario())
