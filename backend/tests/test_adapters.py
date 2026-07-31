"""Tests del sistema de adaptadores (Fase 2, minuta §27).

Cubre:
  - ToolAdapterRegistry: registro, consulta, error en kind desconocido.
  - PassiveCaptureAdapter: build_command, parse_output.
  - HandshakeCaptureAdapter: build_command, parse_output.
  - PMKIDCaptureAdapter: build_command, parse_output.
  - HcxPcapngToolAdapter: build_command, parse_output.
  - Excepciones de adaptadores.
"""

from __future__ import annotations

import tempfile

import pytest

from aegiswifi.adapters.errors import AdapterError, ToolNotInstalled
from aegiswifi.adapters.registry import get_adapter, list_adapters

_TMP = tempfile.gettempdir()

# ===================================================================
# ToolAdapterRegistry Tests
# ===================================================================


class TestToolAdapterRegistry:
    def test_register_and_get(self):
        """Registrar y recuperar un adaptador."""
        adapter = get_adapter(
            "passive_capture",
            job_id=1,
            engagement_id=1,
            event_bus=None,  # type: ignore[arg-type]
            config=None,  # type: ignore[arg-type]
        )
        assert adapter is not None
        assert adapter.tool_name == "tcpdump"

    def test_get_handshake_adapter(self):
        adapter = get_adapter(
            "handshake_capture",
            job_id=1,
            engagement_id=1,
            event_bus=None,  # type: ignore[arg-type]
            config=None,  # type: ignore[arg-type]
        )
        assert adapter.tool_name == "airodump-ng"

    def test_get_pmkid_adapter(self):
        adapter = get_adapter(
            "pmkid_capture",
            job_id=1,
            engagement_id=1,
            event_bus=None,  # type: ignore[arg-type]
            config=None,  # type: ignore[arg-type]
        )
        assert adapter.tool_name == "hcxdumptool"

    def test_get_hash_convert_adapter(self):
        adapter = get_adapter(
            "hash_convert",
            job_id=1,
            engagement_id=1,
            event_bus=None,  # type: ignore[arg-type]
            config=None,  # type: ignore[arg-type]
        )
        assert adapter.tool_name == "hcxpcapngtool"

    def test_unknown_kind_raises_valueerror(self):
        with pytest.raises(ValueError, match="no adapter registered"):
            get_adapter("nonexistent_tool")

    def test_list_adapters_includes_all(self):
        all_a = list_adapters()
        assert "passive_capture" in all_a
        assert "handshake_capture" in all_a
        assert "pmkid_capture" in all_a
        assert "hash_convert" in all_a


# ===================================================================
# Adapter helpers — optionally accept None event_bus/config for testing
# ===================================================================


def _adapter(kind: str, **kw: object):
    """Shortcut para crear un adaptador en tests."""
    return get_adapter(
        kind,
        job_id=42,
        engagement_id=1,
        event_bus=None,  # type: ignore[arg-type]
        config=None,  # type: ignore[arg-type]
        **kw,
    )


# ===================================================================
# PassiveCaptureAdapter Tests
# ===================================================================


class TestPassiveCaptureAdapter:
    @pytest.mark.asyncio
    async def test_build_command_structure(self):
        adapter = _adapter("passive_capture")
        output = f"{_TMP}/test.pcapng"
        cmd = await adapter.build_command({"interface": "wlan0mon", "output": output})
        assert cmd[0] == "tcpdump"
        assert "-i" in cmd
        assert "wlan0mon" in cmd
        assert "-w" in cmd
        assert output in cmd
        assert "22" in cmd  # not port 22

    @pytest.mark.asyncio
    async def test_build_command_default_output(self):
        adapter = _adapter("passive_capture")
        cmd = await adapter.build_command({"interface": "wlan0mon"})
        idx = cmd.index("-w") + 1
        assert idx < len(cmd)
        assert "passive_" in cmd[idx]

    @pytest.mark.asyncio
    async def test_parse_output_packets_captured(self):
        adapter = _adapter("passive_capture")
        result = await adapter.parse_output("10 packets captured")
        assert result is not None
        assert "packets_captured" in result

    @pytest.mark.asyncio
    async def test_parse_output_ignores_noise(self):
        adapter = _adapter("passive_capture")
        result = await adapter.parse_output("listening on wlan0mon")
        assert result is None


# ===================================================================
# HandshakeCaptureAdapter Tests
# ===================================================================


