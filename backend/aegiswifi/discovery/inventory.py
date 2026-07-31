"""Inventario en memoria de APs y clientes (minuta §14, §37).

Mantiene el estado actual del entorno inalámbrico descubierto,
detecta cambios entre escaneos y emite eventos estructurados
que el módulo WebSocket consume.

Thread-safe vía ``asyncio.Lock`` — las operaciones de upsert
desde el scanner compiten con lecturas desde la API.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from aegiswifi.discovery.classifier import classify_security, detect_degraded_security
from aegiswifi.discovery.schemas import (
    AccessPointDetail,
    ClientSummary,
    DiscoveryEvent,
    InventoryExport,
    InventoryFilter,
    InventorySnapshot,
    PnfMode,
    ScanStatus,
    SecurityProtocol,
    TransitionMode,
)


class DiscoveryInventory:
    """Inventario en memoria del entorno inalámbrico.

    Almacena APs (key: BSSID) y clients (key: MAC), detecta
    cambios en cada ``upsert_*`` y genera eventos para WebSocket.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

        # Estado actual
        self._aps: dict[str, AccessPointDetail] = {}
        self._clients: dict[str, ClientSummary] = {}
        self._event_history: list[DiscoveryEvent] = []

        # Historial de protocolos para detección de degradación
        self._protocol_history: dict[str, SecurityProtocol] = {}

        # Límite del ring buffer de eventos
        self._max_events: int = 1000

    # ── Propiedades ────────────────────────────────────────────────

    @property
    def ap_count(self) -> int:
        return len(self._aps)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    # ── Upserts ────────────────────────────────────────────────────

    async def upsert_ap(self, data: dict[str, Any]) -> list[DiscoveryEvent]:
        """Inserta o actualiza un AP. Retorna lista de eventos generados."""
        async with self._lock:
            bssid = data.get("bssid", "").upper()
            if not bssid:
                return []

            # Clasificar seguridad
            classification = classify_security(
                privacy=data.get("privacy", ""),
                cipher=data.get("cipher", ""),
                authentication=data.get("authentication", ""),
                wps_col=data.get("wps", ""),
                flags=data.get("flags", ""),
                essid=data.get("essid", ""),
            )

            existing = self._aps.get(bssid)
            now = datetime.now(UTC)
            events: list[DiscoveryEvent] = []

            if existing is None:
                # Nuevo AP
                detail = self._build_ap_detail(data, classification, now)
                self._aps[bssid] = detail
                self._protocol_history[bssid] = detail.protocol
                events.append(
                    DiscoveryEvent(
                        event_type="ap_discovered",
                        data={"bssid": bssid, "ssid": detail.ssid, "protocol": str(detail.protocol)},
                    )
                )
            else:
                # Actualizar campos
                detail = self._build_ap_detail(data, classification, now)
                detail.first_seen = existing.first_seen
                self._aps[bssid] = detail
                events.append(
                    DiscoveryEvent(
                        event_type="ap_updated",
                        data={"bssid": bssid, "changes": self._detect_changes(existing, detail)},
                    )
                )

                # Detectar degradación
                prev_protocol = self._protocol_history.get(bssid)
                if prev_protocol and detect_degraded_security(detail.protocol, prev_protocol):
                    self._protocol_history[bssid] = detail.protocol
                    events.append(
                        DiscoveryEvent(
                            event_type="security_degraded",
                            data={
                                "bssid": bssid,
                                "previous": str(prev_protocol),
                                "current": str(detail.protocol),
                            },
                        )
                    )

            self._event_history.extend(events)
            self._trim_history()
            return events

    async def upsert_client(self, data: dict[str, Any]) -> list[DiscoveryEvent]:
        """Inserta o actualiza un cliente. Retorna lista de eventos generados."""
        async with self._lock:
            mac = data.get("station_mac", "").upper()
            if not mac:
                return []

            existing = self._clients.get(mac)
            now = datetime.now(UTC)
            events: list[DiscoveryEvent] = []

            probe_requests = data.get("probed_essids", "")
            probes = [p.strip() for p in probe_requests.split(",") if p.strip()] if probe_requests else []

            power = data.get("power")
            signal = int(power) if power is not None and power != "" and power != "?" else None

            if existing is None:
                summary = ClientSummary(
                    mac=mac,
                    signal=signal,
                    associated_bssid=data.get("bssid", "").upper() or None,
                    associated_ssid=None,
                    probe_requests=probes,
                    first_seen=now,
                    last_seen=now,
                )
                self._clients[mac] = summary
                events.append(
                    DiscoveryEvent(
                        event_type="client_discovered",
                        data={"mac": mac, "signal": signal},
                    )
                )
            else:
                summary = existing.model_copy(
                    update={
                        "signal": signal if signal else existing.signal,
                        "last_seen": now,
                        "associated_bssid": data.get("bssid", "").upper() or existing.associated_bssid,
                        "probe_requests": probes or existing.probe_requests,
                    }
                )
                self._clients[mac] = summary
                events.append(
                    DiscoveryEvent(
                        event_type="client_updated",
                        data={"mac": mac, "signal": signal},
                    )
                )

            self._event_history.extend(events)
            self._trim_history()
            return events

    # ── Lecturas ────────────────────────────────────────────────────

    async def list_aps(self, filters: InventoryFilter | None = None) -> list[AccessPointDetail]:
        """Lista APs aplicando filtros opcionales."""
        async with self._lock:
            aps = list(self._aps.values())

        if filters is None:
            return aps

        return self._apply_ap_filters(aps, filters)

    async def list_clients(self, filters: InventoryFilter | None = None) -> list[ClientSummary]:
        """Lista clientes aplicando filtros opcionales."""
        async with self._lock:
            clients = list(self._clients.values())

        return clients  # Client-level filtering TBD

    async def get_ap(self, bssid: str) -> AccessPointDetail | None:
        """Obtiene un AP por BSSID."""
        async with self._lock:
            return self._aps.get(bssid.upper())

    async def snapshot(self, scan_status: ScanStatus | None = None) -> InventorySnapshot:
        """Toma un snapshot del inventario actual."""
        async with self._lock:
            return InventorySnapshot(
                access_points=list(self._aps.values()),
                clients=list(self._clients.values()),
                scan_status=scan_status or ScanStatus(),
            )

    async def export(self, filters: InventoryFilter | None = None) -> InventoryExport:
        """Exporta el inventario con filtros opcionales."""
        aps = await self.list_aps(filters)
        async with self._lock:
            clients = list(self._clients.values())

        return InventoryExport(
            access_points=aps,
            clients=clients,
            filters_applied=filters,
        )

    async def find_degraded(self) -> list[AccessPointDetail]:
        """Encuentra APs con degradación de seguridad."""
        async with self._lock:
            return [ap for ap in self._aps.values() if ap.degraded]

    async def find_aps_with_wps(self) -> list[AccessPointDetail]:
        """Encuentra APs con WPS habilitado."""
        async with self._lock:
            return [ap for ap in self._aps.values() if ap.wps]

    async def clear(self) -> None:
        """Limpia todo el inventario."""
        async with self._lock:
            self._aps.clear()
            self._clients.clear()
            self._event_history.clear()
            self._protocol_history.clear()

    # ── Eventos ─────────────────────────────────────────────────────

    async def recent_events(self, limit: int = 50) -> list[DiscoveryEvent]:
        """Retorna los eventos más recientes."""
        async with self._lock:
            return self._event_history[-limit:]

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _build_ap_detail(
        data: dict[str, Any],
        classification: dict,
        now: datetime,
    ) -> AccessPointDetail:
        """Construye un AccessPointDetail desde datos crudos + clasificación."""
        channel_str = data.get("channel", "")
        channel = int(channel_str) if channel_str and channel_str not in ("?", "-1", "") else None
        power = data.get("power")
        signal = int(power) if power is not None and power != "?" else None

        return AccessPointDetail(
            bssid=data.get("bssid", "").upper(),
            ssid=data.get("essid", "") or None,
            channel=channel,
            frequency=None,
            band=None,
            signal=signal,
            protocol=classification.get("protocol", SecurityProtocol.UNKNOWN),
            akm=", ".join(classification.get("akm", [])),
            cipher=classification.get("cipher", "UNKNOWN"),
            pmf=classification.get("pmf", PnfMode.UNKNOWN),
            wps=classification.get("wps", False),
            wpa3_supported=classification.get("wpa3_supported", False),
            transition_mode=classification.get("transition_mode", TransitionMode.NONE),
            degraded=classification.get("degraded", False),
            beacon_count=int(data.get("beacons", 0)) if data.get("beacons", "").strip().isdigit() else None,
            first_seen=now,
            last_seen=now,
        )

    @staticmethod
    def _detect_changes(
        old: AccessPointDetail,
        new: AccessPointDetail,
    ) -> dict[str, dict[str, str]]:
        """Compara dos APs y retorna los campos cambiados."""
        changes: dict[str, dict[str, str]] = {}
        comparable_fields = ["signal", "channel", "ssid", "protocol", "pmf", "wps", "akm"]

        for field in comparable_fields:
            old_val = getattr(old, field, None)
            new_val = getattr(new, field, None)
            if str(old_val) != str(new_val):
                changes[field] = {"from": str(old_val), "to": str(new_val)}

        return changes

    @staticmethod
    def _apply_ap_filters(
        aps: list[AccessPointDetail],
        filters: InventoryFilter,
    ) -> list[AccessPointDetail]:
        """Aplica filtros a una lista de APs."""
        result = aps

        if filters.ssid is not None:
            result = [ap for ap in result if ap.ssid and filters.ssid.lower() in ap.ssid.lower()]
        if filters.bssid is not None:
            result = [ap for ap in result if ap.bssid and filters.bssid.upper() in ap.bssid]
        if filters.band is not None:
            result = [ap for ap in result if ap.band == filters.band]
        if filters.channel is not None:
            result = [ap for ap in result if ap.channel == filters.channel]
        if filters.protocol is not None:
            result = [ap for ap in result if ap.protocol == filters.protocol]
        if filters.in_scope is not None:
            result = [ap for ap in result if ap.in_scope == filters.in_scope]
        if filters.wps is not None:
            result = [ap for ap in result if ap.wps == filters.wps]
        if filters.pmf is not None:
            result = [ap for ap in result if ap.pmf == filters.pmf]
        if filters.signal_min is not None:
            result = [ap for ap in result if ap.signal is not None and ap.signal >= filters.signal_min]
        if filters.signal_max is not None:
            result = [ap for ap in result if ap.signal is not None and ap.signal <= filters.signal_max]
        if filters.vendor is not None:
            result = [ap for ap in result if ap.vendor and filters.vendor.lower() in ap.vendor.lower()]

        # Paginación
        result = result[filters.offset : filters.offset + filters.limit]

        return result

    def _trim_history(self) -> None:
        """Recorta el ring buffer de eventos al límite."""
        if len(self._event_history) > self._max_events:
            self._event_history = self._event_history[-self._max_events:]