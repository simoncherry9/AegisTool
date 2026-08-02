"""Tests del módulo de interfaces (Fase 3, minuta §13 + §37).

Cubre:
  - Schemas: serialización, defaults, validación.
  - Detection: parsers, list_interfaces, chipset, driver, rfkill, airmon.
  - Monitor: enable/disable, virtual, injection test, capabilities.
  - Restoration: save/load/delete state, capture, restore.
  - Service: prepare, restore, diagnose, orchestrations.
  - API: endpoints REST.

Todas las llamadas a herramientas externas (iw, ethtool, etc.) se mockean
con :func:`unittest.mock.patch` para no depender del sistema operativo.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from aegiswifi.interfaces.schemas import (
    InterfaceDiagnostic,
    InterfacePrepareResult,
    InterfaceRestoreResult,
    InterfaceState,
    WirelessInterface,
)

_TMP = Path(__file__).parent / "_test_interface_states"


# ===================================================================
# Schemas Tests
# ===================================================================


class TestSchemas:
    def test_wireless_interface_defaults(self):
        """WirelessInterface con solo name, el resto defaults."""
        w = WirelessInterface(name="wlan0")
        assert w.name == "wlan0"
        assert w.phy is None
        assert w.type == "managed"
        assert w.state == "down"
        assert w.bands == []
        assert w.monitor_mode is False

    def test_wireless_interface_monitor(self):
        w = WirelessInterface(name="wlan0mon", type="monitor", monitor_mode=True)
        assert w.type == "monitor"
        assert w.monitor_mode is True

    def test_wireless_interface_full(self):
        w = WirelessInterface(
            name="wlan0",
            phy="phy0",
            mac="00:11:22:33:44:55",
            chipset="MT7612U",
            driver="mt76x2u",
            bands=["2.4 GHz", "5 GHz"],
            channels=[1, 6, 11],
            supported_modes=["managed", "monitor", "AP"],
            type="managed",
            state="up",
            monitor_mode=False,
            ap_mode=False,
        )
        assert w.mac == "00:11:22:33:44:55"
        assert w.channels == [1, 6, 11]
        assert "AP" in w.supported_modes

    def test_interface_state_defaults(self):
        s = InterfaceState(interface="wlan0", original_type="managed", was_up=True)
        assert s.interface == "wlan0"
        assert s.original_type == "managed"
        assert s.was_up is True
        assert s.original_channel is None

    def test_interface_state_serialization(self):
        s = InterfaceState(
            interface="wlan0",
            original_type="monitor",
            original_channel=6,
            was_up=True,
        )
        data = s.model_dump()
        loaded = InterfaceState.model_validate(data)
        assert loaded.interface == "wlan0"
        assert loaded.original_channel == 6

    def test_prepare_result(self):
        state = InterfaceState(interface="wlan0", original_type="managed", was_up=True)
        r = InterfacePrepareResult(
            interface="wlan0",
            monitor_interface="wlan0",
            mode_set=True,
            injection_ok=True,
            original_state=state,
        )
        assert r.mode_set is True
        assert r.injection_ok is True
        assert r.monitor_interface == "wlan0"

    def test_restore_result(self):
        r = InterfaceRestoreResult(interface="wlan0", restored=True, current_type="managed")
        assert r.restored is True
        assert r.current_type == "managed"

    def test_diagnostic_defaults(self):
        d = InterfaceDiagnostic()
        assert d.present is False
        assert d.blocked is False
        assert d.issues == []

    def test_diagnostic_full(self):
        d = InterfaceDiagnostic(
            interface="wlan0",
            present=True,
            blocked=True,
            conflicting_processes=["NetworkManager"],
            rfkill_blocks=[{"id": 0, "type": "wlan", "soft": True, "hard": False}],
            issues=["rfkill bloquea interfaz"],
        )
        assert len(d.conflicting_processes) == 1
        assert len(d.issues) == 1

    def test_invalid_name_empty(self):
        """name vacío es aceptado (no hay validación extra sobre str)."""
        w = WirelessInterface(name="")
        assert w.name == ""


# ===================================================================
# Detection Parser Tests
# ===================================================================


class TestDetectionParsers:
    """Tests de los parsers de salida de herramientas."""

    def test_parse_iw_dev_output(self):
        """Parsea la salida típica de ``iw dev``."""
        from aegiswifi.interfaces.detection import _parse_iw_dev_output

        output = """phy#0