class TestHandshakeCaptureAdapter:
    @pytest.mark.asyncio
    async def test_build_command_structure(self):
        adapter = _adapter("handshake_capture")
        cmd = await adapter.build_command({"interface": "wlan0mon", "bssid": "AA:BB:CC:DD:EE:FF"})
        assert cmd[0] == "airodump-ng"
        assert "-i" in cmd
        assert "--bssid" in cmd
        assert "AA:BB:CC:DD:EE:FF" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_channel(self):
        adapter = _adapter("handshake_capture")
        cmd = await adapter.build_command(
            {"interface": "wlan0mon", "bssid": "AA:BB:CC:DD:EE:FF", "channel": 6}
        )
        assert "-c" in cmd
        assert "6" in cmd

    @pytest.mark.asyncio
    async def test_build_command_without_channel(self):
        adapter = _adapter("handshake_capture")
        cmd = await adapter.build_command({"interface": "wlan0mon", "bssid": "AA:BB:CC:DD:EE:FF"})
        assert "-c" not in cmd

    @pytest.mark.asyncio
    async def test_parse_output_handshake_detected(self):
        adapter = _adapter("handshake_capture")
        result = await adapter.parse_output("WPA handshake: AA:BB:CC:DD:EE:FF")
        assert result is not None
        assert result["handshake_detected"] is True

    @pytest.mark.asyncio
    async def test_parse_output_ignores_noise(self):
        adapter = _adapter("handshake_capture")
        result = await adapter.parse_output("BSSID              PWR  Beacons")
        assert result is None


# ===================================================================
# PMKIDCaptureAdapter Tests
# ===================================================================


class TestPMKIDCaptureAdapter:
    @pytest.mark.asyncio
    async def test_build_command_structure(self):
        adapter = _adapter("pmkid_capture")
        cmd = await adapter.build_command({"interface": "wlan0mon"})
        assert cmd[0] == "hcxdumptool"
        assert "-i" in cmd
        assert "-o" in cmd
        assert "--enable_status=1" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_channel(self):
        adapter = _adapter("pmkid_capture")
        cmd = await adapter.build_command({"interface": "wlan0mon", "channel": 6})
        assert "-c" in cmd
        assert "6" in cmd

    @pytest.mark.asyncio
    async def test_parse_output_pmkid_found(self):
        adapter = _adapter("pmkid_capture")
        result = await adapter.parse_output("PMKID found from AA:BB:CC:DD:EE:FF")
        assert result is not None
        assert result["pmkid_event"] is True

    @pytest.mark.asyncio
    async def test_parse_output_found_keyword(self):
        adapter = _adapter("pmkid_capture")
        result = await adapter.parse_output("FOUND PMKID EAPOL ...")
        assert result is not None
        assert result["pmkid_event"] is True


# ===================================================================
# HcxPcapngToolAdapter Tests
# ===================================================================


class TestHcxPcapngToolAdapter:
    @pytest.mark.asyncio
    async def test_build_command_structure(self):
        adapter = _adapter("hash_convert")
        input_path = f"{_TMP}/capture.pcapng"
        cmd = await adapter.build_command({"input": input_path})
        assert cmd[0] == "hcxpcapngtool"
        assert "-o" in cmd
        assert input_path in cmd  # input file

    @pytest.mark.asyncio
    async def test_parse_output_written(self):
        adapter = _adapter("hash_convert")
        result = await adapter.parse_output("Written 42 hashes to file")
        assert result is not None
        assert result["write_event"] is True

    @pytest.mark.asyncio
    async def test_parse_output_pmkid_detected(self):
        adapter = _adapter("hash_convert")
        result = await adapter.parse_output("pmkid detected")
        assert result is not None
        assert result["pmkid_detected"] is True

    @pytest.mark.asyncio
    async def test_parse_output_handshake_detected(self):
        adapter = _adapter("hash_convert")
        result = await adapter.parse_output("handshake from AA:BB:CC:DD:EE:FF")
        assert result is not None
        assert result["handshake_detected"] is True

    @pytest.mark.asyncio
    async def test_parse_output_ignores_noise(self):
        adapter = _adapter("hash_convert")
        result = await adapter.parse_output("hcxpcapngtool 4.2 starting")
        assert result is None


# ===================================================================
# Error Classes Tests
# ===================================================================


class TestAdapterErrorClasses:
    def test_adapter_error_base(self):
        assert issubclass(ToolNotInstalled, AdapterError)
        err = AdapterError("generic error")
        assert "generic error" in str(err)

    def test_tool_not_installed_message(self):
        err = ToolNotInstalled("tcpdump not found")
        assert "tcpdump not found" in str(err)
