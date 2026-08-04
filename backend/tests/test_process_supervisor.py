"""Tests del ProcessSupervisor — subprocesos con EventBus (minuta §27).

Cubre:
  - Init: defaults, custom max_memory_lines.
  - Run: subprocess exit, log file, SHA-256, eventos, timeout, env, cwd,
         creación de directorio, límite de eventos en memoria.
  - GracefulShutdown: SIGTERM, SIGKILL en timeout, no-op sin proceso,
         no-op si ya terminó.
  - Cleanup: cierre de log, kill de proceso colgado.
  - EmitLogLine: publica JobEventEnvelope correcto al EventBus.

Todas las llamadas a asyncio.create_subprocess_exec se mockean.

Nota sobre mocks de subprocess: ``terminate()`` y ``kill()`` son métodos
síncronos en ``asyncio.subprocess.Process``, mientras que ``wait()`` es
async. Por eso usamos ``MagicMock`` con ``wait=AsyncMock()`` en vez de
``AsyncMock`` directo.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from aegiswifi.jobs.event_bus import EventBus, JobEventEnvelope
from aegiswifi.jobs.process_supervisor import ProcessSupervisor


# ===================================================================
# Init Tests
# ===================================================================


class TestInit:
    def test_init_defaults(self, tmp_path: Path):
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(
            job_id=1,
            engagement_id=2,
            log_dir=tmp_path / "logs",
            event_bus=bus,
        )
        assert sup._job_id == 1
        assert sup._engagement_id == 2
        assert sup._log_dir == tmp_path / "logs"
        assert sup._event_bus is bus
        assert sup._max_memory_lines == 10000
        assert sup._process is None
        assert sup._log_file is None
        assert sup._line_count == 0

    def test_init_custom_max_lines(self, tmp_path: Path):
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(
            job_id=1,
            engagement_id=2,
            log_dir=tmp_path,
            event_bus=bus,
            max_memory_lines=50,
        )
        assert sup._max_memory_lines == 50


# ===================================================================
# Helper: mock subprocess factory
# ===================================================================


def _mock_process(
    lines: list[bytes] | None = None,
    returncode: int = 0,
) -> MagicMock:
    """Crea un MagicMock que imita asyncio.subprocess.Process.

    ``terminate()`` y ``kill()`` son síncronos (no AsyncMock) para evitar
    el RuntimeWarning de corrutinas nunca await-eadas.
    ``wait()`` es AsyncMock (es async en el proceso real).
    """
    if lines is None:
        lines = []

    remaining = list(lines)

    async def readline() -> bytes:
        if remaining:
            return remaining.pop(0)
        return b""

    mock_stdout = MagicMock()
    mock_stdout.readline = readline

    process = MagicMock()
    process.stdout = mock_stdout
    process.returncode = returncode
    process.wait = AsyncMock(return_value=returncode)
    process.terminate = MagicMock()
    process.kill = MagicMock()
    return process


# ===================================================================
# Run Tests (async)
# ===================================================================


@pytest.mark.asyncio
class TestRun:
    """ProcessSupervisor.run() parameterized scenarios."""

    async def test_run_success(self, tmp_path: Path):
        """Ejecución exitosa: log file, SHA-256 y eventos."""
        bus = MagicMock(spec=EventBus)
        log_dir = tmp_path / "logs"
        sup = ProcessSupervisor(job_id=42, engagement_id=7, log_dir=log_dir, event_bus=bus)

        lines = [b"line1\n", b"line2\n", b"line3\n"]
        mock_process = _mock_process(lines.copy(), returncode=0)

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_process),
        ):
            result = await sup.run(["echo", "hello"])

        assert result["exit_code"] == 0
        assert result["line_count"] == 3
        assert "log_path" in result
        assert "sha256" in result

        # Verificar archivo de log en disco.
        log_path = Path(result["log_path"])
        assert log_path.read_text(encoding="utf-8") == "line1\nline2\nline3\n"

        # Verificar SHA-256.
        expected_sha = hashlib.sha256()
        for line_bytes in [b"line1\n", b"line2\n", b"line3\n"]:
            expected_sha.update(line_bytes)
        assert result["sha256"] == expected_sha.hexdigest()

        # Verificar eventos emitidos (3 líneas ≤ max_memory_lines=10000).
        assert bus.publish.call_count == 3

    async def test_run_nowrite_log(self, tmp_path: Path):
        """Corrobora que el path del log está dentro de log_dir."""
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(job_id=99, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = _mock_process([b"data\n"], returncode=0)

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_process),
        ):
            result = await sup.run(["cmd"])

        log_path = Path(result["log_path"])
        assert result["log_path"] == str(tmp_path / "job_99.log")
        assert log_path.parent == tmp_path

    async def test_run_timeout_triggers_shutdown(self, tmp_path: Path):
        """Timeout lanza TimeoutError y llama graceful_shutdown."""
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        async def never_ending_readline() -> bytes:
            await asyncio.sleep(3600)
            return b""

        mock_stdout = MagicMock()
        mock_stdout.readline = never_ending_readline

        mock_process = MagicMock()
        mock_process.stdout = mock_stdout
        wait_calls = 0

        async def wait_until_killed() -> int:
            nonlocal wait_calls
            wait_calls += 1
            if wait_calls == 1:
                await asyncio.sleep(3600)
            if wait_calls == 2:
                raise TimeoutError
            return 0

        mock_process.wait = AsyncMock(side_effect=wait_until_killed)
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_process),
        ):
            with pytest.raises(TimeoutError):
                await sup.run(["sleep", "100"], timeout_sec=0.05)

        # graceful_shutdown debe haber terminado el proceso.
        mock_process.terminate.assert_called_once()

    async def test_run_custom_env_cwd(self, tmp_path: Path):
        """Verifica que env y cwd se pasen a create_subprocess_exec."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = _mock_process(returncode=0)

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_process),
        ) as mock_spawn:
            await sup.run(
                ["cmd"],
                cwd=tmp_path,
                env={"CUSTOM": "value"},
            )

        mock_spawn.assert_called_once_with(
            "cmd",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=tmp_path,
            env={"CUSTOM": "value"},
        )

    async def test_run_creates_log_dir(self, tmp_path: Path):
        """El directorio de logs se crea si no existe."""
        bus = MagicMock()
        log_dir = tmp_path / "nonexistent" / "deep" / "logs"
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=log_dir, event_bus=bus)

        mock_process = _mock_process(returncode=0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await sup.run(["cmd"])

        assert log_dir.is_dir(), "log_dir debería haber sido creado"
        assert Path(result["log_path"]).exists()

    async def test_run_exceeds_memory_lines(self, tmp_path: Path):
        """Al superar max_memory_lines deja de emitir eventos."""
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(
            job_id=1,
            engagement_id=1,
            log_dir=tmp_path,
            event_bus=bus,
            max_memory_lines=2,
        )

        lines = [b"1\n", b"2\n", b"3\n"]  # 3 líneas, max_memory=2
        mock_process = _mock_process(lines.copy(), returncode=0)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=mock_process)):
            result = await sup.run(["cmd"])

        assert result["line_count"] == 3
        # Solo 2 eventos emitidos (líneas 1 y 2).
        assert bus.publish.call_count == 2


