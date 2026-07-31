"""Tests de la CLI Typer (minuta §33) y del app factory (minuta §8, §34).

CLI cubre:
  - Estructura: nombre, ayuda, sub-apps registrados.
  - Comandos base: version, serve.
  - Engagement: create, activate.
  - Scope: import.
  - Job: list, status, events, cancel.
  - Evidence: list, inspect, verify.
  - Interface: list, info, prepare, restore, diagnose.

App factory cubre:
  - create_app: configuración FastAPI, middleware, router, exception handlers.
  - Lifespan: inicio y parada de JobManager.
  - Módulo: app = create_app() al cargarse.

Notas técnicas:
  - Los sub-apps se verifican vía ``app.registered_groups`` (Typer >=0.13).
  - Los comandos con import perezoso (``import uvicorn`` dentro de la función)
    se parchean desde su ubicación real, no desde ``aegiswifi.cli.*``.
  - ``Middleware`` de Starlette expone ``.kwargs`` (no ``.options``).
  - ``app.routes`` incluye objetos sin ``.path`` (``_IncludedRouter``),
    hay que filtrar.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from aegiswifi.cli import app as cli_app

runner = CliRunner()

# ===================================================================
# CLI Structure Tests
# ===================================================================


class TestCliAppStructure:
    def test_app_name(self):
        assert cli_app.info.name == "aegiswifi"

    def test_app_help_mentions_auditoria(self):
        assert cli_app.info.help is not None
        assert "auditoría" in cli_app.info.help

    def test_sub_apps_registered(self):
        """Sub-aplicaciones añadidas con add_typer() aparecen en registered_groups."""
        groups = {g.name for g in cli_app.registered_groups}
        for name in ("engagement", "scope", "job", "evidence", "interface", "discovery"):
            assert name in groups, f"sub-app '{name}' no registrado"

    def test_root_commands_registered(self):
        """Comandos directos (@app.command()) se registran por callback."""
        cbs = {c.callback.__name__ for c in cli_app.registered_commands if c.callback}
        assert "version" in cbs
        assert "serve" in cbs


# ===================================================================
# CLI: Version Command
# ===================================================================


class TestVersionCommand:
    @patch("aegiswifi.cli.__version__", "0.1.0")
    @patch("aegiswifi.cli.get_settings")
    def test_version_output(self, mock_settings):
        mock_settings.return_value.environment = "development"
        result = runner.invoke(cli_app, ["version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.stdout
        assert "development" in result.stdout


# ===================================================================
# CLI: Serve Command
# ===================================================================


class TestServeCommand:
    @patch("aegiswifi.cli.get_settings")
    def test_serve_defaults(self, mock_settings):
        """serve usa settings por defecto.
        Nota: uvicorn se importa dentro de la función, así que parcheamos
        ``uvicorn.run`` directamente.
        """
        mock_settings.return_value.api_host = "127.0.0.1"
        mock_settings.return_value.api_port = 8000
        mock_settings.return_value.is_dev = False

        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(cli_app, ["serve"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            "aegiswifi.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )

    @patch("aegiswifi.cli.get_settings")
    def test_serve_with_overrides(self, mock_settings):
        """serve acepta host/port explícitos."""
        mock_settings.return_value.is_dev = False
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(cli_app, ["serve", "--host", "0.0.0.0", "--port", "9000"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            "aegiswifi.main:app",
            host="0.0.0.0",
            port=9000,
            reload=False,
        )


# ===================================================================
# CLI: Engagement Commands
# ===================================================================


class TestEngagementCommands:
    """Module-level imports: ``aegiswifi.cli.engagements_service`` existe."""

    @patch("aegiswifi.cli.get_sessionmaker")
    @patch("aegiswifi.cli.engagements_service")
    def test_create(self, mock_service, mock_sm):
        """engagement create invoca create_engagement y muestra resultado."""
        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_eng = MagicMock()
        mock_eng.id = 1
        mock_eng.code = "ENG-2026-001"
        mock_eng.status = "DRAFT"
        mock_service.create_engagement.return_value = mock_eng

        result = runner.invoke(cli_app, [
            "engagement", "create",
            "--name", "Test",
            "--client", "Client",
            "--operator", "Op",
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1
        assert data["code"] == "ENG-2026-001"
        assert data["status"] == "DRAFT"
        mock_service.create_engagement.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("aegiswifi.cli.get_sessionmaker")
    @patch("aegiswifi.cli.engagements_service")
    def test_activate(self, mock_service, mock_sm):
        """engagement activate invoca activate y muestra resultado."""
        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_eng = MagicMock()
        mock_eng.id = 1
        mock_eng.code = "ENG-2026-001"
        mock_eng.status = "ACTIVE"
        mock_service.activate.return_value = mock_eng

        result = runner.invoke(cli_app, ["engagement", "activate", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ACTIVE"
        mock_service.activate.assert_called_once_with(mock_session, 1)
        mock_session.close.assert_called_once()


# ===================================================================
# CLI: Scope Command
# ===================================================================


class TestScopeCommand:
    """Module-level import: ``aegiswifi.cli.scope_service`` existe."""

    @patch("aegiswifi.cli.get_sessionmaker")
    @patch("aegiswifi.cli.scope_service")
    def test_import_scope(self, mock_service, mock_sm, tmp_path):
        """scope import llama import_scope y muestra resultado."""
        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        scope_file = tmp_path / "scope.yaml"
        scope_file.write_text("dummy", encoding="utf-8")

        mock_scope = MagicMock()
        mock_scope.scope.allowed_ssids = ["TEST-NET"]
        mock_scope.scope.allowed_bssids = ["AA:BB:CC:DD:EE:FF"]
        mock_scope.permissions.model_dump.return_value = {"passive_capture": True}

        mock_service.import_scope.return_value = (
            MagicMock(code="ENG-2026-001"),
            mock_scope,
        )

        result = runner.invoke(cli_app, [
            "scope", "import", str(scope_file),
            "--engagement", "1",
        ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["engagement"] == "ENG-2026-001"
        assert "TEST-NET" in data["ssids"]


# ===================================================================
# CLI: Job Commands (import perezoso dentro de la función)
# ===================================================================


class TestJobCommands:
    """Los comandos job importan ``from aegiswifi.jobs import service as jobs_service``
    dentro del cuerpo de la función. Parcheamos las funciones reales."""

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_job_list(self, mock_sm):
        from unittest.mock import MagicMock, patch

        from aegiswifi.database.models import JobStatus

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.kind = "passive_capture"
        mock_job.status = JobStatus.CREATED.value
        mock_job.priority = 0
        mock_job.progress = 0.0
        mock_job.error_message = None

        with patch("aegiswifi.jobs.service.list_jobs") as mock_list:
            mock_list.return_value = [mock_job]
            result = runner.invoke(cli_app, ["job", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["kind"] == "passive_capture"

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_job_status(self, mock_sm):
        from datetime import UTC, datetime
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.kind = "handshake_capture"
        mock_job.status = "RUNNING"
        mock_job.priority = 5
        mock_job.progress = 0.5
        mock_job.error_message = None
        mock_job.group_id = None
        mock_job.timeout_seconds = 300
        mock_job.worker_pid = 12345
        mock_job.heartbeat_at = None
        mock_job.started_at = datetime(2026, 7, 29, 10, 0, 0, tzinfo=UTC)
        mock_job.finished_at = None
        mock_job.log_path = "/tmp/job_1.log"
        mock_job.sha256 = "abc123"
        mock_job.parameters = {"interface": "wlan0"}
        mock_job.result_summary = None
        mock_job.created_at = datetime(2026, 7, 29, 9, 0, 0, tzinfo=UTC)
        mock_job.updated_at = datetime(2026, 7, 29, 10, 0, 0, tzinfo=UTC)

        with patch("aegiswifi.jobs.service.get_job") as mock_get:
            mock_get.return_value = mock_job
            result = runner.invoke(cli_app, ["job", "status", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1
        assert data["status"] == "RUNNING"
        assert data["parameters"] == {"interface": "wlan0"}

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_job_events(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.from_status = "CREATED"
        mock_event.to_status = "QUEUED"
        mock_event.message = "job enqueued"
        mock_event.created_at = "2026-07-29T09:00:00"

        with patch("aegiswifi.jobs.service.list_job_events") as mock_events:
            mock_events.return_value = [mock_event]
            result = runner.invoke(cli_app, ["job", "events", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["to"] == "QUEUED"

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_job_cancel(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = "CANCELLED"

        with patch("aegiswifi.jobs.service.cancel_job") as mock_cancel:
            mock_cancel.return_value = mock_job
            result = runner.invoke(cli_app, ["job", "cancel", "1", "--message", "test"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "CANCELLED"


# ===================================================================
# CLI: Evidence Commands (import perezoso)
# ===================================================================


class TestEvidenceCommands:
    @patch("aegiswifi.cli.get_sessionmaker")
    def test_evidence_list(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_cap = MagicMock()
        mock_cap.id = 1
        mock_cap.category = "original"
        mock_cap.format = "pcapng"
        mock_cap.sha256 = "ab" * 32
        mock_cap.original_filename = "capture.pcapng"
        mock_cap.size_bytes = 1024
        mock_cap.tool = "tcpdump"
        mock_cap.created_at = "2026-07-29T10:00:00"

        with patch("aegiswifi.evidence.service.list_evidence") as mock_list:
            mock_list.return_value = [mock_cap]
            result = runner.invoke(cli_app, [
                "evidence", "list",
                "--engagement", "1",
            ])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["tool"] == "tcpdump"

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_evidence_inspect(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_cap = MagicMock()
        mock_cap.id = 1
        mock_cap.engagement_id = 1
        mock_cap.job_id = None
        mock_cap.category = "original"
        mock_cap.path = "/tmp/test.pcapng"
        mock_cap.format = "pcapng"
        mock_cap.sha256 = "ab" * 32
        mock_cap.original_filename = None
        mock_cap.size_bytes = None
        mock_cap.interface = "wlan0"
        mock_cap.channel = 6
        mock_cap.bssid = "AA:BB:CC:DD:EE:FF"
        mock_cap.ssid = "TestNet"
        mock_cap.tool = "tcpdump"
        mock_cap.tool_version = "4.9"
        mock_cap.metadata = {}
        mock_cap.derived_from_id = None
        mock_cap.started_at = None
        mock_cap.finished_at = None
        mock_cap.created_at = "2026-07-29T10:00:00"

        with patch("aegiswifi.evidence.service.get_evidence") as mock_get:
            mock_get.return_value = mock_cap
            result = runner.invoke(cli_app, ["evidence", "inspect", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ssid"] == "TestNet"
        assert data["channel"] == 6

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_evidence_verify_valid(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_cap = MagicMock()
        mock_cap.id = 1
        mock_cap.path = "/tmp/valid.pcapng"
        mock_cap.sha256 = "abc123"

        with patch("aegiswifi.evidence.service.get_evidence") as mock_get:
            mock_get.return_value = mock_cap
            with patch("pathlib.Path.exists", return_value=True):
                with patch("aegiswifi.evidence.store.EvidenceStore.verify_integrity", return_value=True):
                    result = runner.invoke(cli_app, ["evidence", "verify", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_evidence_verify_file_not_found(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_session = MagicMock()
        mock_sm.return_value.return_value = mock_session

        mock_cap = MagicMock()
        mock_cap.id = 1
        mock_cap.path = "/tmp/missing.pcapng"
        mock_cap.sha256 = "abc123"

        with patch("aegiswifi.evidence.service.get_evidence") as mock_get:
            mock_get.return_value = mock_cap
            with patch("pathlib.Path.exists", return_value=False):
                result = runner.invoke(cli_app, ["evidence", "verify", "1"])
        assert result.exit_code == 1
        assert "no encontrado" in result.stdout


# ===================================================================
# CLI: Interface Commands (import perezoso + asyncio.run)
# ===================================================================


class TestInterfaceCommands:
    """Los comandos interface importan dentro del cuerpo y envuelven
    servicios async con ``asyncio.run()``. Parcheamos las funciones
    reales con ``AsyncMock``."""

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_list(self, mock_sm):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_iface = MagicMock()
        mock_iface.name = "wlan0"
        mock_iface.phy = "phy0"
        mock_iface.mac = "AA:BB:CC:DD:EE:FF"
        mock_iface.driver = "ath9k"
        mock_iface.type = "managed"
        mock_iface.state = "up"
        mock_iface.monitor_mode = False
        mock_iface.bands = ["2.4", "5"]

        with patch("aegiswifi.interfaces.service.list_all_interfaces") as mock_list:
            mock_list.return_value = [mock_iface]
            result = runner.invoke(cli_app, ["interface", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["name"] == "wlan0"
        assert data[0]["driver"] == "ath9k"

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_info_found(self, mock_sm):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_iface = MagicMock()
        mock_iface.model_dump_json.return_value = '{"name": "wlan0", "type": "managed"}'

        with patch("aegiswifi.interfaces.service.get_interface") as mock_get:
            mock_get.return_value = mock_iface
            result = runner.invoke(cli_app, ["interface", "info", "wlan0"])
        assert result.exit_code == 0
        assert "wlan0" in result.stdout

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_info_not_found(self, mock_sm):
        from unittest.mock import AsyncMock, patch

        with patch("aegiswifi.interfaces.service.get_interface") as mock_get:
            mock_get.return_value = None
            result = runner.invoke(cli_app, ["interface", "info", "invalid0"])
        assert result.exit_code == 1
        assert "no encontrada" in result.stdout

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_prepare(self, mock_sm):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"success": true, "monitor_mode": true}'

        with patch("aegiswifi.interfaces.service.prepare_interface") as mock_prep:
            mock_prep.return_value = mock_result
            result = runner.invoke(cli_app, ["interface", "prepare", "wlan0"])
        assert result.exit_code == 0
        assert "monitor_mode" in result.stdout

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_prepare_error(self, mock_sm):
        from unittest.mock import patch

        with patch("aegiswifi.interfaces.service.prepare_interface") as mock_prep:
            mock_prep.side_effect = RuntimeError("no interface")
            result = runner.invoke(cli_app, ["interface", "prepare", "wlan0"])
        assert result.exit_code == 1
        assert "no interface" in result.stdout

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_restore(self, mock_sm):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"restored": true}'

        with patch("aegiswifi.interfaces.service.restore_interface") as mock_rest:
            mock_rest.return_value = mock_result
            result = runner.invoke(cli_app, ["interface", "restore", "wlan0"])
        assert result.exit_code == 0

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_restore_failed(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"restored": false}'
        mock_result.restored = False  # atributo real, no MagicMock

        with patch("aegiswifi.interfaces.service.restore_interface") as mock_rest:
            mock_rest.return_value = mock_result
            result = runner.invoke(cli_app, ["interface", "restore", "wlan0"])
        assert result.exit_code == 1

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_diagnose(self, mock_sm):
        from unittest.mock import MagicMock, patch

        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"issues": []}'
        mock_result.issues = []  # lista real, no MagicMock

        with patch("aegiswifi.interfaces.service.diagnose_interface") as mock_diag:
            mock_diag.return_value = mock_result
            result = runner.invoke(cli_app, ["interface", "diagnose"])
        assert result.exit_code == 0

    @patch("aegiswifi.cli.get_sessionmaker")
    def test_interface_diagnose_with_issues(self, mock_sm):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_result = MagicMock()
        mock_result.model_dump_json.return_value = '{"issues": ["driver not found"]}'

        with patch("aegiswifi.interfaces.service.diagnose_interface") as mock_diag:
            mock_diag.return_value = mock_result
            result = runner.invoke(cli_app, ["interface", "diagnose", "wlan0"])
        assert result.exit_code == 1


# ===================================================================
# Main App Factory Tests
# ===================================================================


class TestCreateApp:
    """Tests de create_app() en main.py."""

    def test_create_app_dev_mode(self):
        from aegiswifi.main import create_app

        with patch("aegiswifi.main.get_settings") as mock_settings:
            mock_settings.return_value.is_dev = True
            mock_settings.return_value.cors_origins = ["http://localhost:5173"]
            app = create_app()
        assert app.title == "AegisWiFi"
        assert app.docs_url == "/docs"
        assert app.redoc_url is None

    def test_create_app_production_no_docs(self):
        from aegiswifi.main import create_app

        with patch("aegiswifi.main.get_settings") as mock_settings:
            mock_settings.return_value.is_dev = False
            mock_settings.return_value.cors_origins = []
            app = create_app()
        assert app.docs_url is None

    def test_create_app_has_cors_middleware(self):
        from aegiswifi.main import create_app

        with patch("aegiswifi.main.get_settings") as mock_settings:
            mock_settings.return_value.is_dev = True
            mock_settings.return_value.cors_origins = ["http://localhost:5173"]
            app = create_app()
        cors_middleware = [
            m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
        ]
        assert len(cors_middleware) == 1
        # Starlette Middleware expone kwargs (no options).
        assert cors_middleware[0].kwargs.get("allow_origins") == ["http://localhost:5173"]

    def test_create_app_includes_api_router(self):
        from aegiswifi.main import create_app

        with patch("aegiswifi.main.get_settings") as mock_settings:
            mock_settings.return_value.is_dev = True
            mock_settings.return_value.cors_origins = []
            app = create_app()
        # La API v1 se monta como _IncludedRouter con original_router.prefix.
        has_api_v1 = any(
            hasattr(r, "original_router") and r.original_router.prefix == "/api/v1"
            for r in app.routes
        )
        assert has_api_v1, "api_router no incluido en la app"

    def test_create_app_has_exception_handlers(self):
        from aegiswifi.main import create_app

        with patch("aegiswifi.main.get_settings") as mock_settings:
            mock_settings.return_value.is_dev = True
            mock_settings.return_value.cors_origins = []
            app = create_app()
        assert len(app.exception_handlers) > 0

    def test_app_module_level(self):
        """El módulo main.py exporta app = create_app()."""
        import aegiswifi.main as main_mod

        assert hasattr(main_mod, "app")
        assert main_mod.app.title == "AegisWiFi"


class TestLifespan:
    """Tests del ciclo de vida del app factory."""

    @pytest.mark.asyncio
    async def test_lifespan_starts_and_stops_job_manager(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_settings = MagicMock()
        mock_settings.log_level = "INFO"
        mock_settings.log_json = False
        mock_settings.jobs.event_buffer_size = 1000
        mock_settings.jobs.max_workers = 2
        mock_settings.jobs.heartbeat_interval = 15

        mock_manager = AsyncMock()
        mock_manager.start = AsyncMock()
        mock_manager.stop = AsyncMock()

        with (
            patch("aegiswifi.main.get_settings", return_value=mock_settings),
            patch("aegiswifi.main.JobManager", return_value=mock_manager) as mock_jm_cls,
        ):
            from aegiswifi.main import lifespan

            async with lifespan(MagicMock()) as _:
                mock_jm_cls.assert_called_once()
                mock_manager.start.assert_awaited_once()

        mock_manager.stop.assert_awaited_once()
