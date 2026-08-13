import asyncio
import base64
import json
import secrets
from pathlib import Path

from platform_api import ApiSettings, create_app
from platform_api.keygen import generate_development_key_ring
from platform_runner import RunnerApplication, RunnerSettings
from platform_scheduler import SchedulerApplication, SchedulerSettings
from platform_worker import WorkerApplication, WorkerSettings


def test_all_python_processes_assemble_from_installed_packages(tmp_path: Path) -> None:
    database_url = "mysql+pymysql://platform:local@127.0.0.1/platform_test"
    jwt_key_ring = generate_development_key_ring(tmp_path / "jwt")
    hmac_key_ring = tmp_path / "auth-hmac-key-ring.json"
    hmac_key_ring.write_text(
        json.dumps(
            {
                "ring_version": "process-assembly-v1",
                "active_key_id": "active",
                "keys": [
                    {
                        "key_id": "active",
                        "key_material": base64.urlsafe_b64encode(secrets.token_bytes(32))
                        .rstrip(b"=")
                        .decode("ascii"),
                        "activated_at": "2025-01-01T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    api_settings = ApiSettings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        jwt_key_ring_file=jwt_key_ring.manifest_file,
        auth_hmac_master_key_file=hmac_key_ring,
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
