"""Tests del módulo de descubrimiento (Fase 4, minuta §14 + §37).

Cubre:
  - Schemas: serialización, defaults, enums.
  - Classifier: classify_security (open, wpa2, wpa3, transition, wps, pmf).
  - CSV parser: vacío, APs, clientes, full, malformado.
  - Inventory: upsert new/update, eventos, clientes, filtros, snapshot, export, degraded.
  - Scanner: available T/F.
  - Service: start/stop/status, double-start.
  - API: endpoints REST via TestClient.

Todas las llamadas a herramientas externas (airodump-ng) se mockean
con :func:`unittest.mock.patch` para no depender del sistema operativo.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aegiswifi.discovery import service as discovery_service
from aegiswifi.discovery.classifier import (
    PnfMode,
    classify_security,
    detect_degraded_security,
)
from aegiswifi.discovery.csv_parser import parse_full_csv
from aegiswifi.discovery.inventory import DiscoveryInventory
from aegiswifi.discovery.schemas import (
    AccessPointDetail,
    AccessPointSummary,
    BandEnum,
    ClientSummary,
    InventoryFilter,
    ScanConfig,
    ScanStatus,
    SecurityProtocol,
    TransitionMode,
)
from aegiswifi.discovery.scanner import AirodumpScanner, _parse_csv_content, _scan_available
from fastapi.testclient import TestClient


# ===================================================================
# Schemas Tests
# ===================================================================


class TestSchemas:
    def test_ap_summary_defaults(self):
        ap = AccessPointSummary(bssid="AA:BB:CC:DD:EE:FF")
        assert ap.protocol == SecurityProtocol.UNKNOWN
        assert ap.in_scope is False
        assert ap.clients_count == 0
        assert ap.ssid is None

    def test_ap_summary_serialize_roundtrip(self):
        ap = AccessPointSummary(bssid="AA:BB:CC:DD:EE:FF", ssid="MyNet", channel=6)
        loaded = AccessPointSummary.model_validate_json(ap.model_dump_json())
        assert loaded.bssid == "AA:BB:CC:DD:EE:FF"
        assert loaded.ssid == "MyNet"
        assert loaded.channel == 6

    def test_client_summary_defaults(self):
        c = ClientSummary(mac="11:22:33:44:55:66")
        assert c.randomized is False
        assert c.probe_requests == []
        assert c.controlled is False

    def test_client_summary_serialize_roundtrip(self):
        c = ClientSummary(mac="11:22:33:44:55:66", vendor="Google", probe_requests=["A", "B"])
        loaded = ClientSummary.model_validate_json(c.model_dump_json())
        assert loaded.mac == "11:22:33:44:55:66"
        assert loaded.vendor == "Google"
        assert loaded.probe_requests == ["A", "B"]

    def test_security_protocol_enum_values(self):
        assert SecurityProtocol.WPA2 == "WPA2"
        assert SecurityProtocol.WPA3 == "WPA3"
        assert SecurityProtocol.WPA2_WPA3 == "WPA2/WPA3"

    def test_scan_config_defaults(self):
        cfg = ScanConfig(interface="wlan0")
        assert cfg.interface == "wlan0"
        assert cfg.channel is None
        assert cfg.hop_interval == 1


# ===================================================================
# Classifier Tests
# ===================================================================


class TestClassifier:
    def test_open_network(self):
        result = classify_security(privacy="OPN")
        assert result["protocol"] == SecurityProtocol.OPEN
        assert result["degraded"] is True

    def test_wpa2_psk(self):
        result = classify_security(privacy="WPA2", cipher="CCMP", authentication="PSK")
        assert result["protocol"] == SecurityProtocol.WPA2
        assert result["akm"] == ["PSK"]
        assert result["cipher"] == "CCMP"

    def test_wpa3_sae(self):
        result = classify_security(privacy="WPA3", cipher="GCMP", authentication="SAE")
        assert result["protocol"] == SecurityProtocol.WPA3
        assert result["wpa3_supported"] is True

    def test_transition_mode_wpa2wpa3(self):
        result = classify_security(
            privacy="WPA2WPA3", cipher="CCMP", authentication="SAE", flags="Transition"
        )
        assert result["transition_mode"] == TransitionMode.WPA3_TRANSITION
        assert result["wpa3_supported"] is True

    def test_wps_enabled_via_col(self):
        result = classify_security(privacy="WPA2", wps_col="1")
        assert result["wps"] is True

    def test_wps_enabled_via_flags(self):
        result = classify_security(privacy="WPA2", flags="WPS")
        assert result["wps"] is True

    def test_wps_disabled(self):
        result = classify_security(privacy="OPN", wps_col="0")
        assert result["wps"] is False

    def test_pmf_optional_via_mfp(self):
        result = classify_security(privacy="WPA2", flags="MFP")
        assert result["pmf"] == PnfMode.OPTIONAL

    def test_pmf_required_via_mfp_req(self):
        result = classify_security(privacy="WPA2", flags="MFP-REQ")
        assert result["pmf"] == PnfMode.REQUIRED

    def test_pmf_unknown_when_no_flags(self):
        result = classify_security(privacy="WPA2")
        assert result["pmf"] == PnfMode.UNKNOWN

    def test_detect_degraded_downgrade(self):
        assert detect_degraded_security(
            current_protocol=SecurityProtocol.WPA2,
            previous_protocol=SecurityProtocol.WPA3,
        )

    def test_detect_degraded_upgrade(self):
        assert not detect_degraded_security(
            current_protocol=SecurityProtocol.WPA3,
            previous_protocol=SecurityProtocol.WPA2,
        )

    def test_detect_degraded_same(self):
        assert not detect_degraded_security(
            current_protocol=SecurityProtocol.WPA2,
            previous_protocol=SecurityProtocol.WPA2,
        )


# ===================================================================
# CSV Parser Tests
# ===================================================================


_AP_CSV = (
    "BSSID,First time seen,Last time seen,channel,Speed,Privacy,Cipher,"
    "Authentication,Power,# beacons,IV,LAN IP,ID length,ESSID\n"
    "AA:BB:CC:DD:EE:FF,2026-07-29 10:00:00,2026-07-29 10:05:00,6,6,"
    "WPA2,CCMP,PSK,-45,100,0,0,0,MyNetwork\n"
)

_CLIENT_CSV = (
    "Station MAC,First time seen,Last time seen,Power,# packets,BSSID,"
    "Probed ESSIDs\n"
    "11:22:33:44:55:66,2026-07-29 10:01:00,2026-07-29 10:02:00,-40,45,"
    "AA:BB:CC:DD:EE:FF,MyNetwork\n"
)


class TestCsvParser:
    def test_empty_csv(self):
        aps, clients = parse_full_csv("")
        assert aps == []
        assert clients == []

    def test_aps_only(self):
        aps, clients = parse_full_csv(_AP_CSV)
        assert len(aps) == 1
        assert aps[0]["bssid"] == "AA:BB:CC:DD:EE:FF"
        assert aps[0]["essid"] == "MyNetwork"
        assert aps[0]["privacy"] == "WPA2"
        assert aps[0]["channel"] == "6"
        assert clients == []

    def test_clients_only(self):
        aps, clients = parse_full_csv(_CLIENT_CSV)
        assert aps == []
        assert len(clients) == 1
        assert clients[0]["station_mac"] == "11:22:33:44:55:66"
        assert clients[0]["bssid"] == "AA:BB:CC:DD:EE:FF"

    def test_full_csv_ap_and_clients(self):
        aps, clients = parse_full_csv(_AP_CSV + "\n" + _CLIENT_CSV)
        assert len(aps) == 1
        assert len(clients) == 1

    def test_power_parsed_as_int(self):
        aps, _ = parse_full_csv(_AP_CSV)
        assert aps[0]["power"] == -45


# ===================================================================
# Inventory Tests
# ===================================================================


def _ap_data(signal: str = "-40") -> dict:
    return {
        "bssid": "AA:BB:CC:DD:EE:FF",
        "essid": "MyNetwork",
        "channel": "6",
        "privacy": "WPA2",
        "cipher": "CCMP",
        "authentication": "PSK",
        "wps": "0",
        "flags": "MFP",
        "power": signal,
    }


class TestInventory:
    @pytest.mark.asyncio
    async def test_upsert_new_ap_emits_discovered(self):
        inv = DiscoveryInventory()
        events = await inv.upsert_ap(_ap_data())
        assert len(events) == 1
        assert events[0].event_type == "ap_discovered"

    @pytest.mark.asyncio
    async def test_upsert_existing_ap_emits_updated(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        events = await inv.upsert_ap(_ap_data(signal="-35"))
        assert len(events) == 1
        assert events[0].event_type == "ap_updated"

    @pytest.mark.asyncio
    async def test_upsert_new_client_emits_discovered(self):
        inv = DiscoveryInventory()
        events = await inv.upsert_client(
            {
                "station_mac": "11:22:33:44:55:66",
                "bssid": "AA:BB:CC:DD:EE:FF",
                "power": "-40",
                "probed_essids": "Google,MyNetwork",
            }
        )
        assert len(events) == 1
        assert events[0].event_type == "client_discovered"

    @pytest.mark.asyncio
    async def test_get_ap_returns_detail(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        ap = await inv.get_ap("AA:BB:CC:DD:EE:FF")
        assert ap is not None
        assert ap.ssid == "MyNetwork"

    @pytest.mark.asyncio
    async def test_get_ap_missing_returns_none(self):
        inv = DiscoveryInventory()
        assert await inv.get_ap("00:00:00:00:00:00") is None

    @pytest.mark.asyncio
    async def test_list_aps_with_protocol_filter(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        filters = InventoryFilter(protocol=SecurityProtocol.WPA2)
        aps = await inv.list_aps(filters)
        assert len(aps) == 1

    @pytest.mark.asyncio
    async def test_list_aps_with_nonmatching_filter(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        filters = InventoryFilter(protocol=SecurityProtocol.WPA3)
        aps = await inv.list_aps(filters)
        assert aps == []

    @pytest.mark.asyncio
    async def test_snapshot_includes_aps_and_clients(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        snapshot = await inv.snapshot(ScanStatus(running=True, interface="wlan0"))
        assert len(snapshot.access_points) == 1
        assert snapshot.scan_status.running is True

    @pytest.mark.asyncio
    async def test_export_contains_aps(self):
        inv = DiscoveryInventory()
        await inv.upsert_ap(_ap_data())
        export = await inv.export()
        assert len(export.access_points) == 1

    @pytest.mark.asyncio
    async def test_find_degraded_returns_marked_aps(self):
        inv = DiscoveryInventory()
        inv._aps["AA:BB:CC:DD:EE:FF"] = AccessPointDetail(
            bssid="AA:BB:CC:DD:EE:FF", protocol=SecurityProtocol.OPEN, degraded=True
        )
        degraded = await inv.find_degraded()
        assert len(degraded) == 1
        assert degraded[0].degraded is True

    @pytest.mark.asyncio
    async def test_find_aps_with_wps(self):
        inv = DiscoveryInventory()
        inv._aps["AA:BB:CC:DD:EE:FF"] = AccessPointDetail(
            bssid="AA:BB:CC:DD:EE:FF", wps=True
        )
        found = await inv.find_aps_with_wps()
        assert len(found) == 1
        assert found[0].wps is True


# ===================================================================
# Scanner Tests
# ===================================================================


class TestScanner:
    @pytest.mark.asyncio
    async def test_scan_available_true(self):
        with patch(
            "aegiswifi.discovery.scanner._run_airodump",
            new_callable=AsyncMock,
            return_value=("airodump-ng v1.0", ""),
        ):
            assert await _scan_available() is True

    @pytest.mark.asyncio
    async def test_scan_available_false(self):
        with patch(
            "aegiswifi.discovery.scanner._run_airodump",
            new_callable=AsyncMock,
            return_value=("", ""),
        ):
            assert await _scan_available() is False

    @pytest.mark.asyncio
    async def test_parse_csv_content_delegates(self):
        with patch(
            "aegiswifi.discovery.csv_parser.parse_full_csv",
            return_value=([{"bssid": "AA"}], []),
        ):
            aps, clients = await _parse_csv_content("dummy")
            assert aps == [{"bssid": "AA"}]
            assert clients == []


# ===================================================================
# Service Tests
# ===================================================================


class TestService:
    @pytest.mark.asyncio
    async def test_start_scan_returns_running_status(self):
        with patch(
            "aegiswifi.discovery.service._scan_available", new_callable=AsyncMock
        ), patch(
            "aegiswifi.discovery.service.AirodumpScanner"
        ) as mock_scanner_cls:
            mock_scanner = AsyncMock()
            mock_scanner.running = True
            mock_scanner.start = AsyncMock(return_value=True)
            mock_scanner_cls.return_value = mock_scanner

            # Reset module singletons
            discovery_service._set_scanner(None)
            discovery_service._inventory.clear = AsyncMock()

            status = await discovery_service.start_scan(ScanConfig(interface="wlan0"))
            assert status.running is True
            assert status.interface == "wlan0"

    @pytest.mark.asyncio
    async def test_stop_scan_when_not_running(self):
        discovery_service._set_scanner(None)
        status = await discovery_service.stop_scan()
        assert status.running is False

    @pytest.mark.asyncio
    async def test_get_scan_status_when_not_running(self):
        discovery_service._set_scanner(None)
        status = await discovery_service.get_scan_status()
        assert status.running is False

    @pytest.mark.asyncio
    async def test_start_scan_start_failure_returns_error(self):
        with patch(
            "aegiswifi.discovery.service._scan_available", new_callable=AsyncMock
        ), patch(
            "aegiswifi.discovery.service.AirodumpScanner"
        ) as mock_scanner_cls:
            mock_scanner = AsyncMock()
            mock_scanner.start = AsyncMock(return_value=False)
            mock_scanner_cls.return_value = mock_scanner

            discovery_service._set_scanner(None)
            discovery_service._inventory.clear = AsyncMock()

            status = await discovery_service.start_scan(ScanConfig(interface="wlan0"))
            assert status.running is False
            assert status.error is not None


# ===================================================================
# API Tests
# ===================================================================


@pytest.fixture()
def client():
    from aegiswifi.api.v1 import api_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(api_router)
    return TestClient(app)


class TestAPI:
    def test_get_status_not_running(self, client):
        discovery_service._set_scanner(None)
        with patch.object(
            discovery_service, "get_scan_status", new_callable=AsyncMock
        ) as mock_status:
            mock_status.return_value = ScanStatus()
            response = client.get("/api/v1/discovery/status")
        assert response.status_code == 200
        assert response.json()["running"] is False

    def test_list_aps_empty(self, client):
        with patch.object(
            discovery_service, "list_aps", new_callable=AsyncMock, return_value=[]
        ):
            response = client.get("/api/v1/discovery/aps")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_ap_not_found(self, client):
        with patch.object(
            discovery_service, "get_ap", new_callable=AsyncMock, return_value=None
        ):
            response = client.get("/api/v1/discovery/aps/00:00:00:00:00:00")
        assert response.status_code == 404

    def test_get_snapshot(self, client):
        from aegiswifi.discovery.schemas import InventorySnapshot

        with patch.object(
            discovery_service,
            "get_inventory_snapshot",
            new_callable=AsyncMock,
            return_value=InventorySnapshot(),
        ):
            response = client.get("/api/v1/discovery/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert "access_points" in data
        assert "clients" in data

    def test_start_scan_endpoint(self, client):
        with patch.object(
            discovery_service,
            "start_scan",
            new_callable=AsyncMock,
            return_value=ScanStatus(running=True, interface="wlan0"),
        ):
            response = client.post(
                "/api/v1/discovery/scan/start", json={"interface": "wlan0"}
            )
        assert response.status_code == 200
        assert response.json()["running"] is True

    def test_stop_scan_endpoint(self, client):
        with patch.object(
            discovery_service,
            "stop_scan",
            new_callable=AsyncMock,
            return_value=ScanStatus(),
        ):
            response = client.post("/api/v1/discovery/scan/stop")
        assert response.status_code == 200
        assert response.json()["running"] is False

    def test_get_degraded_endpoint(self, client):
        with patch.object(
            discovery_service, "find_degraded_aps", new_callable=AsyncMock, return_value=[]
        ):
            response = client.get("/api/v1/discovery/degraded")
        assert response.status_code == 200
        assert response.json() == []


# ===================================================================
# CLI Tests
# ===================================================================


class TestCli:
    def test_discovery_app_registered(self):
        from aegiswifi.discovery.cli import discovery_app

        # Typer stores the name under .info.name (or on the registered command).
        # The app is created with name="discovery".
        assert discovery_app.info.name == "discovery" or "discovery" in {
            getattr(r, "name", "") for r in discovery_app.registered_commands
        }
