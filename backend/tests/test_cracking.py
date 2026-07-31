"""Tests del módulo de cracking con Hashcat (minuta §18, §28).

Cubre:
  - Schemas: AttackMode, AttackStage, CrackingPlan, CrackingProgress, CrackingResult,
    DictionaryInfo, HashInfo, RuleInfo, CrackingJobRead.
  - DictionaryManager: scan, get, count_lines.
  - RulesManager: scan, get, count_rules.
  - CrackingPlanner: build_plan, build_profile_plan, _pick_preferred_*.
  - CrackingService: validate_artifact, create/get/list/cancel job, get_hash_info.
  - HashcatAdapter: build_command, parse_output, collect_results.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegiswifi.cracking.schemas import (
    AttackMode,
    AttackStage,
    CrackingJobRead,
    CrackingPlan,
    CrackingProgress,
    CrackingResult,
    DictionaryInfo,
    HashInfo,
    RuleInfo,
)
from aegiswifi.database.models import (
    CrackJobStatus,
    CrackingJob,
    HandshakeArtifact,
    HandshakeQuality,
)


# ===================================================================
# Schema Tests
# ===================================================================


class TestAttackMode:
    def test_values(self):
        assert AttackMode.DICTIONARY.value == "dictionary"
        assert AttackMode.COMBIATOR.value == "combinator"
        assert AttackMode.MASK.value == "mask"
        assert AttackMode.BRUTE_FORCE.value == "brute_force"
        assert AttackMode.PRINCE.value == "prince"
        assert AttackMode.RULE_BASED.value == "rule_based"

    def test_all_members_present(self):
        assert len(AttackMode) == 8


class TestAttackStage:
    def test_defaults(self):
        stage = AttackStage(mode=AttackMode.DICTIONARY)
        assert stage.mode == AttackMode.DICTIONARY
        assert stage.dictionary_path is None
        assert stage.timeout_seconds is None
        assert stage.extra_args == []

    def test_full_stage(self):
        stage = AttackStage(
            mode=AttackMode.RULE_BASED,
            dictionary_path="/dicts/rockyou.txt",
            rules_path="/rules/best64.rule",
            timeout_seconds=300,
            extra_args=["--slow-candidates"],
        )
        assert stage.dictionary_path == "/dicts/rockyou.txt"
        assert stage.rules_path == "/rules/best64.rule"

    def test_rejects_bad_timeout(self):
        with pytest.raises(Exception):
            AttackStage(mode=AttackMode.DICTIONARY, timeout_seconds=10)


class TestCrackingPlan:
    def test_minimal_plan(self):
        plan = CrackingPlan(job_id=1, artifact_id=1, hash_file_path="/tmp/test.22000")
        assert plan.job_id == 1
        assert plan.artifact_id == 1
        assert plan.stages == []
        assert plan.max_total_time == 3600
        assert plan.hash_mode == 22000

    def test_plan_with_stages(self):
        stages = [AttackStage(mode=AttackMode.DICTIONARY), AttackStage(mode=AttackMode.MASK)]
        plan = CrackingPlan(
            job_id=2,
            artifact_id=3,
            hash_file_path="/tmp/h.22000",
            stages=stages,
            max_total_time=1800,
        )
        assert len(plan.stages) == 2
        assert plan.stages[0].mode == AttackMode.DICTIONARY

    def test_max_total_time_bounds(self):
        with pytest.raises(Exception):
            CrackingPlan(job_id=1, artifact_id=1, hash_file_path="x", max_total_time=10)
        with pytest.raises(Exception):
            CrackingPlan(job_id=1, artifact_id=1, hash_file_path="x", max_total_time=90000)


class TestCrackingProgress:
    def test_defaults(self):
        p = CrackingProgress(job_id=1, status="Running")
        assert p.speed == 0
        assert p.recovered == 0
        assert p.progress_denom == 0.0
        assert p.timestamp is not None

    def test_full_progress(self):
        p = CrackingProgress(
            job_id=1,
            status="Running",
            progress_denom=0.5,
            speed=50000,
            recovered=1,
            hashes_total=1000,
        )
        assert p.progress_denom == 0.5
        assert p.speed == 50000
        assert p.recovered == 1


class TestCrackingResult:
    def test_defaults(self):
        r = CrackingResult(job_id=1)
        assert r.cracked is False
        assert r.password is None
        assert r.stages_executed == 0

    def test_cracked_result(self):
        r = CrackingResult(
            job_id=1,
            cracked=True,
            password="secret123",
            mode_used=AttackMode.DICTIONARY,
            stages_executed=2,
            stages_total=6,
        )
        assert r.password == "secret123"
        assert r.mode_used == AttackMode.DICTIONARY


class TestDictionaryInfo:
    def test_defaults(self):
        info = DictionaryInfo(path="/dicts/rockyou.txt", name="rockyou.txt")
        assert info.size_bytes == 0
        assert info.line_count is None
        assert info.encoding == "utf-8"
        assert info.is_sorted is False

    def test_full(self):
        info = DictionaryInfo(
            path="/d/rockyou.txt",
            name="rockyou.txt",
            size_bytes=1_000_000,
            line_count=100_000,
            is_sorted=True,
        )
        assert info.size_bytes == 1_000_000


class TestHashInfo:
    def test_defaults(self):
        info = HashInfo(artifact_id=1, hash_file_path="/tmp/x.22000")
        assert info.hash_count == 1
        assert info.kind == "eapol"

    def test_full(self):
        info = HashInfo(
            artifact_id=1,
            hash_file_path="/tmp/x.22000",
            ssid="TestNet",
            bssid="AA:BB:CC:DD:EE:FF",
            kind="pmkid",
        )
        assert info.ssid == "TestNet"


class TestRuleInfo:
    def test_defaults(self):
        info = RuleInfo(path="/rules/best64.rule", name="best64.rule")
        assert info.size_bytes == 0
        assert info.rule_count is None


class TestCrackingJobRead:
    def test_from_attributes(self, db_session):
        """CrackingJobRead puede construirse desde un modelo SQLAlchemy."""
        job = CrackingJob(strategy="dictionary", status=CrackJobStatus.CREATED)
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        read = CrackingJobRead.model_validate(job)
        assert read.id == job.id
        assert read.strategy == "dictionary"
        assert read.status == "CREATED"
        assert read.recovered is False


# ===================================================================
# DictionaryManager Tests
# ===================================================================


class TestDictionaryManager:
    def test_scan_all_empty_dir(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        manager = DictionaryManager(extra_dirs=[tmp_path])
        results = manager.scan_all()
        assert results == []

    def test_scan_finds_wordlists(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        (tmp_path / "rockyou.txt").write_text("pass1\npass2\n")
        (tmp_path / "custom.lst").write_text("word1\nword2\n")
        (tmp_path / "not_a_wordlist.pdf").write_text("junk")

        manager = DictionaryManager(extra_dirs=[tmp_path])
        results = manager.scan_all()
        assert len(results) == 2
        names = {r.name for r in results}
        assert "rockyou.txt" in names
        assert "custom.lst" in names
        assert "not_a_wordlist.pdf" not in names

    def test_get_existing(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        wordlist = tmp_path / "words.txt"
        wordlist.write_text("a\nb\nc\n")
        manager = DictionaryManager(extra_dirs=[tmp_path])
        manager.scan_all()
        info = manager.get(str(wordlist))
        assert info is not None
        assert info.name == "words.txt"

    def test_get_nonexistent(self):
        from aegiswifi.cracking.dictionary import DictionaryManager

        manager = DictionaryManager(extra_dirs=[])
        assert manager.get("/nonexistent/path") is None

    def test_count_lines_text(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        wordlist = tmp_path / "words.txt"
        wordlist.write_text("line1\nline2\nline3\n")
        manager = DictionaryManager()
        count = manager.count_lines(str(wordlist))
        assert count == 3

    def test_count_lines_text_no_trailing_newline(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        wordlist = tmp_path / "words.txt"
        wordlist.write_text("line1\nline2")
        manager = DictionaryManager()
        count = manager.count_lines(str(wordlist))
        assert count == 2

    def test_count_lines_nonexistent(self):
        from aegiswifi.cracking.dictionary import DictionaryManager

        manager = DictionaryManager(extra_dirs=[])
        assert manager.count_lines("/nonexistent") is None

    def test_rockyou_marked_sorted(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        (tmp_path / "rockyou.txt").write_text("a\nb\nc\n")
        manager = DictionaryManager(extra_dirs=[tmp_path])
        results = manager.scan_all()
        rockyou = [r for r in results if "rockyou" in r.name.lower()]
        if rockyou:
            assert rockyou[0].is_sorted is True

    def test_scan_caching(self, tmp_path):
        from aegiswifi.cracking.dictionary import DictionaryManager

        (tmp_path / "words.txt").write_text("a\n")
        manager = DictionaryManager(extra_dirs=[tmp_path])
        r1 = manager.scan_all()
        # Agregar otro archivo y verificar que scan_all() usa caché.
        (tmp_path / "more.txt").write_text("b\n")
        r2 = manager.scan_all()
        assert len(r1) == len(r2)  # resultado cacheado

        r3 = manager.scan_all(force=True)
        assert len(r3) == 2  # re-escanneado


# ===================================================================
# RulesManager Tests
# ===================================================================


class TestRulesManager:
    def test_scan_all_empty_dir(self, tmp_path):
        from aegiswifi.cracking.rules import RulesManager

        manager = RulesManager(extra_dirs=[tmp_path])
        results = manager.scan_all()
        assert results == []

    def test_scan_finds_rules(self, tmp_path):
        from aegiswifi.cracking.rules import RulesManager

        (tmp_path / "best64.rule").write_text(": $1 $! $@\n")
        (tmp_path / "d3ad.rule").write_text("$[ $]\n")
        (tmp_path / "readme.txt").write_text("not a rule")

        manager = RulesManager(extra_dirs=[tmp_path])
        results = manager.scan_all()
        assert len(results) == 2
        names = {r.name for r in results}
        assert "best64.rule" in names
        assert "d3ad.rule" in names

    def test_get_existing(self, tmp_path):
        from aegiswifi.cracking.rules import RulesManager

        rule_file = tmp_path / "test.rule"
        rule_file.write_text(": $1\n")
        manager = RulesManager(extra_dirs=[tmp_path])
        manager.scan_all()
        info = manager.get(str(rule_file))
        assert info is not None
        assert info.name == "test.rule"

    def test_get_nonexistent(self):
        from aegiswifi.cracking.rules import RulesManager

        manager = RulesManager(extra_dirs=[])
        assert manager.get("/nonexistent.rule") is None

    def test_count_rules(self, tmp_path):
        from aegiswifi.cracking.rules import RulesManager

        rule_file = tmp_path / "test.rule"
        rule_file.write_text(": $1\n$[ $]\n# comment\n\n: $!\n")
        manager = RulesManager()
        count = manager.count_rules(str(rule_file))
        assert count == 3  # excluye comentarios y líneas vacías

    def test_count_rules_nonexistent(self):
        from aegiswifi.cracking.rules import RulesManager

        manager = RulesManager(extra_dirs=[])
        assert manager.count_rules("/nonexistent") is None

    def test_scan_caching(self, tmp_path):
        from aegiswifi.cracking.rules import RulesManager

        (tmp_path / "a.rule").write_text(":\n")
        manager = RulesManager(extra_dirs=[tmp_path])
        r1 = manager.scan_all()
        (tmp_path / "b.rule").write_text(":\n")
        r2 = manager.scan_all()
        assert len(r1) == len(r2)  # cacheado
        r3 = manager.scan_all(force=True)
        assert len(r3) == 2  # re-escanneado


# ===================================================================
# CrackingPlanner Tests
# ===================================================================


class TestCrackingPlanner:
    def _make_manager_with_dicts(self, tmp_path, names=None):
        from aegiswifi.cracking.dictionary import DictionaryManager

        if names is None:
            names = ["rockyou.txt"]
        for name in names:
            (tmp_path / name).write_text("a\nb\nc\n")
        return DictionaryManager(extra_dirs=[tmp_path])

    def _make_manager_with_rules(self, tmp_path, names=None):
        from aegiswifi.cracking.rules import RulesManager

        if names is None:
            names = ["best64.rule"]
        for name in names:
            (tmp_path / name).write_text(": $1\n")
        return RulesManager(extra_dirs=[tmp_path])

    def test_build_plan_with_defaults(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = self._make_manager_with_dicts(tmp_path)
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        plan = planner.build_plan(
            job_id=1,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
        )

        assert plan.job_id == 1
        assert plan.hash_mode == 22000
        assert len(plan.stages) > 0
        # Primera etapa debe ser dictionary.
        assert plan.stages[0].mode == AttackMode.DICTIONARY

    def test_build_plan_skips_modes(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = self._make_manager_with_dicts(tmp_path, ["rockyou.txt", "other.txt"])
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        plan = planner.build_plan(
            job_id=1,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
            skip_modes=[AttackMode.DICTIONARY, AttackMode.MASK],
        )

        for stage in plan.stages:
            assert stage.mode != AttackMode.DICTIONARY
            assert stage.mode != AttackMode.MASK

    def test_build_plan_with_preferred_dict(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        (tmp_path / "wordlist.txt").write_text("a\nb\nc\n")
        (tmp_path / "rockyou.txt").write_text("x\ny\nz\n")
        dm = self._make_manager_with_dicts(tmp_path, ["wordlist.txt", "rockyou.txt"])
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        plan = planner.build_plan(
            job_id=1,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
            preferred_dicts=[str(tmp_path / "wordlist.txt")],
        )

        if plan.stages:
            wordlist_stage = plan.stages[0]
            assert wordlist_stage.dictionary_path is not None
            assert "rockyou" not in wordlist_stage.dictionary_path

    def test_build_plan_no_dicts(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = self._make_manager_with_dicts(tmp_path, [])
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        plan = planner.build_plan(job_id=1, artifact_id=1, hash_file_path="/tmp/h.22000")
        # Sin diccionarios, no se puede construir stages de diccionario.
        assert len(plan.stages) <= 1  # solo máscara

    def test_build_profile_plan_movistar(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = self._make_manager_with_dicts(tmp_path)
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        plan = planner.build_plan(
            job_id=1,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
        )

        # Usar build_plan normal (build_profile_plan agrega stages extras).
        profile_plan = planner.build_profile_plan(
            job_id=2,
            artifact_id=2,
            hash_file_path="/tmp/h.22000",
            essid="MOVISTAR_ABCD",
        )
        assert len(profile_plan.stages) >= len(plan.stages)

    def test_pick_preferred_rockyou(self, tmp_path):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = self._make_manager_with_dicts(tmp_path, ["rockyou.txt", "other.txt"])
        rm = self._make_manager_with_rules(tmp_path)
        planner = CrackingPlanner(dm, rm)

        path = planner._pick_preferred_dict(
            [DictionaryInfo(path="/dicts/other.txt", name="other.txt",
                            size_bytes=100),
             DictionaryInfo(path="/dicts/rockyou.txt", name="rockyou.txt",
                            size_bytes=200)]
        )
        assert path is not None
        assert "rockyou" in path

    def test_pick_preferred_rule_best64(self):
        from aegiswifi.cracking.planner import CrackingPlanner

        dm = MagicMock()
        rm = MagicMock()
        planner = CrackingPlanner(dm, rm)

        path = planner._pick_preferred_rule(
            [RuleInfo(path="/rules/complex.rule", name="complex.rule",
                      size_bytes=10),
             RuleInfo(path="/rules/best64.rule", name="best64.rule",
                      size_bytes=5)]
        )
        assert path is not None
        assert "best64" in path


# ===================================================================
# CrackingService Tests
# ===================================================================


class TestCrackingService:
    def test_validate_artifact_valid(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.GOOD,
            hash22000_path="/tmp/test.22000",
        )
        db_session.add(artifact)
        db_session.commit()

        service = CrackingService()
        service.validate_artifact(artifact)

    def test_validate_artifact_not_validated(self):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=False,
            quality=HandshakeQuality.GOOD,
            hash22000_path="/tmp/test.22000",
        )
        service = CrackingService()
        with pytest.raises(ValueError, match="no está validado"):
            service.validate_artifact(artifact)

    def test_validate_artifact_poor_quality(self):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.INVALID,
            hash22000_path="/tmp/test.22000",
        )
        service = CrackingService()
        with pytest.raises(ValueError, match="calidad"):
            service.validate_artifact(artifact)

    def test_validate_artifact_no_hashfile(self):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.EXCELLENT,
            hash22000_path=None,
        )
        service = CrackingService()
        with pytest.raises(ValueError, match="archivo .22000"):
            service.validate_artifact(artifact)

    def test_create_cracking_job(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(validated=True, quality=HandshakeQuality.GOOD,
                                      hash22000_path="/tmp/x.22000")
        db_session.add(artifact)
        db_session.commit()

        service = CrackingService(event_bus=MagicMock())
        job = service.create_cracking_job(
            db_session, artifact_id=artifact.id, strategy="dictionary"
        )
        assert job.id is not None
        assert job.strategy == "dictionary"
        assert job.status == CrackJobStatus.CREATED.value

    def test_get_job_found(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        job = CrackingJob(strategy="mask", status=CrackJobStatus.CREATED)
        db_session.add(job)
        db_session.commit()

        service = CrackingService()
        found = service.get_job(db_session, job.id)
        assert found is not None
        assert found.strategy == "mask"

    def test_get_job_not_found(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        service = CrackingService()
        assert service.get_job(db_session, 99999) is None

    def test_list_jobs(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        db_session.add_all([
            CrackingJob(strategy="a", status=CrackJobStatus.CREATED),
            CrackingJob(strategy="b", status=CrackJobStatus.RUNNING),
        ])
        db_session.commit()

        service = CrackingService()
        jobs = service.list_jobs(db_session)
        assert len(jobs) >= 2

    def test_cancel_job_created(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        job = CrackingJob(strategy="dictionary", status=CrackJobStatus.CREATED)
        db_session.add(job)
        db_session.commit()

        service = CrackingService(event_bus=MagicMock())
        cancelled = service.cancel_job(db_session, job.id)
        assert cancelled is not None
        assert cancelled.status == CrackJobStatus.CANCELLED.value

    def test_cancel_job_not_found(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        service = CrackingService()
        assert service.cancel_job(db_session, 99999) is None

    def test_get_hash_info(self, db_session, tmp_path):
        from aegiswifi.cracking.service import CrackingService

        hash_file = tmp_path / "test.22000"
        hash_file.write_text("hash1:hash2:TestNet:AA:BB:CC:DD:EE:FF\n")

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.GOOD,
            hash22000_path=str(hash_file),
        )
        db_session.add(artifact)
        db_session.commit()

        service = CrackingService()
        info = service.get_hash_info(artifact)
        assert info is not None
        assert info.ssid == "TestNet"
        assert info.bssid == "AA:BB:CC:DD:EE:FF"

    def test_get_hash_info_no_file(self):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.GOOD,
            hash22000_path=None,
        )
        service = CrackingService()
        assert service.get_hash_info(artifact) is None

    def test_get_hash_info_file_not_found(self, db_session):
        from aegiswifi.cracking.service import CrackingService

        artifact = HandshakeArtifact(
            validated=True,
            quality=HandshakeQuality.GOOD,
            hash22000_path="/nonexistent/file.22000",
        )
        db_session.add(artifact)
        db_session.commit()

        service = CrackingService()
        assert service.get_hash_info(artifact) is None

    @pytest.mark.asyncio
    async def test_execute_plan_success(self, db_session):
        """Ejecución de plan: adaptador reporta cracked."""
        from aegiswifi.cracking.service import CrackingService

        job = CrackingJob(strategy="dictionary", status=CrackJobStatus.CREATED)
        db_session.add(job)
        db_session.commit()

        plan = CrackingPlan(
            job_id=job.id,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
            stages=[AttackStage(mode=AttackMode.DICTIONARY, dictionary_path="/dicts/rockyou.txt")],
        )

        # Mockear get_adapter para evitar hashcat real.
        mock_adapter = AsyncMock()
        mock_adapter.start = AsyncMock(return_value={"exit_code": 0, "log_path": "/tmp/log"})
        mock_adapter.collect_results = AsyncMock(return_value={
            "cracked": True,
            "password": "secret123",
            "exit_code": 0,
            "peak_speed": 50000,
        })

        service = CrackingService(event_bus=MagicMock())

        with patch("aegiswifi.cracking.service.get_adapter", return_value=mock_adapter):
            result = await service._execute_with_session(
                plan, engagement_id=1, session=db_session
            )

        assert result.cracked is True
        assert result.password == "secret123"
        assert result.stages_executed == 1

        # Verificar que el job se actualizó en BD.
        db_session.refresh(job)
        assert job.recovered is True

    @pytest.mark.asyncio
    async def test_execute_plan_exhausted(self, db_session):
        """Ejecución de plan donde no se crackea la clave."""
        from aegiswifi.cracking.service import CrackingService, get_cracking_service

        job = CrackingJob(strategy="dictionary", status=CrackJobStatus.CREATED)
        db_session.add(job)
        db_session.commit()

        plan = CrackingPlan(
            job_id=job.id,
            artifact_id=1,
            hash_file_path="/tmp/h.22000",
            stages=[AttackStage(mode=AttackMode.DICTIONARY, dictionary_path="/dicts/rockyou.txt")],
        )

        mock_adapter = AsyncMock()
        mock_adapter.start = AsyncMock(return_value={"exit_code": 0})
        mock_adapter.collect_results = AsyncMock(return_value={
            "cracked": False,
            "password": None,
            "exit_code": 0,
            "peak_speed": 0,
        })

        service = CrackingService(event_bus=MagicMock())

        with patch("aegiswifi.cracking.service.get_adapter", return_value=mock_adapter):
            result = await service._execute_with_session(
                plan, engagement_id=1, session=db_session
            )

        assert result.cracked is False
        assert result.password is None
        assert result.stages_executed == 1

        db_session.refresh(job)
        assert job.recovered is False


# ===================================================================
# HashcatAdapter Tests
# ===================================================================


class TestHashcatAdapter:
    def _make_adapter(self):
        from aegiswifi.cracking.hashcat_adapter import HashcatAdapter

        config = MagicMock()
        config.log_dir = "/tmp/logs"
        return HashcatAdapter(
            job_id=1,
            engagement_id=1,
            event_bus=MagicMock(),
            config=config,
        )

    @pytest.mark.asyncio
    async def test_build_command_minimal(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({"hash_file": "/tmp/h.22000"})
        assert "hashcat" in cmd
        assert "-m" in cmd
        assert "22000" in cmd
        assert "-a" in cmd
        assert "0" in cmd
        assert "/tmp/h.22000" in cmd
        assert "--status" in cmd
        assert "--status-json" in cmd

    @pytest.mark.asyncio
    async def test_build_command_dictionary(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "dictionary": "/dicts/rockyou.txt",
        })
        assert "/dicts/rockyou.txt" in cmd

    @pytest.mark.asyncio
    async def test_build_command_mask(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "attack_mode": AttackMode.MASK,
            "mask": "?l?l?l?l",
        })
        assert "-a" in cmd
        idx = cmd.index("-a")
        assert cmd[idx + 1] == "3"
        assert "?l?l?l?l" in cmd

    @pytest.mark.asyncio
    async def test_build_command_with_rules(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "dictionary": "/dicts/rockyou.txt",
            "rules": "/rules/best64.rule",
        })
        assert "-r" in cmd
        idx = cmd.index("-r")
        assert cmd[idx + 1] == "/rules/best64.rule"

    @pytest.mark.asyncio
    async def test_build_command_opencl_device(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "opencl_device": "1",
        })
        assert "--opencl-device" in cmd
        idx = cmd.index("--opencl-device")
        assert cmd[idx + 1] == "1"

    @pytest.mark.asyncio
    async def test_build_command_extra_args(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "extra_args": ["--slow-candidates", "--optimized-kernel-enable"],
        })
        assert "--slow-candidates" in cmd

    @pytest.mark.asyncio
    async def test_build_command_workload(self):
        adapter = self._make_adapter()
        cmd = await adapter.build_command({
            "hash_file": "/tmp/h.22000",
            "workload_profile": 4,
        })
        assert "-w" in cmd
        idx = cmd.index("-w")
        assert cmd[idx + 1] == "4"

    @pytest.mark.asyncio
    async def test_parse_output_returns_none_for_empty(self):
        adapter = self._make_adapter()
        result = await adapter.parse_output("")
        assert result is None

    @pytest.mark.asyncio
    async def test_parse_output_status_json(self):
        adapter = self._make_adapter()
        line = '{"status":"Running","progress":{"guessBase":1000,"guessMod":500,"curHashes":50,"totalHashes":200},'
        line += '"speed":50000,"recovered":0,"rejected":2}'
        result = await adapter.parse_output(line)
        assert result is not None
        assert result["event"] == "status"
        assert result["status"] == "Running"
        assert result["progress"] == 0.5
        assert result["speed"] == 50000

    @pytest.mark.asyncio
    async def test_parse_output_status_json_accumulates(self):
        adapter = self._make_adapter()
        line = '{"status":"Running","progress":{"guessBase":2000,"guessMod":1000,"curHashes":100},"speed":45000}'
        await adapter.parse_output(line)
        assert len(adapter._progress) == 1
        assert adapter._progress[0].progress_denom == 0.5
        assert adapter._progress[0].speed == 45000

        line2 = '{"status":"Exhausted","progress":{"guessBase":2000,"guessMod":2000,"curHashes":200},"speed":0}'
        await adapter.parse_output(line2)
        assert len(adapter._progress) == 2

    @pytest.mark.asyncio
    async def test_parse_output_password_cracked(self):
        adapter = self._make_adapter()
        line = "a" * 40 + ":secret123"
        result = await adapter.parse_output(line)
        assert result is not None
        assert result["event"] == "password_cracked"
        assert result["password"] == "secret123"
        assert adapter._cracked_password == "secret123"

    @pytest.mark.asyncio
    async def test_parse_output_hashcat_log(self):
        adapter = self._make_adapter()
        for prefix in ("Session.Name:", "Status:", "Speed.", "Progress."):
            result = await adapter.parse_output(prefix + " test value")
            assert result is not None
            assert result["event"] == "hashcat_log"

    @pytest.mark.asyncio
    async def test_collect_results_cracked(self):
        adapter = self._make_adapter()
        adapter._raw_result = {"exit_code": 0, "log_path": "/tmp/log"}
        adapter._cracked_password = "found_it"
        adapter._progress = [
            CrackingProgress(job_id=1, status="Running", speed=50000),
            CrackingProgress(job_id=1, status="Running", speed=60000),
        ]
        adapter._progress[0].speed = 50000
        adapter._progress[1].speed = 60000

        result = await adapter.collect_results()
        assert result["cracked"] is True
        assert result["password"] == "found_it"
        assert result["peak_speed"] == 60000

    @pytest.mark.asyncio
    async def test_collect_results_not_cracked(self):
        adapter = self._make_adapter()
        adapter._raw_result = {"exit_code": 0}
        adapter._cracked_password = None

        result = await adapter.collect_results()
        assert result["cracked"] is False
        assert result["password"] is None


# ===================================================================
# Singleton Tests
# ===================================================================


class TestCrackingServiceSingleton:
    def test_get_cracking_service_returns_singleton(self):
        from aegiswifi.cracking.service import get_cracking_service
        import aegiswifi.cracking.service as srv

        # Reset para test.
        srv._cracking_service = None

        s1 = get_cracking_service()
        s2 = get_cracking_service()
        assert s1 is s2