# ===================================================================
# GracefulShutdown Tests (async)
# ===================================================================


@pytest.mark.asyncio
class TestGracefulShutdown:
    async def _make_mock_process(self) -> MagicMock:
        proc = MagicMock()
        proc.returncode = None
        proc.wait = AsyncMock(return_value=0)
        proc.terminate = MagicMock()
        proc.kill = MagicMock()
        return proc

    async def test_shutdown_terminates_and_waits(self, tmp_path: Path):
        """graceful_shutdown envía SIGTERM y espera."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = await self._make_mock_process()
        sup._process = mock_process

        await sup.graceful_shutdown()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()

    async def test_shutdown_kills_on_timeout(self, tmp_path: Path):
        """Si SIGTERM no basta, pasa a SIGKILL."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = await self._make_mock_process()
        sup._process = mock_process

        mock_process.wait = AsyncMock(side_effect=[TimeoutError(), 0])
        await sup.graceful_shutdown()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()

    async def test_shutdown_no_process(self, tmp_path: Path):
        """Sin proceso activo, graceful_shutdown es no-op."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)
        # _process is None — no debe lanzar.
        await sup.graceful_shutdown()

    async def test_shutdown_already_exited(self, tmp_path: Path):
        """Si el proceso ya terminó, graceful_shutdown es no-op."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = await self._make_mock_process()
        mock_process.returncode = 0  # ya terminó
        sup._process = mock_process

        await sup.graceful_shutdown()
        mock_process.terminate.assert_not_called()


# ===================================================================
# Cleanup Tests
# ===================================================================


class TestCleanup:
    def test_cleanup_closes_log(self, tmp_path: Path):
        """cleanup cierra el archivo de log si está abierto."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        log_path = tmp_path / "test.log"
        sup._log_file = log_path.open("w")

        sup.cleanup()
        assert sup._log_file.closed

    def test_cleanup_kills_running_process(self, tmp_path: Path):
        """cleanup mata el proceso si sigue corriendo."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)

        mock_process = MagicMock()
        mock_process.returncode = None  # still running
        sup._process = mock_process

        sup.cleanup()
        mock_process.kill.assert_called_once()

    def test_cleanup_no_log_or_process(self, tmp_path: Path):
        """cleanup sin log ni proceso no debe lanzar."""
        bus = MagicMock()
        sup = ProcessSupervisor(job_id=1, engagement_id=1, log_dir=tmp_path, event_bus=bus)
        sup.cleanup()  # no-op


# ===================================================================
# EmitLogLine Tests
# ===================================================================


class TestEmitLogLine:
    def test_emit_log_line_publishes_envelope(self, tmp_path: Path):
        """_emit_log_line publica un JobEventEnvelope correcto."""
        bus = MagicMock(spec=EventBus)
        sup = ProcessSupervisor(job_id=5, engagement_id=10, log_dir=tmp_path, event_bus=bus)
        sup._line_count = 3

        sup._emit_log_line("test output")

        bus.publish.assert_called_once()
        envelope = bus.publish.call_args[0][0]
        assert isinstance(envelope, JobEventEnvelope)
        assert envelope.event_type == "job_log_line"
        assert envelope.job_id == 5
        assert envelope.engagement_id == 10
        assert envelope.data["line"] == "test output"
        assert envelope.data["line_number"] == 3
