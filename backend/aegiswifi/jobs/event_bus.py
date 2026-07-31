"""Pub/sub event bus con buffer de replay para WebSocket (minuta §26 req 13).

    EventBus
        subscribe(queue, job_id=..., engagement_id=...)
        unsubscribe(queue)
        publish(envelope)
        get_replay(job_ids=..., engagement_ids=..., limit=...)

Los WebSocket handlers se suscriben al EventBus y reciben eventos en tiempo real.
El ring buffer permite replay a clientes que se reconectan.
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class JobEventEnvelope:
    """Payload de un evento de trabajo publicado en el bus."""

    event_type: str  # tipo de evento: job_created, job_status_changed, etc.
    job_id: int
    engagement_id: int
    data: dict[str, object]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


_WILDCARD = "*"


class EventBus:
    """Bus de eventos pub/sub con buffer circular para replay.

    Los suscriptores se registran por patrón: ``"job:<id>"``, ``"engagement:<id>"``,
    o ``"*"`` para todos los eventos.
    """

    def __init__(self, buffer_size: int = 1000) -> None:
        self._buffer_size = buffer_size
        self._subscribers: dict[str, set[asyncio.Queue[JobEventEnvelope]]] = {}
        self._replay_buffer: deque[JobEventEnvelope] = deque(maxlen=buffer_size)

    # ------------------------------------------------------------------
    # Suscripción
    # ------------------------------------------------------------------

    def subscribe(
        self,
        queue: asyncio.Queue[JobEventEnvelope],
        *,
        job_id: int | None = None,
        engagement_id: int | None = None,
    ) -> None:
        """Registra una cola para recibir eventos, opcionalmente filtrados."""
        self._register(queue, _WILDCARD)
        if job_id is not None:
            self._register(queue, f"job:{job_id}")
        if engagement_id is not None:
            self._register(queue, f"engagement:{engagement_id}")

    def unsubscribe(self, queue: asyncio.Queue[JobEventEnvelope]) -> None:
        """Elimina una cola de todos los patrones en los que esté registrada."""
        for key, queues in list(self._subscribers.items()):
            queues.discard(queue)
            if not queues:
                del self._subscribers[key]

    # ------------------------------------------------------------------
    # Publicación
    # ------------------------------------------------------------------

    def publish(self, envelope: JobEventEnvelope) -> None:
        """Publica un evento en el bus y lo guarda en el buffer de replay."""
        self._replay_buffer.append(envelope)
        self._dispatch(envelope)

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def get_replay(
        self,
        *,
        job_ids: list[int] | None = None,
        engagement_ids: list[int] | None = None,
        limit: int = 100,
    ) -> list[JobEventEnvelope]:
        """Devuelve eventos del buffer de replay filtrados opcionalmente."""
        result: list[JobEventEnvelope] = []
        for env in reversed(self._replay_buffer):
            if len(result) >= limit:
                break
            if job_ids and env.job_id not in job_ids:
                continue
            if engagement_ids and env.engagement_id not in engagement_ids:
                continue
            result.append(env)
        result.reverse()
        return result

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _register(self, queue: asyncio.Queue[JobEventEnvelope], key: str) -> None:
        if key not in self._subscribers:
            self._subscribers[key] = set()
        self._subscribers[key].add(queue)

    def _dispatch(self, envelope: JobEventEnvelope) -> None:
        targets: set[asyncio.Queue[JobEventEnvelope]] = set()
        # Siempre incluir wildcard.
        targets.update(self._subscribers.get(_WILDCARD, set()))
        targets.update(self._subscribers.get(f"job:{envelope.job_id}", set()))
        targets.update(self._subscribers.get(f"engagement:{envelope.engagement_id}", set()))

        for queue in targets:
            with suppress(asyncio.QueueFull):
                queue.put_nowait(envelope)


# Singleton module-level accessor.

_instance: EventBus | None = None


def get_event_bus(buffer_size: int = 1000) -> EventBus:
    """Devuelve la instancia singleton del EventBus, creándola si es necesario."""
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = EventBus(buffer_size=buffer_size)
    return _instance


def reset_event_bus() -> None:
    """Reinicia el singleton (útil en tests)."""
    global _instance  # noqa: PLW0603
    _instance = None
