"""Planificador multi-etapa de ataques de cracking (minuta §18).

Genera un :class:`CrackingPlan` secuencial priorizando etapas rápidas
antes que lentas: diccionario → reglas → combinator → máscara → fuerza bruta.
"""

from __future__ import annotations

from typing import Any

from aegiswifi.cracking.dictionary import DictionaryManager
from aegiswifi.cracking.rules import RulesManager
from aegiswifi.cracking.schemas import (
    AttackMode,
    AttackStage,
    CrackingPlan,
    DictionaryInfo,
    RuleInfo,
)


class CrackingPlanner:
    """Genera planes de cracking multi-etapa optimizados.

    El plan se construye en orden creciente de costo computacional:
    cada etapa es más costosa que la anterior, y el plan se detiene
    en cuanto una etapa recupera la contraseña.
    """

    # Tiempos por defecto por etapa (segundos).
    DEFAULT_TIMEOUTS: dict[AttackMode, int] = {
        AttackMode.DICTIONARY: 300,  # 5 min
        AttackMode.RULE_BASED: 600,  # 10 min
        AttackMode.COMBIATOR: 900,  # 15 min
        AttackMode.HYBRID_WORDLIST_MASK: 1200,  # 20 min
        AttackMode.HYBRID_MASK_WORDLIST: 1200,  # 20 min
        AttackMode.MASK: 1800,  # 30 min
        AttackMode.PRINCE: 1800,  # 30 min
        AttackMode.BRUTE_FORCE: 3600,  # 60 min
    }

    def __init__(
        self,
        dict_manager: DictionaryManager,
        rules_manager: RulesManager,
    ) -> None:
        self._dicts = dict_manager
        self._rules = rules_manager

    # ------------------------------------------------------------------
    # Generación de planes
    # ------------------------------------------------------------------

    def build_plan(
        self,
        job_id: int,
        artifact_id: int,
        hash_file_path: str,
        hash_mode: int = 22000,
        max_total_time: int = 3600,
        preferred_dicts: list[str] | None = None,
        preferred_rules: list[str] | None = None,
        skip_modes: list[AttackMode] | None = None,
    ) -> CrackingPlan:
        """Construye un plan secuencial multi-etapa.

        Args:
            job_id: ID del CrackingJob.
            artifact_id: ID del HandshakeArtifact.
            hash_file_path: Ruta al archivo .22000.
            hash_mode: Modo hash de hashcat (-m).
            max_total_time: Tiempo máximo total del plan (s).
            preferred_dicts: Lista de paths de wordlists preferidas.
            preferred_rules: Lista de paths de reglas preferidas.
            skip_modes: Modos de ataque a excluir.

        Returns:
            :class:`CrackingPlan` con etapas en orden de ejecución.
        """
        skip = set(skip_modes or [])

        # Escanear wordlists disponibles.
        # Hashcat recibe únicamente wordlists listas para usar. Los archivos
        # comprimidos permanecen visibles en Recursos hasta que el operador
        # los descomprima explícitamente.
        dicts = [dictionary for dictionary in self._dicts.scan_all() if not dictionary.compressed]
        rules = self._rules.scan_all()

        stages: list[AttackStage] = []

        # --- Etapa 1: Dictionary attack (rockyou u otras) ---
        if AttackMode.DICTIONARY not in skip:
            dict_path = self._pick_preferred_dict(dicts, preferred_dicts)
            if dict_path:
                stages.append(
                    AttackStage(
                        mode=AttackMode.DICTIONARY,
                        dictionary_path=dict_path,
                        timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.DICTIONARY],
                    )
                )

        # --- Etapa 2: Dictionary + rules ---
        if AttackMode.RULE_BASED not in skip:
            dict_path = self._pick_preferred_dict(dicts, preferred_dicts)
            rule_path = self._pick_preferred_rule(rules, preferred_rules)
            if dict_path and rule_path:
                stages.append(
                    AttackStage(
                        mode=AttackMode.RULE_BASED,
                        dictionary_path=dict_path,
                        rules_path=rule_path,
                        timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.RULE_BASED],
                    )
                )

        # --- Etapa 3: Combinator (dos wordlists) ---
        if AttackMode.COMBIATOR not in skip:
            dicts_available = [d.path for d in dicts if d.path]
            if len(dicts_available) >= 2:
                stages.append(
                    AttackStage(
                        mode=AttackMode.COMBIATOR,
                        dictionary_path=dicts_available[1],
                        extra_args=[dicts_available[0]],
                        timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.COMBIATOR],
                    )
                )

        # --- Etapa 4: Hybrid wordlist + mask ---
        if AttackMode.HYBRID_WORDLIST_MASK not in skip:
            dict_path = self._pick_preferred_dict(dicts, preferred_dicts)
            if dict_path:
                stages.append(
                    AttackStage(
                        mode=AttackMode.HYBRID_WORDLIST_MASK,
                        dictionary_path=dict_path,
                        mask="?d?d?d?d",
                        timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.HYBRID_WORDLIST_MASK],
                    )
                )

        # --- Etapa 5: Mask attack (8 chars lowercase) ---
        if AttackMode.MASK not in skip:
            stages.append(
                AttackStage(
                    mode=AttackMode.MASK,
                    mask="?l?l?l?l?l?l?l?l",
                    timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.MASK],
                )
            )

        # --- Etapa 6: PRINCE mode ---
        if AttackMode.PRINCE not in skip:
            dict_path = self._pick_preferred_dict(dicts, preferred_dicts)
            if dict_path:
                stages.append(
                    AttackStage(
                        mode=AttackMode.PRINCE,
                        dictionary_path=dict_path,
                        timeout_seconds=self.DEFAULT_TIMEOUTS[AttackMode.PRINCE],
                    )
                )

        return CrackingPlan(
            job_id=job_id,
            artifact_id=artifact_id,
            hash_file_path=hash_file_path,
            hash_mode=hash_mode,
            stages=stages,
            max_total_time=max_total_time,
        )

    # ------------------------------------------------------------------
    # Profile-based plan (ataque inteligente)
    # ------------------------------------------------------------------

    def build_profile_plan(
        self,
        job_id: int,
        artifact_id: int,
        hash_file_path: str,
        essid: str | None = None,
        bssid: str | None = None,
        **kwargs: Any,
    ) -> CrackingPlan:
        """Construye un plan adaptado al perfil de la red objetivo.

        Si el ESSID tiene un formato conocido (ej. ``MOVISTAR_XXXX``,
        ``WLAN_XXXX``), ajusta las máscaras y prioridades.
        """
        plan = self.build_plan(
            job_id=job_id,
            artifact_id=artifact_id,
            hash_file_path=hash_file_path,
            **kwargs,
        )

        # Personalizar según nombre de red.
        if essid:
            essid_upper = essid.upper()
            if essid_upper.startswith("MOVISTAR"):
                # Las redes Movistar suelen tener 8 dígitos.
                plan.stages.append(
                    AttackStage(
                        mode=AttackMode.MASK,
                        mask="?d?d?d?d?d?d?d?d",
                        timeout_seconds=1800,
                    )
                )
            elif any(p in essid_upper for p in ("WLAN", "JAZZTEL", "ONO", "YA_")):
                plan.stages.append(
                    AttackStage(
                        mode=AttackMode.MASK,
                        mask="?d?d?d?d?d?d?d?d?d?d",
                        timeout_seconds=3600,
                    )
                )

        return plan

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pick_preferred_dict(
        self,
        available: list[DictionaryInfo],
        preferred: list[str] | None = None,
    ) -> str | None:
        """Elige la mejor wordlist disponible.

        Prioriza preferidas del usuario, luego rockyou, luego la primera.
        """
        if not available:
            return None

        preferred_set = set(preferred or [])
        for info in available:
            if info.path in preferred_set:
                return info.path

        # rockyou es la preferida por defecto.
        for info in available:
            if "rockyou" in info.name.lower():
                return info.path

        return available[0].path

    def _pick_preferred_rule(
        self,
        available: list[RuleInfo],
        preferred: list[str] | None = None,
    ) -> str | None:
        """Elige el mejor archivo de reglas disponible."""
        if not available:
            return None

        preferred_set = set(preferred or [])
        for info in available:
            if info.path in preferred_set:
                return info.path

        # best64.rule es la regla más común.
        for info in available:
            if "best64" in info.name.lower():
                return info.path

        return available[0].path