\tInterface wlan0
\t\tifindex 3
\t\twdev 0x1
\t\taddr 00:11:22:33:44:55
\t\ttype managed
phy#1
\tInterface wlan1
\t\tifindex 4
\t\twdev 0x2
\t\taddr AA:BB:CC:DD:EE:FF
\t\ttype monitor
"""
        parsed = _parse_iw_dev_output(output)
        assert len(parsed) == 2
        assert parsed[0]["iface"] == "wlan0"
        assert parsed[0]["addr"] == "00:11:22:33:44:55"
        assert parsed[0]["type"] == "managed"
        assert parsed[1]["iface"] == "wlan1"
        assert parsed[1]["type"] == "monitor"

    def test_parse_iw_dev_empty(self):
        from aegiswifi.interfaces.detection import _parse_iw_dev_output

        assert _parse_iw_dev_output("") == []

    def test_parse_iw_dev_no_interfaces(self):
        from aegiswifi.interfaces.detection import _parse_iw_dev_output

        parsed = _parse_iw_dev_output("phy#0\n\ttype managed\n")
        assert parsed == []

    def test_parse_iw_phy_info_bands_and_modes(self):
        from aegiswifi.interfaces.detection import _parse_iw_phy_info

        output = """Wiphy phy0
\tmax # scan SSIDs: 10
\tSupported interface modes:
\t\t * managed
\t\t * monitor
\t\t * AP
\tBand 1:
\t\tCapabilities: 0x0000
\t\tFrequencies:
\t\t\t* 2412 MHz [1] (20.0 dBm)
\t\t\t* 2437 MHz [6] (20.0 dBm)
\t\t\t* 2462 MHz [11] (20.0 dBm)
\tBand 2:
\t\tFrequencies:
\t\t\t* 5180 MHz [36] (20.0 dBm)
\t\t\t* 5200 MHz [40] (20.0 dBm)
"""
        parsed = _parse_iw_phy_info(output)
        assert "2.4 GHz" in parsed["bands"] or any("1" in b for b in parsed["bands"])
        assert parsed["channels"] == [1, 6, 11, 36, 40]
        assert "monitor" in parsed["supported_modes"]
        assert "managed" in parsed["supported_modes"]
        assert "AP" in parsed["supported_modes"]

    def test_parse_iw_phy_info_no_output(self):
        from aegiswifi.interfaces.detection import _parse_iw_phy_info

        parsed = _parse_iw_phy_info("")
        assert parsed["bands"] == []
        assert parsed["channels"] == []

    def test_parse_iw_phy_info_only_modes(self):
        from aegiswifi.interfaces.detection import _parse_iw_phy_info

        output = "Supported interface modes:\n\t * managed\n\t * monitor\n"
        parsed = _parse_iw_phy_info(output)
        assert "managed" in parsed["supported_modes"]
        assert parsed["bands"] == []

    def test_parse_ethtool_output(self):
        from aegiswifi.interfaces.detection import _parse_ethtool_output

        output = """driver: mt76x2u
version: 5.15.0
firmware-version: 0.1.0
"""
        parsed = _parse_ethtool_output(output)
        assert parsed["driver"] == "mt76x2u"
        assert parsed["version"] == "5.15.0"
        assert parsed["firmware-version"] == "0.1.0"

    def test_parse_rfkill_output(self):
        from aegiswifi.interfaces.detection import _parse_rfkill_output

        output = """0: phy0: Wireless LAN
\tSoft blocked: yes
\tHard blocked: no
1: hci0: Bluetooth
\tSoft blocked: no
\tHard blocked: no
"""
        parsed = _parse_rfkill_output(output)
        assert len(parsed) == 2
        assert parsed[0]["id"] == 0
        assert parsed[0]["soft"] is True
        assert parsed[0]["hard"] is False


# ===================================================================
# Detection Module Tests
# ===================================================================


class TestDetectionModule:
    @pytest.mark.asyncio
    async def test_list_interfaces_with_output(self):
        """list_interfaces con iw dev mockeado."""
        mock_iw_output = """phy#0
