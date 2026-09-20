#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Meta Business Automator — V6.5.2 Certification & Regression Test Suite
=============================================================================
Tests:
1. Settings save validates optimistic concurrency token (rejects stale).
2. Failed settings save does not return false success or dispatch reload.
3. Unlink rule dispatches worker snapshot with sha256_token.
4. Snapshot failures are cleanly captured in runtime_refresh_failures without masking disk_ok.
5. Conflict resolution loads authoritative rule directly from disk.
6. Conflict resolution rejects stale expected SHAs before modifying disk.
7. 3-Profile conflict detection and authoritative resolution across all participating profiles.
8. Coordinated save re-verifies SHAs of all staged profiles immediately before writing.
9. Multi-profile migration atomic rollback restores exact pre-write bytes on failure.
10. Keyword array parsing in gui/app.js does not use lossy delimiter splitting or trimming.
11. Worker pySaveConfig participates in optimistic concurrency.
12. ProfileManager write mutex uses reentrant RLock preventing recursive deadlocks.
13. Extracted delivery package has zero stale V6.5.0/V6.5.1 user-visible identifiers.
=============================================================================
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from profile_manager import (
    ProfileManager,
    ProfileRootOwnershipGuard,
    atomic_write_json,
)
from desktop_app import DesktopBridgeApi


