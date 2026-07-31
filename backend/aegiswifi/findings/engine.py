"""Motor de hallazgos (minuta §29, §28).

Convierte evidencia técnica en hallazgos profesionales mediante reglas
de detección. Incluye reglas integradas y permite extender con reglas
personalizadas.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegiswifi.database.models import (
    CrackingJob,
    CrackJobStatus,
    Engagement,
    Finding,
    FindingStatus,
    Severity,
)
from aegiswifi.findings.schemas import (
    EngineResult,
    FindingCreate,
    FindingRead,
    FindingRule,
    FindingSummary,
)


class FindingsEngine:
    """Motor de generación de hallazgos profesionales.

    El motor ejecuta reglas de detección sobre los datos de un engagement
    y produce hallazgos estructurados según la taxonomía del sistema.

    Reglas integradas (minuta §29):
      - WIFI-PSK-001  Contraseña WPA2 recuperable          → CRITICAL
      - WIFI-PSK-002  Handshake WPA2 capturado              → INFO
      - WIFI-WPS-001  WPS PIN habilitado                    → HIGH
      - WIFI-PSK-003  Contraseña débil (ataque por diccionario) → HIGH
      - WIFI-PMF-001  PMF opcional                          → MEDIUM
      - WIFI-PSK-004  Sin protección PMF                    → MEDIUM
    """

    # ------------------------------------------------------------------
    # Reglas integradas
    # ------------------------------------------------------------------

    _BUILTIN_RULES: list[FindingRule] = [
        FindingRule(
            rule_id="WIFI-PSK-001",
            title="Contraseña WPA2 recuperable",
            category="WIFI-PSK",
            severity=Severity.CRITICAL,
            description=(
                "La contraseña WPA2 de la red ha sido recuperada mediante "
                "ataque de cracking fuera de línea. Esto implica que la "
                "contraseña es susceptible a ataques de diccionario o fuerza "
                "bruta."
            ),
            impact=(
                "Un atacante con acceso a la captura del handshake puede "
                "recuperar la contraseña y conectarse a la red, obteniendo "
                "acceso a la infraestructura de red interna."
            ),
            remediation=(
                "Utilizar una contraseña WPA2 de al menos 16 caracteres "
                "aleatorios que incluya mayúsculas, minúsculas, números y "
                "símbolos. Considerar migrar a WPA3 si los dispositivos lo "
                "soportan."
            ),
            conditions=["cracking.result == RECOVERED"],
            confidence=1.0,
        ),
        FindingRule(
            rule_id="WIFI-PSK-002",
            title="Handshake WPA2 capturado",
            category="WIFI-PSK",
            severity=Severity.INFO,
            description=(
                "Se ha capturado un handshake WPA2 válido para la red. "
                "Esto es un paso necesario para realizar ataques de cracking "
                "fuera de línea."
            ),
            impact=(
                "La captura del handshake por sí sola no representa un "
                "riesgo inmediato, pero es el requisito previo para ataques "
                "de cracking de contraseña."
            ),
            remediation=(
                "Asegurar que la contraseña WPA2 sea lo suficientemente "
                "fuerte para resistir ataques de diccionario y fuerza bruta."
            ),
            conditions=["handshake.validated == true"],
            confidence=1.0,
        ),
        FindingRule(
            rule_id="WIFI-PSK-003",
            title="Contraseña WPA2 susceptible a diccionario",
            category="WIFI-PSK",
            severity=Severity.HIGH,
            description=(
                "El handshake WPA2 capturado no fue crackeado, pero la "
                "calidad del handshake permite intentar ataques de diccionario "
                "con wordlists extensas."
            ),
            impact=(
                "Si la contraseña está en una wordlist común, un atacante "
                "podría recuperarla mediante un ataque de diccionario fuera "
                "de línea."
            ),
            remediation=(
                "Verificar que la contraseña no esté presente en wordlists "
                "conocidas como rockyou. Utilizar contraseñas generadas "
                "aleatoriamente."
            ),
            conditions=[
                "handshake.validated == true",
                "cracking.result == EXHAUSTED",
            ],
            confidence=0.8,
        ),
        FindingRule(
            rule_id="WIFI-WPS-001",
            title="WPS PIN habilitado",
            category="WIFI-WPS",
            severity=Severity.HIGH,
            description=(
                "El punto de acceso tiene WPS con autenticación PIN "
                "habilitado. Esto permite ataques de fuerza bruta al PIN "
                "de 8 dígitos, que puede ser recuperado en horas."
            ),
            impact=(
                "Un atacante puede recuperar el PIN WPS en aproximadamente "
                "3-10 horas y obtener la contraseña WPA2 sin necesidad de "
                "cracking, independientemente de la complejidad de la "
                "contraseña."
            ),
            remediation=(
                "Deshabilitar WPS en el punto de acceso. Si no es posible "
                "deshabilitarlo, actualizar el firmware del AP para mitigar "
                "el ataque de desconección PIN."
            ),
            conditions=["network.wps.enabled == true", "network.wps.pin == true"],
            confidence=0.95,
        ),
        FindingRule(
            rule_id="WIFI-PMF-001",
            title="Protected Management Frames (PMF) opcional",
            category="WIFI-PMF",
            severity=Severity.MEDIUM,
            description=(
                "El punto de acceso tiene PMF configurado como opcional. "
                "Las tramas de gestión no están protegidas criptográficamente, "
                "lo que permite ataques de desautenticación y de asociación."
            ),
            impact=(
                "Un atacante puede enviar tramas de desautenticación "
                "forjadas para desconectar clientes de la red, facilitando "
                "ataques de captura de handshake o de evil twin."
            ),
            remediation=(
                "Configurar PMF como obligatorio en el punto de acceso si "
                "todos los clientes lo soportan."
            ),
            conditions=["network.pmf == optional"],
            confidence=0.85,
        ),
        FindingRule(
            rule_id="WIFI-PMF-002",
            title="Protected Management Frames (PMF) no soportado",
            category="WIFI-PMF",
            severity=Severity.MEDIUM,
            description=(
                "El punto de acceso no soporta PMF. Las tramas de gestión "
                "no están protegidas, permitiendo ataques de suplantación "
                "y denegación de servicio."
            ),
            impact=(
                "Un atacante puede realizar ataques de deautenticación, "
                "desasociación y suplantación de tramas de gestión."
            ),
            remediation=(
                "Actualizar el punto de acceso a un modelo que soporte "
                "PMF obligatorio (IEEE 802.11w)."
            ),
            conditions=["network.pmf == not_supported"],
            confidence=0.90,
        ),
    ]

    def __init__(
        self,
        custom_rules: list[FindingRule] | None = None,
    ) -> None:
        self._rules: list[FindingRule] = list(self._BUILTIN_RULES)
        if custom_rules:
            self._rules.extend(custom_rules)

    @property
    def rules(self) -> list[FindingRule]:
        """Retorna todas las reglas registradas."""
        return list(self._rules)

    def get_rule(self, rule_id: str) -> FindingRule | None:
        """Busca una regla por ID."""
        for r in self._rules:
            if r.rule_id == rule_id:
                return r
        return None

    def register_rule(self, rule: FindingRule) -> None:
        """Registra una nueva regla de detección."""
        # Reemplazar si ya existe.
        for i, r in enumerate(self._rules):
            if r.rule_id == rule.rule_id:
                self._rules[i] = rule
                return
        self._rules.append(rule)

    # ------------------------------------------------------------------
    # Ejecución del motor
    # ------------------------------------------------------------------

    def run_for_engagement(
        self,
        engagement: Engagement,
        db_session: Session,
        context: dict[str, Any] | None = None,
    ) -> EngineResult:
        """Ejecuta todas las reglas sobre un engagement y genera hallazgos.

        Args:
            engagement: Engagement a evaluar.
            db_session: Sesión de BD para persistir hallazgos.
            context: Datos contextuales adicionales (handshakes, cracking, etc.).

        Returns:
            :class:`EngineResult` con los hallazgos generados.
        """
        result = EngineResult()
        ctx = context or {}

        for rule in self._rules:
            try:
                if self._evaluate_rule(rule, engagement, db_session, ctx):
                    finding = self._apply_rule(rule, engagement, db_session, ctx)
                    if finding:
                        result.findings.append(finding)
                        result.new_findings += 1
            except Exception as exc:
                result.errors.append(
                    f"Error evaluando regla {rule.rule_id}: {exc}"
                )

        result.total_findings = result.new_findings
        return result

    def run_all(
        self,
        db_session: Session,
        context: dict[str, Any] | None = None,
    ) -> EngineResult:
        """Ejecuta el motor sobre todos los engagements activos."""
        stmt = select(Engagement)
        engagements = list(db_session.scalars(stmt).all())

        combined = EngineResult()
        for eng in engagements:
            eng_result = self.run_for_engagement(eng, db_session, context)
            combined.findings.extend(eng_result.findings)
            combined.new_findings += eng_result.new_findings
            combined.errors.extend(eng_result.errors)

        combined.total_findings = combined.new_findings
        return combined

    # ------------------------------------------------------------------
    # Evaluación de reglas
    # ------------------------------------------------------------------

    def _evaluate_rule(
        self,
        rule: FindingRule,
        engagement: Engagement,
        db_session: Session,
        context: dict[str, Any],
    ) -> bool:
        """Evalúa si una regla debe activarse.

        Implementa las condiciones de las reglas integradas mediante
        lógica programática (no eval dinámico por seguridad).
        """
        for condition in rule.conditions:
            if not self._check_condition(
                condition, engagement, db_session, context
            ):
                return False
        return True

    def _check_condition(
        self,
        condition: str,
        engagement: Engagement,
        db_session: Session,
        context: dict[str, Any],
    ) -> bool:
        """Evalúa una condición individual."""
        condition = condition.strip()

        # WIFI-PSK-001: cracking.result == RECOVERED
        if condition == "cracking.result == RECOVERED":
            return self._has_recovered_password(engagement, db_session)

        # WIFI-PSK-002: handshake.validated == true
        if condition == "handshake.validated == true":
            return self._has_validated_handshake(engagement, db_session)

        # WIFI-PSK-003: handshake.validated == true AND cracking.result == EXHAUSTED
        if condition == "cracking.result == EXHAUSTED":
            return self._has_exhausted_cracking(engagement, db_session)

        # WIFI-WPS-001: network.wps.enabled == true and network.wps.pin == true
        if condition == "network.wps.enabled == true":
            return self._check_wps_enabled(engagement, context)

        if condition == "network.wps.pin == true":
            return self._check_wps_pin(engagement, context)

        # WIFI-PMF-001: network.pmf == optional
        if condition == "network.pmf == optional":
            return self._check_pmf(engagement, context, "optional")

        # WIFI-PMF-002: network.pmf == not_supported
        if condition == "network.pmf == not_supported":
            return self._check_pmf(engagement, context, "not_supported")

        # Condiciones basadas en datos.
        # network.wps.enabled, network.wps.pin, network.pmf se obtienen
        # del contexto pasado por el llamador.
        return self._check_context_condition(condition, context)

    # ------------------------------------------------------------------
    # Verificaciones programáticas
    # ------------------------------------------------------------------

    def _has_recovered_password(
        self, engagement: Engagement, db_session: Session
    ) -> bool:
        """Verifica si hay CrackingJobs con status RECOVERED."""
        stmt = (
            select(CrackingJob)
            .join(Finding, CrackingJob.artifact_id == Finding.id, isouter=True)
            .where(CrackingJob.status == CrackJobStatus.RECOVERED.value)
            .limit(1)
        )
        return db_session.execute(stmt).first() is not None

    def _has_validated_handshake(
        self, engagement: Engagement, db_session: Session
    ) -> bool:
        """Verifica si hay HandshakeArtifacts validados."""
        from aegiswifi.database.models import HandshakeArtifact

        stmt = (
            select(HandshakeArtifact)
            .where(HandshakeArtifact.validated == True)  # noqa: E712
            .limit(1)
        )
        return db_session.execute(stmt).first() is not None

    def _has_exhausted_cracking(
        self, engagement: Engagement, db_session: Session
    ) -> bool:
        """Verifica si hay CrackingJobs con status EXHAUSTED sin RECOVERED."""
        stmt = (
            select(CrackingJob)
            .where(
                CrackingJob.status == CrackJobStatus.EXHAUSTED.value,
                CrackingJob.recovered == False,  # noqa: E712
            )
            .limit(1)
        )
        return db_session.execute(stmt).first() is not None

    @staticmethod
    def _check_wps_enabled(
        engagement: Engagement, context: dict[str, Any]
    ) -> bool:
        """Verifica si WPS está habilitado en el contexto."""
        wps_info = context.get("wps", {})
        return bool(wps_info.get("enabled", False))

    @staticmethod
    def _check_wps_pin(
        engagement: Engagement, context: dict[str, Any]
    ) -> bool:
        """Verifica si el PIN WPS está habilitado."""
        wps_info = context.get("wps", {})
        return bool(wps_info.get("pin", False))

    @staticmethod
    def _check_pmf(
        engagement: Engagement,
        context: dict[str, Any],
        expected: str,
    ) -> bool:
        """Verifica el estado de PMF en el contexto."""
        pmf_info = context.get("pmf", {})
        return str(pmf_info.get("status", "")).lower() == expected

    @staticmethod
    def _check_context_condition(
        condition: str, context: dict[str, Any]
    ) -> bool:
        """Evalúa condiciones basadas en datos del contexto."""
        # Formato: data.key == value
        if " == " not in condition:
            return False

        path, expected = condition.split(" == ", 1)
        expected = expected.strip().strip('"')

        parts = path.strip().split(".")
        if len(parts) < 2 or parts[0] != "data":
            return False

        # Navegar el contexto.
        current: Any = context
        for key in parts:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return False

        return str(current) == expected

    # ------------------------------------------------------------------
    # Aplicación de reglas
    # ------------------------------------------------------------------

    def _apply_rule(
        self,
        rule: FindingRule,
        engagement: Engagement,
        db_session: Session,
        context: dict[str, Any],
    ) -> FindingRead | None:
        """Aplica una regla: crea el hallazgo en BD si no existe duplicado."""
        # Verificar que no exista ya un hallazgo idéntico para este engagement.
        if self._has_existing_finding(rule.rule_id, engagement.id, db_session):
            return None

        # Construir evidencias desde el contexto.
        evidence = self._build_evidence(rule, context)

        # Crear hallazgo en BD.
        finding = Finding(
            engagement_id=engagement.id,
            title=rule.title,
            category=rule.category,
            rule_id=rule.rule_id,
            severity=rule.severity.value,
            confidence=rule.confidence,
            description=rule.description,
            impact=rule.impact,
            evidence=evidence,
            remediation=rule.remediation,
            status=FindingStatus.OPEN.value,
        )
        db_session.add(finding)
        db_session.commit()
        db_session.refresh(finding)

        return FindingRead.model_validate(finding)

    # ------------------------------------------------------------------
    # CRUD findings
    # ------------------------------------------------------------------

    def create_finding(
        self, db_session: Session, data: FindingCreate
    ) -> FindingRead:
        """Crea un hallazgo manualmente."""
        finding = Finding(
            engagement_id=data.engagement_id,
            title=data.title,
            category=data.category,
            rule_id=data.rule_id,
            severity=data.severity.value if isinstance(data.severity, Severity) else data.severity,
            confidence=data.confidence,
            description=data.description,
            impact=data.impact,
            evidence=data.evidence,
            remediation=data.remediation,
            affected_assets=data.affected_assets,
            status=FindingStatus.OPEN.value,
        )
        db_session.add(finding)
        db_session.commit()
        db_session.refresh(finding)
        return FindingRead.model_validate(finding)

    def get_finding(
        self, db_session: Session, finding_id: int
    ) -> FindingRead | None:
        """Obtiene un hallazgo por ID."""
        finding = db_session.get(Finding, finding_id)
        if finding is None:
            return None
        return FindingRead.model_validate(finding)

    def list_findings(
        self,
        db_session: Session,
        engagement_id: int | None = None,
        severity: str | None = None,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[FindingRead]:
        """Lista hallazgos con filtros opcionales."""
        stmt = select(Finding)
        if engagement_id is not None:
            stmt = stmt.where(Finding.engagement_id == engagement_id)
        if severity:
            stmt = stmt.where(Finding.severity == severity.upper())
        if category:
            stmt = stmt.where(Finding.category == category.upper())
        if status:
            stmt = stmt.where(Finding.status == status.upper())
        stmt = stmt.order_by(Finding.id.desc()).limit(limit)
        return [FindingRead.model_validate(f) for f in db_session.scalars(stmt).all()]

    def update_finding(
        self,
        db_session: Session,
        finding_id: int,
        data: dict[str, Any],
    ) -> FindingRead | None:
        """Actualiza un hallazgo."""
        finding = db_session.get(Finding, finding_id)
        if finding is None:
            return None

        for key, value in data.items():
            if hasattr(finding, key) and value is not None:
                if isinstance(value, Enum):
                    setattr(finding, key, value.value)
                else:
                    setattr(finding, key, value)

        db_session.commit()
        db_session.refresh(finding)
        return FindingRead.model_validate(finding)

    def delete_finding(
        self, db_session: Session, finding_id: int
    ) -> bool:
        """Elimina un hallazgo."""
        finding = db_session.get(Finding, finding_id)
        if finding is None:
            return False
        db_session.delete(finding)
        db_session.commit()
        return True

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(
        self, db_session: Session, engagement_id: int
    ) -> FindingSummary:
        """Genera un resumen de hallazgos para un engagement."""
        findings = self.list_findings(
            db_session, engagement_id=engagement_id, limit=500
        )

        summary = FindingSummary(engagement_id=engagement_id, total=len(findings))

        for f in findings:
            summary.by_severity[f.severity] = summary.by_severity.get(f.severity, 0) + 1
            summary.by_category[f.category] = summary.by_category.get(f.category, 0) + 1
            summary.by_status[f.status] = summary.by_status.get(f.status, 0) + 1

            if f.status == "OPEN":
                if f.severity == "CRITICAL":
                    summary.open_critical += 1
                elif f.severity == "HIGH":
                    summary.open_high += 1
                elif f.severity == "MEDIUM":
                    summary.open_medium += 1
                elif f.severity == "LOW":
                    summary.open_low += 1
                elif f.severity == "INFO":
                    summary.open_info += 1

        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _has_existing_finding(
        self, rule_id: str, engagement_id: int, db_session: Session
    ) -> bool:
        """Verifica si ya existe un hallazgo generado por esta regla."""
        stmt = select(Finding).where(
            Finding.rule_id == rule_id,
            Finding.engagement_id == engagement_id,
        )
        return db_session.execute(stmt).first() is not None

    def _build_evidence(
        self,
        rule: FindingRule,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Construye el bloque de evidencia para un hallazgo.

        Incluye metadatos contextuales relevantes según la regla.
        """
        evidence: dict[str, Any] = {
            "rule_id": rule.rule_id,
            "generated_by": "findings_engine",
        }

        # Incluir contexto relevante.
        for key in ("ssid", "bssid", "channel", "cracking", "handshake"):
            if key in context:
                evidence[key] = context[key]

        return evidence


# Singleton.
_engine: FindingsEngine | None = None


def get_findings_engine() -> FindingsEngine:
    """Retorna el singleton del motor de hallazgos."""
    global _engine
    if _engine is None:
        _engine = FindingsEngine()
    return _engine