\tInterface wlan0
\t\taddr 00:11:22:33:44:55
\t\ttype managed
"""
        with (
            patch("aegiswifi.interfaces.detection._run_iw", new_callable=AsyncMock) as mock_iw,
            patch(
                "aegiswifi.interfaces.detection.get_phy_info", new_callable=AsyncMock
            ) as mock_phy,
            patch(
                "aegiswifi.interfaces.detection.detect_driver", new_callable=AsyncMock
            ) as mock_drv,
            patch(
                "aegiswifi.interfaces.detection.detect_chipset", new_callable=AsyncMock
            ) as mock_chip,
        ):
            mock_iw.return_value = (mock_iw_output, "")
            mock_phy.return_value = {
                "bands": ["2.4 GHz"],
                "channels": [1, 6, 11],
                "supported_modes": ["managed", "monitor"],
            }
            mock_drv.return_value = ("mt76x2u", "5.15.0")
            mock_chip.return_value = "MediaTek MT7612U"

            from aegiswifi.interfaces.detection import list_interfaces

            ifaces = await list_interfaces()

        assert len(ifaces) == 1
        assert ifaces[0].name == "wlan0"
        assert ifaces[0].mac == "00:11:22:33:44:55"
        assert ifaces[0].type == "managed"
        assert ifaces[0].driver == "mt76x2u"
        assert ifaces[0].chipset == "MediaTek MT7612U"

    @pytest.mark.asyncio
    async def test_list_interfaces_no_tool(self):
        """list_interfaces cuando iw no está instalado."""
        with patch("aegiswifi.interfaces.detection._run_iw", new_callable=AsyncMock) as mock_iw:
            mock_iw.return_value = ("", "iw: command not found")

            from aegiswifi.interfaces.detection import list_interfaces

            ifaces = await list_interfaces()
        assert ifaces == []

    @pytest.mark.asyncio
    async def test_get_interface_details_found(self):
        """get_interface_details encuentra por nombre."""
        with patch(
            "aegiswifi.interfaces.detection.list_interfaces", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [
                WirelessInterface(name="wlan0", type="managed"),
                WirelessInterface(name="wlan1", type="monitor"),
            ]

            from aegiswifi.interfaces.detection import get_interface_details

            iface = await get_interface_details("wlan0")
        assert iface is not None
        assert iface.name == "wlan0"

    @pytest.mark.asyncio
    async def test_get_interface_details_not_found(self):
        with patch(
            "aegiswifi.interfaces.detection.list_interfaces", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [WirelessInterface(name="wlan0", type="managed")]

            from aegiswifi.interfaces.detection import get_interface_details

            iface = await get_interface_details("nonexistent")
        assert iface is None

    @pytest.mark.asyncio
    async def test_detect_driver_ethtool(self):
        """detect_driver con ethtool exitoso."""
        from aegiswifi.interfaces.detection import detect_driver

        with patch(
            "aegiswifi.interfaces.detection._run_ethtool", new_callable=AsyncMock
        ) as mock_ethtool:
            mock_ethtool.return_value = ("driver: iwlwifi\nversion: 5.15.0\n", "")
            driver, version = await detect_driver("wlan0")

        assert driver == "iwlwifi"
        assert version == "5.15.0"

    @pytest.mark.asyncio
    async def test_detect_driver_not_found(self):
        from aegiswifi.interfaces.detection import detect_driver

        with patch(
            "aegiswifi.interfaces.detection._run_ethtool", new_callable=AsyncMock
        ) as mock_ethtool:
            mock_ethtool.return_value = ("", "ethtool: command not found")
            driver, version = await detect_driver("wlan0")

        assert driver is None
        assert version is None

    @pytest.mark.asyncio
    async def test_detect_chipset_via_modalias(self):
        from aegiswifi.interfaces.detection import detect_chipset

        mock_modalias = "usb:v1234p5678d0000dc00dsc00dp00icFFiscFFipFF00"
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value=mock_modalias),
        ):
            chipset = await detect_chipset("phy0")
        assert chipset is not None

    @pytest.mark.asyncio
    async def test_detect_chipset_not_found(self):
        from aegiswifi.interfaces.detection import detect_chipset

        with patch("pathlib.Path.exists", return_value=False):
            chipset = await detect_chipset("phy0")
        assert chipset is None

    @pytest.mark.asyncio
    async def test_detect_conflicting_processes(self):
        from aegiswifi.interfaces.detection import detect_conflicting_processes

        mock_output = """Found 2 processes that could cause trouble.