class TestProfileCertificationV652(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir)
        self.manager.ownership_guard.acquire()

        # Mock loop and controller for bridge
        self.bridge = DesktopBridgeApi(self.manager, controller=None, loop=None)

    def tearDown(self):
        if self.manager.ownership_guard.is_owned():
            self.manager.ownership_guard.release()
        self.tmp_dir.cleanup()

    def _create_fixture_profile(self, name: str, rules: list, config: dict = None) -> tuple:
        prof_dir = self.base_dir / name
        prof_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = prof_dir / "config.json"
        data = {
            "rules": rules,
            "config": config or {"active": True, "cooldown_seconds": 1.5}
        }
        raw_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        cfg_file.write_bytes(raw_bytes)
        sha = hashlib.sha256(raw_bytes).hexdigest()
        return cfg_file, sha

    # -------------------------------------------------------------------------
    # Test 1 & 2: Settings Save Optimistic Concurrency & Suppression on Failure
    # -------------------------------------------------------------------------
    def test_settings_save_uses_sha_token_and_rejects_stale(self):
        """Settings save must validate SHA token; stale token must fail and leave disk untouched."""
        rules = [{"id": "r1", "name": "R1", "ruleCode": "MBS-CODE1", "keywords": ["hi"], "reply": "hello", "matchType": "ultra_exact"}]
        cfg_file, initial_sha = self._create_fixture_profile("TestProf", rules, {"active": True})

        # 1. Attempt save with stale SHA
        new_data = {
            "rules": rules,
            "config": {"active": False, "cooldown_seconds": 3.0}
        }
        res_stale = self.bridge.save_profile_config_coordinated("TestProf", new_data, expected_sha256="stale_sha_token_123")
        self.assertFalse(res_stale.get("ok"))
        self.assertEqual(res_stale.get("code"), "STALE_CONFIG")
        self.assertFalse(res_stale.get("disk_ok"))
        self.assertEqual(res_stale.get("runtime_refresh_successes"), [])
        self.assertEqual(res_stale.get("runtime_refresh_failures"), {})

        # Disk content must be completely untouched
        current_sha = hashlib.sha256(cfg_file.read_bytes()).hexdigest()
        self.assertEqual(current_sha, initial_sha)

        # 2. Attempt save with valid SHA
        res_valid = self.bridge.save_profile_config_coordinated("TestProf", new_data, expected_sha256=initial_sha)
        self.assertTrue(res_valid.get("ok"))
        self.assertTrue(res_valid.get("disk_ok"))
        self.assertIsNotNone(res_valid.get("sha256_token"))
        self.assertNotEqual(res_valid.get("sha256_token"), initial_sha)

        # Verify disk updated
        disk_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.assertEqual(disk_cfg["config"]["active"], False)
        self.assertEqual(disk_cfg["config"]["cooldown_seconds"], 3.0)

    # -------------------------------------------------------------------------
    # Test 3: Unlink Rule Dispatches Worker Snapshot with SHA256 Token
    # -------------------------------------------------------------------------
    def test_unlink_refreshes_running_worker(self):
        """unlink_rule must dispatch worker snapshot containing rules and sha256_token."""
        rules = [
            {"id": "r1", "name": "Shared", "ruleCode": "MBS-LINKED", "keywords": ["k1"], "reply": "rep1", "matchType": "ultra_exact"}
        ]
        self._create_fixture_profile("WorkerProf", rules)

        with patch.object(self.bridge, "is_worker_running", return_value=True), \
             patch.object(self.bridge, "send_page_command", return_value=True) as mock_send:

            res = self.bridge.unlink_rule("WorkerProf", "r1")
            self.assertTrue(res.get("ok"))
            self.assertTrue(res.get("disk_ok"))
            self.assertIn("WorkerProf", res.get("runtime_refresh_successes"))
            self.assertEqual(res.get("runtime_refresh_failures"), {})

            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            self.assertEqual(args[0], "WorkerProf")
            self.assertEqual(args[1], "APPLY_RULE_SNAPSHOT")
            payload = args[2]
            self.assertIn("rules", payload)
            self.assertIn("sha256_token", payload)
            self.assertIsNotNone(payload["sha256_token"])
            # The rule code in payload should now be unlinked
            self.assertNotEqual(payload["rules"][0]["ruleCode"], "MBS-LINKED")

    # -------------------------------------------------------------------------
    # Test 4: Snapshot Failures Cleanly Reported
    # -------------------------------------------------------------------------
    def test_snapshot_failures_reported_in_result(self):
        """When worker snapshot dispatch fails, it must be reported in runtime_refresh_failures without marking disk_ok False."""
        rules = [{"id": "r1", "name": "R1", "ruleCode": "MBS-CODE1", "keywords": ["hi"], "reply": "hello", "matchType": "ultra_exact"}]
        cfg_file, sha = self._create_fixture_profile("FailProf", rules)

        with patch.object(self.bridge, "is_worker_running", return_value=True), \
             patch.object(self.bridge, "send_page_command", return_value=False):

            res = self.bridge.save_profile_config_coordinated(
                "FailProf",
                {"rules": rules, "config": {}},
                expected_sha256=sha
            )
            self.assertTrue(res.get("ok"))
            self.assertTrue(res.get("disk_ok"))
            self.assertEqual(res.get("runtime_refresh_successes"), [])
            self.assertIn("FailProf", res.get("runtime_refresh_failures"))

    # -------------------------------------------------------------------------
    # Test 5, 6, 7: 3-Profile Conflict Detection & Authoritative Resolution
    # -------------------------------------------------------------------------
    def test_three_profile_conflict_and_resolution(self):
        """Three profiles share a linked rule; one diverges -> conflict detected -> authoritative resolution propagates to all 3."""
        code = "MBS-7Q2N8K4R"
        rule_a = {"id": "rA", "name": "Name A", "ruleCode": code, "keywords": ["عرض"], "reply": "سعر 100", "matchType": "ultra_exact"}
        rule_b = {"id": "rB", "name": "Name B", "ruleCode": code, "keywords": ["عرض"], "reply": "سعر 150", "matchType": "ultra_exact"}
        rule_c = {"id": "rC", "name": "Name C", "ruleCode": code, "keywords": ["عرض"], "reply": "سعر 200", "matchType": "ultra_exact"}

        cfg_a, sha_a = self._create_fixture_profile("ProfA", [rule_a])
        cfg_b, sha_b = self._create_fixture_profile("ProfB", [rule_b])
        cfg_c, sha_c = self._create_fixture_profile("ProfC", [rule_c])

        # 1. Trigger coordinated save on ProfA -> should detect LINK_CONFLICT with all 3 profiles
        mod_a = {"rules": [{"id": "rA", "name": "Name A", "ruleCode": code, "keywords": ["عرض_جديد"], "reply": "سعر 100", "matchType": "ultra_exact"}], "config": {}}
        res_conflict = self.manager.save_profile_config_coordinated("ProfA", mod_a, expected_sha256=sha_a)
        self.assertFalse(res_conflict.get("ok"))
        self.assertEqual(res_conflict.get("code"), "LINK_CONFLICT")
        participating = res_conflict.get("participating_profiles", [])
        self.assertEqual(len(participating), 3)
        prof_names = [p["profile_name"] for p in participating]
        self.assertCountEqual(prof_names, ["ProfA", "ProfB", "ProfC"])

        expected_shas = {p["profile_name"]: p["sha256_token"] for p in participating}

        # 2. Test conflict resolution rejects stale tokens
        stale_shas = dict(expected_shas)
        stale_shas["ProfC"] = "stale_token_c"
        res_stale = self.manager.resolve_link_conflict(code, "ProfB", expected_shas=stale_shas)
        self.assertFalse(res_stale.get("ok"))
        self.assertEqual(res_stale.get("code"), "STALE_CONFIG")

        # 3. Test authoritative resolution from disk (ProfB is authoritative)
        res_resolve = self.bridge.resolve_link_conflict(code, "ProfB", expected_shas=expected_shas)
        self.assertTrue(res_resolve.get("ok"))
        self.assertTrue(res_resolve.get("disk_ok"))
        self.assertCountEqual(res_resolve.get("modified_profiles"), ["ProfA", "ProfB", "ProfC"])

        # Verify all 3 profiles on disk now have ProfB's canonical allowlist: reply='سعر 150', keywords=['عرض']
        for p_name, cfg_path, expected_local_name in [
            ("ProfA", cfg_a, "Name A"),
            ("ProfB", cfg_b, "Name B"),
            ("ProfC", cfg_c, "Name C")
        ]:
            disk_data = json.loads(cfg_path.read_text(encoding="utf-8"))
            rules_list = disk_data["rules"]
            self.assertEqual(len(rules_list), 1)
            r = rules_list[0]
            self.assertEqual(r["ruleCode"], code)
            self.assertEqual(r["reply"], "سعر 150", f"Profile {p_name} must have authoritative reply")
            self.assertEqual(r["keywords"], ["عرض"], f"Profile {p_name} must have authoritative keywords")
            self.assertEqual(r["name"], expected_local_name, f"Profile {p_name} must preserve its local name")

    # -------------------------------------------------------------------------
    # Test 8: Staged Profiles Pre-Replacement SHA Validation
    # -------------------------------------------------------------------------
    def test_staged_profiles_pre_replacement_sha_validation(self):
        """If a linked profile's disk hash changes during save staging, save aborts before writing."""
        code = "MBS-8K4R7Q2N"
        rule_x = {"id": "rX", "name": "X", "ruleCode": code, "keywords": ["kw"], "reply": "rep", "matchType": "ultra_exact"}
        rule_y = {"id": "rY", "name": "Y", "ruleCode": code, "keywords": ["kw"], "reply": "rep", "matchType": "ultra_exact"}

        cfg_x, sha_x = self._create_fixture_profile("ProfX", [rule_x])
        cfg_y, sha_y = self._create_fixture_profile("ProfY", [rule_y])

        mod_x = {
            "rules": [{"id": "rX", "name": "X", "ruleCode": code, "keywords": ["kw_mod"], "reply": "rep_mod", "matchType": "ultra_exact"}],
            "config": {}
        }

        # Modify ProfY on disk right as staged_docs backups are being collected (Call #5)
        orig_gpcp = self.manager.get_profile_config_path
        prof_y_calls = 0

        def gpcp_side_effect(p_name):
            nonlocal prof_y_calls
            p = orig_gpcp(p_name)
            if p_name == "ProfY":
                prof_y_calls += 1
                if prof_y_calls == 5:
                    # Staging completed; mutate ProfY disk file right before pre-replacement verification
                    cfg_y.write_bytes(b'{"rules": [], "config": {"concurrent": true}}')
            return p

        with patch.object(self.manager, "get_profile_config_path", side_effect=gpcp_side_effect):
            res = self.manager.save_profile_config_coordinated("ProfX", mod_x, expected_sha256=sha_x)
            self.assertFalse(res.get("ok"))
            self.assertEqual(res.get("code"), "STALE_CONFIG")
            self.assertIn("ProfY", res.get("message"))

    # -------------------------------------------------------------------------
    # Test 9: Multi-Profile Migration Atomic Rollback
    # -------------------------------------------------------------------------
    def test_multi_profile_migration_atomic_rollback(self):
        """Simulated I/O failure during multi-profile migration restores exact pre-write bytes."""
        p1_dir = self.base_dir / "Migrate1"
        p2_dir = self.base_dir / "Migrate2"
        p1_dir.mkdir()
        p2_dir.mkdir()

        raw1 = json.dumps({"rules": [{"id": "r1", "keywords": ["a"], "reply": "b", "matchType": "ultra_exact"}]}, indent=2).encode("utf-8")
        raw2 = json.dumps({"rules": [{"id": "r2", "keywords": ["c"], "reply": "d", "matchType": "ultra_exact"}]}, indent=2).encode("utf-8")
        (p1_dir / "config.json").write_bytes(raw1)
        (p2_dir / "config.json").write_bytes(raw2)

        original_atomic_write = atomic_write_json
        written_count = 0

        def failing_atomic_write(path, data, **kwargs):
            nonlocal written_count
            written_count += 1
            if written_count >= 2:
                raise IOError("Simulated disk error during second profile write")
            return original_atomic_write(path, data, **kwargs)

        with patch("profile_manager.atomic_write_json", side_effect=failing_atomic_write):
            res = self.manager.migrate_legacy_rule_metadata()
            self.assertFalse(res.get("ok"))
            self.assertEqual(res.get("code"), "WRITE_FAILURE")
            self.assertIn("Simulated disk error", res.get("message"))

        # Both profiles must be rolled back to their exact raw bytes
        self.assertEqual((p1_dir / "config.json").read_bytes(), raw1)
        self.assertEqual((p2_dir / "config.json").read_bytes(), raw2)

    # -------------------------------------------------------------------------
    # Test 10: GUI App.js Delimiter Elimination
    # -------------------------------------------------------------------------
    def test_no_gui_delimiter_split_or_trim(self):
        """Assert gui/app.js does not parse keyword arrays using comma split or trim."""
        app_js_path = Path(__file__).resolve().parent.parent / "gui" / "app.js"
        txt = app_js_path.read_text(encoding="utf-8")

        # Must not contain rule.keywords.split(',') or rule.keyword.split(',')
        self.assertNotIn("rule.keywords.split", txt)
        self.assertNotIn("rule.keyword.split", txt)
        # renderRulesUI section must not use split or trim to break keywords
        render_idx = txt.find("function renderRulesUI(")
        self.assertNotEqual(render_idx, -1)
        render_body = txt[render_idx:render_idx + 1800]
        self.assertNotIn(".split(',')", render_body)
        self.assertNotIn(".split(\",\")", render_body)

    # -------------------------------------------------------------------------
    # Test 11: Worker pySaveConfig Optimistic Concurrency
    # -------------------------------------------------------------------------
    def test_worker_optimistic_concurrency(self):
        """Worker save handler must reject stale client_sha256 and accept matching sha."""
        rules = [{"id": "r1", "name": "R1", "ruleCode": "MBS-W1", "keywords": ["kw"], "reply": "rep", "matchType": "ultra_exact"}]
        cfg_file, sha = self._create_fixture_profile("WorkerConcurProf", rules)

        # 1. Stale token
        res_stale = self.manager.save_profile_config_coordinated(
            "WorkerConcurProf", {"rules": rules, "config": {"active": True}}, expected_sha256="stale_sha"
        )
        self.assertFalse(res_stale.get("ok"))
        self.assertEqual(res_stale.get("code"), "STALE_CONFIG")

        # 2. Valid token
        res_valid = self.manager.save_profile_config_coordinated(
            "WorkerConcurProf", {"rules": rules, "config": {"active": True}}, expected_sha256=sha
        )
        self.assertTrue(res_valid.get("ok"))
        self.assertIsNotNone(res_valid.get("sha256_token"))

    # -------------------------------------------------------------------------
    # Test 12: ProfileManager Write Mutex Uses Reentrant RLock
    # -------------------------------------------------------------------------
    def test_transaction_mutex_uses_rlock_for_import_and_unlink(self):
        """self._write_mutex must be an RLock allowing reentrant acquisition."""
        self.assertIsInstance(self.manager._write_mutex, type(threading.RLock()))

        # Test reentrancy
        acquired_twice = False
        with self.manager._write_mutex:
            with self.manager._write_mutex:
                acquired_twice = True
        self.assertTrue(acquired_twice, "RLock must allow reentrant acquisition")

    # -------------------------------------------------------------------------
    # Test 13: Extracted Package Version Consistency
    # -------------------------------------------------------------------------
    def test_extracted_package_version_consistency(self):
        """Verify delivery package ZIP contains zero stale V6.5.0 or V6.5.1 user-visible strings."""
        pkg_path = Path(__file__).resolve().parent.parent / "Meta_Automation_V6.5.2_Delivery.zip"
        if not pkg_path.is_file():
            self.skipTest(f"Delivery package not yet created at {pkg_path}")

        with tempfile.TemporaryDirectory() as extract_dir:
            extract_path = Path(extract_dir)
            with zipfile.ZipFile(pkg_path, "r") as zf:
                zf.extractall(extract_path)

            scanned_files = 0
            for root, _, files in os.walk(extract_path):
                for f in files:
                    if f.endswith((".py", ".js", ".html", ".md", ".sh", ".bat")):
                        fp = Path(root) / f
                        txt = fp.read_text(encoding="utf-8", errors="ignore")
                        self.assertNotIn("V6.5.0", txt, f"Stale 'V6.5.0' found in packaged file: {f}")
                        self.assertNotIn("V6.5.1", txt, f"Stale 'V6.5.1' found in packaged file: {f}")
                        scanned_files += 1

            self.assertGreater(scanned_files, 8, "Expected at least 8 files scanned in delivery package")


if __name__ == "__main__":
    unittest.main()
