"""Schemas del módulo de cracking con Hashcat (minuta §18, §28).

Define los tipos de datos intercambiados entre la API, el planificador y el
adaptador de hashcat.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AttackMode(str, Enum):
    """Modos de ataque soportados por Hashcat (``-a``).

    Referencia: https://hashcat.net/wiki/doku.php?id=hashcat
    """

    DICTIONARY = "dictionary"  # -a 0
    COMBIATOR = "combinator"  # -a 1
    MASK = "mask"  # -a 3 (incluye hcmask)
    HYBRID_WORDLIST_MASK = "hybrid_wordlist_mask"  # -a 6
    HYBRID_MASK_WORDLIST = "hybrid_mask_wordlist"  # -a 7
    BRUTE_FORCE = "brute_force"  # -a 3 con charset completo
    PRINCE = "prince"  # PRINCE mode (--prince)
    RULE_BASED = "rule_based"  # -a 0 con -r


class AttackStage(BaseModel):
    """Una etapa dentro de un :class:`CrackingPlan`.

    Cada etapa representa una invocación independiente a hashcat con su
    propio modo de ataque, diccionario, reglas y timeout.
    """

    mode: AttackMode
    """Modo de ataque de esta etapa."""

    dictionary_path: str | None = None
    """Ruta al archivo de wordlist (obligatorio para dictionary / rule_based)."""

    rules_path: str | None = None
    """Ruta al archivo de reglas (opcional, usado en rule_based / hybrid)."""

    mask: str | None = None
    """Máscara para mask/hybrid (ej. ``?l?l?l?l?d?d``)."""

    custom_charset_1: str | None = None
    """Conjunto personalizado ?1 (ej. ``?l?d``)."""

    custom_charset_2: str | None = None
    """Conjunto personalizado ?2."""

    timeout_seconds: int | None = Field(default=None, ge=30)
    """Timeout opcional para esta etapa (hereda del plan si no se especifica)."""

    extra_args: list[str] = Field(default_factory=list)
    """Argumentos adicionales para hashcat (ej. ``--slow-candidates``)."""


class CrackingPlan(BaseModel):
    """Plan de auditoría multi-etapa.

    El plan es secuencial: si una etapa recupera la contraseña, las
    siguientes no se ejecutan.
    """

    job_id: int
    """ID del :class:`CrackingJob` en la base de datos."""

    artifact_id: int
    """ID del :class:`HandshakeArtifact` objetivo."""

    hash_file_path: str
    """Ruta absoluta al archivo .22000 que contiene el hash objetivo."""

    hash_mode: int = 22000
    """Modo de hash (-m). 22000 = WPA-PBKDF2-PMKID+EAPOL."""

    stages: list[AttackStage] = Field(default_factory=list)
    """Etapas del plan, ejecutadas en orden hasta recuperar la clave."""

    max_total_time: int = Field(default=3600, ge=60, le=86400)
    """Tiempo máximo total para todo el plan (segundos)."""

    max_total_cost: int | None = None
    """Costo computacional máximo (gigas de hashes, opcional)."""

    skip_self_test: bool = False
    """Si ``True``, omite el self-test de hashcat."""

    opencl_device: str | None = None
    """Dispositivo OpenCL específico (ej. ``--opencl-device=1``)."""


class CrackingProgress(BaseModel):
    """Progreso en vivo de una ejecución de hashcat.

    Corresponde a una línea del ``--status-json`` de hashcat.
    """

    job_id: int
    """ID del CrackingJob."""

    status: str
    """Estado reportado por hashcat (``Running``, ``Exhausted``, ``Cracked``)."""

    progress_denom: float = 0.0
    """Fracción completada (0..1) calculada de Guess.Mod/Guess.Base."""

    speed: int = 0
    """Velocidad actual en H/s (hash por segundo)."""

    time_estimated: int | None = None
    """Tiempo estimado restante en segundos."""

    hashes_processed: int = 0
    """Hashes procesados hasta ahora."""

    hashes_total: int = 0
    """Total de hashes a procesar."""

    recovered: int = 0
    """Cantidad de hashes recuperados."""

    rejected: int = 0
    """Candidatos rechazados por la regla."""

    device_info: str | None = None
    """Información del dispositivo GPU (opcional)."""

    raw_json: dict[str, Any] = Field(default_factory=dict)
    """Payload JSON completo de hashcat para diagnóstico."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    """Momento en que se generó esta métrica."""


class CrackingResult(BaseModel):
    """Resultado final de una ejecución de cracking."""

    job_id: int
    """ID del CrackingJob."""

    cracked: bool = False
    """Indica si la contraseña fue recuperada."""

    password: str | None = None
    """Contraseña recuperada (``None`` si no se crackeó)."""

    encrypted_secret: str | None = None
    """Contraseña cifrada con Fernet (para almacenar)."""

    exit_code: int | None = None
    """Código de salida de hashcat."""

    total_runtime_seconds: int | None = None
    """Tiempo total de ejecución."""

    peak_speed: int = 0
    """Velocidad máxima alcanzada (H/s)."""

    stages_executed: int = 0
    """Número de etapas realmente ejecutadas."""

    stages_total: int = 0
    """Número de etapas planificadas."""

    log_path: str | None = None
    """Ruta al log de la ejecución."""

    sha256: str | None = None
    """SHA-256 del log de salida."""

    mode_used: AttackMode | None = None
    """Modo de ataque que finalmente crackeó la clave."""


class DictionaryInfo(BaseModel):
    """Metadatos de un archivo de diccionario/wordlist."""

    path: str
    """Ruta absoluta al archivo."""

    name: str
    """Nombre del archivo (sin ruta)."""

    size_bytes: int = 0
    """Tamaño en bytes."""

    line_count: int | None = None
    """Cantidad de entradas/palabras (se computa bajo demanda)."""

    encoding: str = "utf-8"
    """Codificación detectada o asumida."""

    is_sorted: bool = False
    """Si las palabras están ordenadas (optimiza el rendimiento)."""

    description: str | None = None
    """Descripción opcional (provista por el usuario)."""

    compressed: bool = False
    """Indica que debe descomprimirse antes de utilizarlo con Hashcat."""

    custom: bool = False
    """Indica que pertenece al directorio administrado por AegisWiFi."""


class HashInfo(BaseModel):
    """Metadatos de un hash en formato 22000 listo para crackear."""

    artifact_id: int
    """ID del HandshakeArtifact de origen."""

    hash_file_path: str
    """Ruta al archivo .22000."""

    hash_line: str | None = None
    """Primera línea del hash (truncado)."""

    hash_count: int = 1
    """Cantidad de hashes en el archivo."""

    bssid: str | None = None
    """BSSID extraído del hash (si aplica)."""

    ssid: str | None = None
    """SSID extraído del hash (si aplica)."""

    kind: str = "eapol"
    """Tipo de handshake (``eapol`` o ``pmkid``)."""


class RuleInfo(BaseModel):
    """Metadatos de un archivo de reglas de Hashcat."""

    path: str
    """Ruta absoluta al archivo."""

    name: str
    """Nombre del archivo (sin ruta)."""

    size_bytes: int = 0
    """Tamaño en bytes."""

    rule_count: int | None = None
    """Cantidad de reglas en el archivo (se computa bajo demanda)."""

    description: str | None = None
    """Descripción opcional (provista por el usuario o extraída del header)."""


class CrackingJobRead(BaseModel):
    """Schema de respuesta para un CrackingJob (evita exponer el modelo SQLAlchemy)."""

    model_config = {"from_attributes": True}

    id: int
    artifact_id: int | None = None
    strategy: str = "dictionary"
    keyspace: int | None = None
    progress: float | None = None
    speed: int | None = None
    status: str = "CREATED"
    recovered: bool = False
    started_at: datetime | None = None
    finished_at: datetime | None = None