\tPID\tName
\t1234\tNetworkManager
\t5678\tnm-applet
"""
        with patch(
            "aegiswifi.interfaces.detection._run_airmon", new_callable=AsyncMock
        ) as mock_airmon:
            mock_airmon.return_value = (mock_output, "")
            procs = await detect_conflicting_processes()

        assert "NetworkManager" in procs

    @pytest.mark.asyncio
    async def test_detect_conflicting_processes_no_tool(self):
        from aegiswifi.interfaces.detection import detect_conflicting_processes

        with patch(
            "aegiswifi.interfaces.detection._run_airmon", new_callable=AsyncMock
        ) as mock_airmon:
            mock_airmon.return_value = ("", "airmon-ng: command not found")
            procs = await detect_conflicting_processes()

        assert procs == []

    @pytest.mark.asyncio
    async def test_check_rfkill(self):
        from aegiswifi.interfaces.detection import check_rfkill

        mock_output = "0: phy0: Wireless LAN\n\tSoft blocked: yes\n\tHard blocked: no\n"
        with patch(
            "aegiswifi.interfaces.detection._run_rfkill", new_callable=AsyncMock
        ) as mock_rfkill:
            mock_rfkill.return_value = (mock_output, "")
            blocks = await check_rfkill()

        assert len(blocks) == 1
        assert blocks[0]["soft"] is True


# ===================================================================
# Monitor Module Tests
# ===================================================================


class TestMonitorModule:
    @pytest.mark.asyncio
    async def test_enable_monitor_mode_direct(self):
        """enable_monitor_mode: cambio directo exitoso."""
        from aegiswifi.interfaces.monitor import enable_monitor_mode

        # iw dev output: first call → managed (initial check), second call → monitor (post-set verification)
        iw_dev_managed = "phy#0\n\tInterface wlan0\n\t\tifindex 3\n\t\ttype managed\n"
        iw_dev_monitor = "phy#0\n\tInterface wlan0\n\t\tifindex 3\n\t\ttype monitor\n"

        mock_iw = AsyncMock(side_effect=[
            (iw_dev_managed, ""),  # initial check: not in monitor
            (iw_dev_monitor, ""),  # post-set verification: now in monitor
        ])

        with (
            patch("aegiswifi.interfaces.monitor._run_airmon", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_ip", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw", mock_iw),
            patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock, return_value=("", "")),
        ):
            result = await enable_monitor_mode("wlan0")

        assert result == "wlan0"

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_virtual_fallback(self):
        """enable_monitor_mode: fallback a virtual si directo falla."""
        from aegiswifi.interfaces.monitor import enable_monitor_mode

        with (
            patch("aegiswifi.interfaces.monitor._run_airmon", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_ip", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut,
        ):
            # 1: set type monitor (fails)
            # 2: set monitor control (fails)
            # 3: interface add (succeeds)
            mock_iw_mut.side_effect = [
                ("", "command failed: Device or resource busy"),
                ("", "command failed: Device or resource busy"),
                ("", ""),
            ]
            result = await enable_monitor_mode("wlan0")

        assert result == "wlan0mon"

    @pytest.mark.asyncio
    async def test_enable_monitor_mode_both_fail(self):
        """enable_monitor_mode: lanza RuntimeError si ambos métodos fallan."""
        from aegiswifi.interfaces.monitor import enable_monitor_mode

        with (
            patch("aegiswifi.interfaces.monitor._run_airmon", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_ip", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut,
        ):
            mock_iw_mut.side_effect = [
                ("", "command failed: Device or resource busy"),
                ("", "command failed: Device or resource busy"),
                ("", "command failed: Operation not supported"),
            ]
            with pytest.raises(RuntimeError, match="no se pudo activar monitor mode"):
                await enable_monitor_mode("wlan0")

    @pytest.mark.asyncio
    async def test_disable_monitor_mode(self):
        from aegiswifi.interfaces.monitor import disable_monitor_mode

        with (
            patch("aegiswifi.interfaces.monitor._run_airmon", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_ip", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock, return_value=("", "")),
        ):
            await disable_monitor_mode("wlan0")

    @pytest.mark.asyncio
    async def test_disable_monitor_mode_fail(self):
        from aegiswifi.interfaces.monitor import disable_monitor_mode

        with (
            patch("aegiswifi.interfaces.monitor._run_airmon", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_ip", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw", new_callable=AsyncMock, return_value=("", "")),
            patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut,
        ):
            mock_iw_mut.return_value = ("", "command failed: Operation not permitted")
            with pytest.raises(RuntimeError, match="no se pudo desactivar monitor mode"):
                await disable_monitor_mode("wlan0")

    @pytest.mark.asyncio
    async def test_create_virtual_monitor(self):
        from aegiswifi.interfaces.monitor import create_virtual_monitor

        with patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut:
            mock_iw_mut.return_value = ("", "")
            result = await create_virtual_monitor("wlan0")
            assert result == "wlan0mon"

        assert result == "wlan0mon"

    @pytest.mark.asyncio
    async def test_create_virtual_monitor_custom_name(self):
        from aegiswifi.interfaces.monitor import create_virtual_monitor

        with patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut:
            mock_iw_mut.return_value = ("", "")
            result = await create_virtual_monitor("wlan0", name="mon0")

        assert result == "mon0"

    @pytest.mark.asyncio
    async def test_remove_virtual_interface(self):
        from aegiswifi.interfaces.monitor import remove_virtual_interface

        with patch("aegiswifi.interfaces.monitor._run_iw_mutating", new_callable=AsyncMock) as mock_iw_mut:
            mock_iw_mut.return_value = ("", "")
            await remove_virtual_interface("wlan0mon")

        mock_iw_mut.assert_called_once_with(["dev", "wlan0mon", "del"])

    @pytest.mark.asyncio
    async def test_test_injection_working(self):
        from aegiswifi.interfaces.monitor import test_injection

        with patch(
            "aegiswifi.interfaces.monitor._run_aireplay", new_callable=AsyncMock
        ) as mock_air:
            mock_air.return_value = ("Injection is working\n", "")
            result = await test_injection("wlan0mon")

        assert result is True

    @pytest.mark.asyncio
    async def test_test_injection_failed(self):
        from aegiswifi.interfaces.monitor import test_injection

        with patch(
            "aegiswifi.interfaces.monitor._run_aireplay", new_callable=AsyncMock
        ) as mock_air:
            mock_air.return_value = ("No Answer\n", "")
            result = await test_injection("wlan0mon")

        assert result is False

    @pytest.mark.asyncio
    async def test_test_injection_not_available(self):
        from aegiswifi.interfaces.monitor import test_injection

        with patch(
            "aegiswifi.interfaces.monitor._run_aireplay", new_callable=AsyncMock
        ) as mock_air:
            mock_air.return_value = ("", "aireplay-ng: command not found")
            result = await test_injection("wlan0mon")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_monitor_support(self):
        from aegiswifi.interfaces.monitor import check_monitor_support

        with patch("aegiswifi.interfaces.monitor.get_phy_info", new_callable=AsyncMock) as mock_phy:
            mock_phy.return_value = {
                "bands": ["2.4 GHz"],
                "channels": [1, 6, 11],
                "supported_modes": ["managed", "monitor", "AP"],
            }
            result = await check_monitor_support("phy0")

        assert result is True

    @pytest.mark.asyncio
    async def test_check_monitor_support_not_supported(self):
        from aegiswifi.interfaces.monitor import check_monitor_support

        with patch("aegiswifi.interfaces.monitor.get_phy_info", new_callable=AsyncMock) as mock_phy:
            mock_phy.return_value = {
                "bands": [],
                "channels": [],
                "supported_modes": ["managed"],
            }
            result = await check_monitor_support("phy0")

        assert result is False


# ===================================================================
# Restoration Module Tests
# ===================================================================


class TestRestorationModule:
    def test_save_and_load_state(self, tmp_path: Path):
        from aegiswifi.interfaces.restoration import (
            delete_interface_state,
            load_interface_state,
            save_interface_state,
        )

        state = InterfaceState(
            interface="wlan0",
            original_type="managed",
            original_channel=6,
            was_up=True,
        )

        # Patch _STATE_DIR to use tmp_path
        with patch("aegiswifi.interfaces.restoration._STATE_DIR", tmp_path / "iface_states"):
            save_interface_state(state)
            loaded = load_interface_state("wlan0")

        assert loaded is not None
        assert loaded.interface == "wlan0"
        assert loaded.original_type == "managed"
        assert loaded.original_channel == 6
        assert loaded.was_up is True

        # cleanup
        with patch("aegiswifi.interfaces.restoration._STATE_DIR", tmp_path / "iface_states"):
            delete_interface_state("wlan0")
            assert load_interface_state("wlan0") is None

    def test_load_state_not_found(self):
        from aegiswifi.interfaces.restoration import load_interface_state

        with patch("aegiswifi.interfaces.restoration._STATE_DIR", Path("/nonexistent")):
            loaded = load_interface_state("wlan0")
        assert loaded is None

    def test_load_state_corrupted(self, tmp_path: Path):
        from aegiswifi.interfaces.restoration import load_interface_state

        state_dir = tmp_path / "iface_states"
        state_dir.mkdir()
        (state_dir / "wlan0.json").write_text("{invalid json", encoding="utf-8")

        with patch("aegiswifi.interfaces.restoration._STATE_DIR", state_dir):
            loaded = load_interface_state("wlan0")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_capture_current_state(self):
        from aegiswifi.interfaces.restoration import capture_current_state

        mock_iw_output = """phy#0
\tInterface wlan0
\t\taddr 00:11:22:33:44:55
\t\ttype managed
\t\tchannel 6 (2462 MHz)
"""
        with (
            patch("aegiswifi.interfaces.restoration._run_iw", new_callable=AsyncMock) as mock_iw,
            patch(
                "aegiswifi.interfaces.restoration._is_interface_up", new_callable=AsyncMock
            ) as mock_up,
        ):
            mock_iw.return_value = (mock_iw_output, "")
            mock_up.return_value = True
            state = await capture_current_state("wlan0")

        assert state.interface == "wlan0"
        assert state.original_type == "managed"
        assert state.original_channel == 6
        assert state.was_up is True

    @pytest.mark.asyncio
    async def test_restore_interface_from_state(self, tmp_path: Path):
        from aegiswifi.interfaces.restoration import restore_interface, save_interface_state

        state = InterfaceState(
            interface="wlan0",
            original_type="managed",
            was_up=True,
        )

        state_dir = tmp_path / "iface_states"
        with patch("aegiswifi.interfaces.restoration._STATE_DIR", state_dir):
            save_interface_state(state)

            # Mock all subprocess calls to succeed
            with (
                patch(
                    "aegiswifi.interfaces.restoration._run_iw", new_callable=AsyncMock
                ) as mock_iw,
                patch(
                    "aegiswifi.interfaces.restoration._run_ip", new_callable=AsyncMock
                ) as mock_ip,
            ):
                mock_iw.return_value = ("", "")
                # ip link show should report state DOWN
                mock_ip.return_value = ("state DOWN", "")
                result = await restore_interface("wlan0")

        assert result is True
        # After restore, state file should be deleted
        with patch("aegiswifi.interfaces.restoration._STATE_DIR", state_dir):
            assert not (state_dir / "wlan0.json").exists()

    @pytest.mark.asyncio
    async def test_restore_interface_no_state(self):
        from aegiswifi.interfaces.restoration import restore_interface

        with patch("aegiswifi.interfaces.restoration._STATE_DIR", Path("/nonexistent")):
            result = await restore_interface("wlan0")
        assert result is True  # Nothing to restore is success

    @pytest.mark.asyncio
    async def test_is_interface_up(self):
        from aegiswifi.interfaces.restoration import _is_interface_up

        with patch("aegiswifi.interfaces.restoration._run_ip", new_callable=AsyncMock) as mock_ip:
            mock_ip.return_value = ("state UP", "")
            assert await _is_interface_up("wlan0") is True

    @pytest.mark.asyncio
    async def test_is_interface_down(self):
        from aegiswifi.interfaces.restoration import _is_interface_up

        with patch("aegiswifi.interfaces.restoration._run_ip", new_callable=AsyncMock) as mock_ip:
            mock_ip.return_value = ("state DOWN", "")
            assert await _is_interface_up("wlan0") is False


# ===================================================================
# Service Module Tests
# ===================================================================


class TestServiceModule:
    @pytest.mark.asyncio
    async def test_get_interface(self):
        from aegiswifi.interfaces.service import get_interface

        mock_iface = WirelessInterface(name="wlan0", type="managed")
        with patch(
            "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_iface
            result = await get_interface("wlan0")
        assert result is not None
        assert result.name == "wlan0"

    @pytest.mark.asyncio
    async def test_get_interface_not_found(self):
        from aegiswifi.interfaces.service import get_interface

        with patch(
            "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None
            result = await get_interface("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_interfaces(self):
        from aegiswifi.interfaces.service import list_all_interfaces

        with patch(
            "aegiswifi.interfaces.service.list_interfaces", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [
                WirelessInterface(name="wlan0", type="managed"),
                WirelessInterface(name="wlan1", type="monitor"),
            ]
            result = await list_all_interfaces()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_prepare_interface_full_flow(self):
        """prepare_interface: flujo completo."""
        from aegiswifi.interfaces.service import prepare_interface

        mock_iface = WirelessInterface(name="wlan0", type="managed")
        mock_state = InterfaceState(interface="wlan0", original_type="managed", was_up=True)

        with (
            patch(
                "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "aegiswifi.interfaces.service.capture_current_state", new_callable=AsyncMock
            ) as mock_capture,
            patch("aegiswifi.interfaces.service.save_interface_state") as mock_save,
            patch(
                "aegiswifi.interfaces.service.enable_monitor_mode", new_callable=AsyncMock
            ) as mock_enable,
            patch(
                "aegiswifi.interfaces.service.test_injection", new_callable=AsyncMock
            ) as mock_inject,
        ):
            mock_get.return_value = mock_iface
            mock_capture.return_value = mock_state
            mock_enable.return_value = "wlan0"
            mock_inject.return_value = True

            result = await prepare_interface("wlan0")

        assert result.interface == "wlan0"
        assert result.monitor_interface == "wlan0"
        assert result.mode_set is True
        assert result.injection_ok is True
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_interface_not_found(self):
        from aegiswifi.interfaces.service import prepare_interface

        with patch(
            "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            with pytest.raises(RuntimeError, match="no encontrada"):
                await prepare_interface("nonexistent")

    @pytest.mark.asyncio
    async def test_restore_interface_service(self):
        from aegiswifi.interfaces.service import (
            restore_interface as svc_restore,
        )

        with (
            patch(
                "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
            ) as mock_get,
            patch(
                "aegiswifi.interfaces.service.restore_interface", new_callable=AsyncMock
            ) as mock_restore,
        ):
            mock_get.return_value = WirelessInterface(name="wlan0", type="managed")
            mock_restore.return_value = True

            result = await svc_restore("wlan0")

        assert result.interface == "wlan0"
        assert result.restored is True
        assert result.current_type == "managed"

    @pytest.mark.asyncio
    async def test_diagnose_interface_found(self):
        from aegiswifi.interfaces.service import diagnose_interface

        with (
            patch(
                "aegiswifi.interfaces.service.check_rfkill", new_callable=AsyncMock
            ) as mock_rfkill,
            patch(
                "aegiswifi.interfaces.service.detect_conflicting_processes", new_callable=AsyncMock
            ) as mock_procs,
            patch(
                "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
            ) as mock_get,
        ):
            mock_rfkill.return_value = []
            mock_procs.return_value = ["NetworkManager"]
            mock_get.return_value = WirelessInterface(name="wlan0", type="managed")

            result = await diagnose_interface("wlan0")

        assert result.present is True
        assert "NetworkManager" in result.conflicting_processes

    @pytest.mark.asyncio
    async def test_diagnose_interface_not_found(self):
        from aegiswifi.interfaces.service import diagnose_interface

        with (
            patch(
                "aegiswifi.interfaces.service.check_rfkill", new_callable=AsyncMock
            ) as mock_rfkill,
            patch(
                "aegiswifi.interfaces.service.detect_conflicting_processes", new_callable=AsyncMock
            ) as mock_procs,
            patch(
                "aegiswifi.interfaces.service.get_interface_details", new_callable=AsyncMock
            ) as mock_get,
        ):
            mock_rfkill.return_value = []
            mock_procs.return_value = []
            mock_get.return_value = None

            result = await diagnose_interface("nonexistent")

        assert result.present is False
        assert len(result.issues) > 0


# ===================================================================
# API Tests
# ===================================================================


class TestInterfaceAPI:
    @pytest.mark.asyncio
    async def test_list_interfaces_api(self, client: TestClient):
        """GET /api/v1/interfaces retorna 200."""
        with patch(
            "aegiswifi.interfaces.service.list_all_interfaces", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = [
                WirelessInterface(name="wlan0", type="managed"),
            ]
            resp = client.get("/api/v1/interfaces")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "wlan0"

    @pytest.mark.asyncio
    async def test_get_interface_api_found(self, client: TestClient):
        with patch(
            "aegiswifi.interfaces.service.get_interface", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = WirelessInterface(
                name="wlan0",
                type="managed",
                mac="00:11:22:33:44:55",
            )
            resp = client.get("/api/v1/interfaces/wlan0")
        assert resp.status_code == 200
        assert resp.json()["name"] == "wlan0"

    @pytest.mark.asyncio
    async def test_get_interface_api_not_found(self, client: TestClient):
        with patch(
            "aegiswifi.interfaces.service.get_interface", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None
            resp = client.get("/api/v1/interfaces/nonexistent")
        assert resp.status_code == 404
        assert "no encontrada" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_prepare_interface_api(self, client: TestClient):
        mock_state = InterfaceState(interface="wlan0", original_type="managed", was_up=True)
        mock_result = InterfacePrepareResult(
            interface="wlan0",
            monitor_interface="wlan0",
            mode_set=True,
            injection_ok=True,
            original_state=mock_state,
        )

        with patch(
            "aegiswifi.interfaces.service.prepare_interface", new_callable=AsyncMock
        ) as mock_prep:
            mock_prep.return_value = mock_result
            resp = client.post("/api/v1/interfaces/wlan0/prepare")
        assert resp.status_code == 200
        data = resp.json()
        assert data["interface"] == "wlan0"
        assert data["mode_set"] is True

    @pytest.mark.asyncio
    async def test_restore_interface_api(self, client: TestClient):
        mock_result = InterfaceRestoreResult(
            interface="wlan0", restored=True, current_type="managed"
        )

        with patch(
            "aegiswifi.interfaces.service.restore_interface", new_callable=AsyncMock
        ) as mock_restore:
            mock_restore.return_value = mock_result
            resp = client.post("/api/v1/interfaces/wlan0/restore")
        assert resp.status_code == 200
        assert resp.json()["restored"] is True

    @pytest.mark.asyncio
    async def test_diagnose_api(self, client: TestClient):
        mock_diag = InterfaceDiagnostic(
            interface="wlan0",
            present=True,
            blocked=False,
            conflicting_processes=[],
        )

        with patch(
            "aegiswifi.interfaces.service.diagnose_interface", new_callable=AsyncMock
        ) as mock_diag_svc:
            mock_diag_svc.return_value = mock_diag
            resp = client.get("/api/v1/interfaces/diagnose?name=wlan0")
        assert resp.status_code == 200
        assert resp.json()["present"] is True
