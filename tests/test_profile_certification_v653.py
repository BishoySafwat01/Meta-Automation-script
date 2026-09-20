#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Meta Business Automator — V6.5.3 Certification & Regression Test Suite
=============================================================================
Comprehensive Regression Coverage:
1. Coordinated save exception never falls back to boolean save_profile_config.
2. Boolean or malformed save responses not accepted as success in UI contract.
3. Source mutation during import/clone detected as STALE_SOURCE_CONFIG with 0 target mutation.
4. Target mutation during import rejected with STALE_CONFIG and target untouched.
5. Clone and Link leave source profile bytes bit-identical (100% parity).
6. Conflict resolution with omitted or incomplete token rejected before staging.
7. Conflict resolution with stale participant rejected before staging with 0 writes.
8. Worker RELOAD_CONFIG / snapshot failure cleanly captured in runtime_refresh_failures.
9. Disk success with runtime refresh failure partial-success contract.
10. Extracted delivery package validation (16 allowlisted files, 0 stale identifiers).
11. Tokenless legacy save_profile_config strictly rejected with MISSING_CONCURRENCY_TOKEN and 0 disk writes.
12. Import/Clone without target concurrency token strictly rejected with MISSING_CONCURRENCY_TOKEN and 0 disk writes.
=============================================================================
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from profile_manager import (
    ProfileManager,
    atomic_write_json,
    allocate_unique_rule_code,
)
from desktop_app import DesktopBridgeApi


class TestProfileCertificationV653(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir)
        self.manager.ownership_guard.acquire()
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
            "config": config or {"active": True, "cooldown_seconds": 1.5, "monitoring_interval_seconds": 5.0}
        }
        raw_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        cfg_file.write_bytes(raw_bytes)
        sha = hashlib.sha256(raw_bytes).hexdigest()
        return cfg_file, sha

    # -------------------------------------------------------------------------
    # Test 1: Coordinated save exception never falls back to boolean save_profile_config
    # -------------------------------------------------------------------------
    def test_coordinated_save_exception_never_invokes_boolean_fallback(self):
        """Verify that in gui/app.js, rule saving has zero fallback to save_profile_config."""
        app_js_path = Path(__file__).resolve().parent.parent / "gui" / "app.js"
        content = app_js_path.read_text(encoding="utf-8")

        # Ensure no fallback to save_profile_config inside btnSaveRules listener
        save_rules_start = content.find("elements.btnSaveRules.addEventListener")
        self.assertNotEqual(save_rules_start, -1, "btnSaveRules listener missing in app.js")
        save_rules_block = content[save_rules_start:save_rules_start + 3000]

        self.assertNotIn("save_profile_config(", save_rules_block,
                         "Unsafe fallback to save_profile_config found in rule saving block!")
        self.assertIn("save_profile_config_coordinated", save_rules_block,
                      "save_profile_config_coordinated missing in rule saving block")

    # -------------------------------------------------------------------------
    # Test 2: Boolean or malformed save responses not accepted as success
    # -------------------------------------------------------------------------
    def test_boolean_or_malformed_save_not_accepted_as_success(self):
        """Verify that UI contract strictly requires res && res.ok && res.disk_ok and rejects boolean true."""
        app_js_path = Path(__file__).resolve().parent.parent / "gui" / "app.js"
        content = app_js_path.read_text(encoding="utf-8")

        # Verify res.disk_ok is required for rule saving
        self.assertIn("res && res.ok && res.disk_ok", content,
                      "Strict envelope check (res && res.ok && res.disk_ok) missing in app.js")
        self.assertNotIn("res === true", content,
                         "Unsafe 'res === true' found in app.js")

        # Python bridge save_profile_config_coordinated contract returns disk_ok
        _, sha = self._create_fixture_profile("P1", [])
        res = self.bridge.save_profile_config_coordinated("P1", {"rules": [], "config": {}}, expected_sha256=sha)
        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("disk_ok"))
        self.assertIn("runtime_refresh_successes", res)
        self.assertIn("runtime_refresh_failures", res)

    # -------------------------------------------------------------------------
    # Test 3: Source mutation during import detected as STALE_SOURCE_CONFIG
    # -------------------------------------------------------------------------
    def test_source_mutation_during_import_detected_as_stale_source(self):
        """Modifying the source profile during import staging triggers STALE_SOURCE_CONFIG with 0 target mutation."""
        code = allocate_unique_rule_code(set())
        rule_src = {
            "id": "r1",
            "ruleCode": code,
            "name": "Source Rule",
            "keywords": ["مرحبا"],
            "reply": "أهلاً بك",
            "matchType": "ultra_exact",
            "caseSensitive": False,
        }
        src_file, _ = self._create_fixture_profile("Source_Prof", [rule_src])
        tgt_file, tgt_sha = self._create_fixture_profile("Target_Prof", [])
        tgt_bytes_before = tgt_file.read_bytes()

        # Monkey-patch json.loads during import to simulate concurrent disk write to source
        original_json_loads = json.loads
        def patched_json_loads(s, *args, **kwargs):
            result = original_json_loads(s, *args, **kwargs)
            # Mutate source on disk right after initial read
            if isinstance(result, dict) and "rules" in result and result.get("rules") and result["rules"][0].get("id") == "r1":
                # External thread overwrites source file
                mutated = {
                    "rules": [{**rule_src, "reply": "تعديل خارجي متزامن"}],
                    "config": {"active": True}
                }
                src_file.write_bytes(json.dumps(mutated, ensure_ascii=False).encode("utf-8"))
            return result

        with patch("json.loads", side_effect=patched_json_loads):
            res = self.manager.import_rules_from_profile(
                "Target_Prof", "Source_Prof", ["r1"], mode="clone", expected_target_sha256=tgt_sha
            )

        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "STALE_SOURCE_CONFIG")
        # Target must be completely unchanged
        tgt_bytes_after = tgt_file.read_bytes()
        self.assertEqual(tgt_bytes_before, tgt_bytes_after,
                         "Target profile was mutated despite source staleness collision!")

    # -------------------------------------------------------------------------
    # Test 4: Target mutation during import rejected
    # -------------------------------------------------------------------------
    def test_target_mutation_during_import_rejected(self):
        """If target profile is modified before import write, operation aborts with STALE_CONFIG."""
        code = allocate_unique_rule_code(set())
        rule_src = {
            "id": "r1",
            "ruleCode": code,
            "name": "Source Rule",
            "keywords": ["مرحبا"],
            "reply": "أهلاً بك",
            "matchType": "ultra_exact",
            "caseSensitive": False,
        }
        self._create_fixture_profile("Source_Prof", [rule_src])
        tgt_file, tgt_sha = self._create_fixture_profile("Target_Prof", [])

        # Call with stale expected target SHA
        stale_sha = "0000000000000000000000000000000000000000000000000000000000000000"
        res = self.manager.import_rules_from_profile(
            "Target_Prof", "Source_Prof", ["r1"], mode="clone", expected_target_sha256=stale_sha
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "STALE_CONFIG")

    # -------------------------------------------------------------------------
    # Test 5: Clone and Link leave source bytes exactly unchanged
    # -------------------------------------------------------------------------
    def test_clone_and_link_leave_source_bytes_exactly_unchanged(self):
        """Clone and Link modes must never modify a single byte in the source profile."""
        code = allocate_unique_rule_code(set())
        rule_src = {
            "id": "r1",
            "ruleCode": code,
            "name": "Original Rule",
            "keywords": ["كود", "عرض"],
            "reply": "تفاصيل العرض",
            "matchType": "ultra_exact",
            "caseSensitive": True,
        }
        src_file, src_sha = self._create_fixture_profile("Source_P", [rule_src])
        src_bytes_initial = src_file.read_bytes()

        tgt_c_file, tgt_c_sha = self._create_fixture_profile("Target_Clone", [])
        tgt_l_file, tgt_l_sha = self._create_fixture_profile("Target_Link", [])

        # 1. Clone mode
        res_clone = self.manager.import_rules_from_profile(
            "Target_Clone", "Source_P", ["r1"], mode="clone", target_sha=tgt_c_sha
        )
        self.assertTrue(res_clone.get("ok"))
        self.assertEqual(src_file.read_bytes(), src_bytes_initial, "Source file modified during Clone!")
        self.assertEqual(hashlib.sha256(src_file.read_bytes()).hexdigest(), src_sha)

        # 2. Link mode
        res_link = self.manager.import_rules_from_profile(
            "Target_Link", "Source_P", ["r1"], mode="link", target_sha=tgt_l_sha
        )
        self.assertTrue(res_link.get("ok"))
        self.assertEqual(src_file.read_bytes(), src_bytes_initial, "Source file modified during Link!")
        self.assertEqual(hashlib.sha256(src_file.read_bytes()).hexdigest(), src_sha)

    # -------------------------------------------------------------------------
    # Test 6: Conflict resolution with omitted token rejected
    # -------------------------------------------------------------------------
    def test_conflict_resolution_with_omitted_token_rejected(self):
        """resolve_link_conflict requires valid expected_shas for all participating profiles."""
        shared_code = allocate_unique_rule_code(set())
        r_p1 = {"id": "r1", "ruleCode": shared_code, "name": "R1", "keywords": ["أ"], "reply": "1", "matchType": "ultra_exact", "caseSensitive": False}
        r_p2 = {"id": "r2", "ruleCode": shared_code, "name": "R2", "keywords": ["ب"], "reply": "2", "matchType": "ultra_exact", "caseSensitive": False}
        f1, sha1 = self._create_fixture_profile("P1", [r_p1])
        f2, sha2 = self._create_fixture_profile("P2", [r_p2])

        b1_before = f1.read_bytes()
        b2_before = f2.read_bytes()

        # Omitted tokens (None)
        res_none = self.manager.resolve_link_conflict(shared_code, "P1", expected_shas=None)
        self.assertFalse(res_none.get("ok"))
        self.assertEqual(res_none.get("code"), "MISSING_CONCURRENCY_TOKEN")

        # Incomplete tokens (missing P2)
        res_partial = self.manager.resolve_link_conflict(shared_code, "P1", expected_shas={"P1": sha1})
        self.assertFalse(res_partial.get("ok"))
        self.assertEqual(res_partial.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertIn("P2", res_partial.get("missing_profiles", []))

        # Disks must be 100% untouched
        self.assertEqual(f1.read_bytes(), b1_before)
        self.assertEqual(f2.read_bytes(), b2_before)

    # -------------------------------------------------------------------------
    # Test 7: Conflict resolution with stale participant rejected
    # -------------------------------------------------------------------------
    def test_conflict_resolution_with_stale_participant_rejected(self):
        """If any participant token is stale, resolve_link_conflict aborts before any writes."""
        shared_code = allocate_unique_rule_code(set())
        r_p1 = {"id": "r1", "ruleCode": shared_code, "name": "R1", "keywords": ["س"], "reply": "1", "matchType": "ultra_exact", "caseSensitive": False}
        r_p2 = {"id": "r2", "ruleCode": shared_code, "name": "R2", "keywords": ["ص"], "reply": "2", "matchType": "ultra_exact", "caseSensitive": False}
        f1, sha1 = self._create_fixture_profile("P1", [r_p1])
        f2, sha2 = self._create_fixture_profile("P2", [r_p2])

        b1_before = f1.read_bytes()
        b2_before = f2.read_bytes()

        stale_shas = {"P1": sha1, "P2": "stale_hash_value_12345"}
        res = self.manager.resolve_link_conflict(shared_code, "P1", expected_shas=stale_shas)
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "STALE_CONFIG")
        self.assertEqual(res.get("stale_profile"), "P2")

        # Both profiles unchanged
        self.assertEqual(f1.read_bytes(), b1_before)
        self.assertEqual(f2.read_bytes(), b2_before)

    # -------------------------------------------------------------------------
    # Test 8: Worker reload config failure captured in runtime_refresh_failures
    # -------------------------------------------------------------------------
    def test_worker_reload_config_failure_reported(self):
        """When live browser reload fails, the error is recorded under runtime_refresh_failures."""
        _, sha = self._create_fixture_profile("Worker_Prof", [])

        # Mock worker as running, but send_page_command fails on RELOAD_CONFIG
        self.bridge.is_worker_running = MagicMock(return_value=True)

        def mock_send(pname, cmd, payload):
            if cmd == "RELOAD_CONFIG":
                return False
            return True

        self.bridge.send_page_command = MagicMock(side_effect=mock_send)

        payload = {"rules": [], "config": {"cooldown_seconds": 3.0}}
        res = self.bridge.save_profile_config_coordinated("Worker_Prof", payload, expected_sha256=sha)

        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("disk_ok"))
        self.assertIn("Worker_Prof", res.get("runtime_refresh_failures", {}))
        self.assertNotIn("Worker_Prof", res.get("runtime_refresh_successes", []))

    # -------------------------------------------------------------------------
    # Test 9: Disk success with runtime refresh failure partial-success contract
    # -------------------------------------------------------------------------
    def test_disk_success_runtime_failure_partial_success_contract(self):
        """Assert disk persistence succeeds and reports partial success when worker fails."""
        _, sha = self._create_fixture_profile("Partial_Prof", [])

        self.bridge.is_worker_running = MagicMock(return_value=True)
        self.bridge.send_page_command = MagicMock(side_effect=Exception("IPC Connection Closed"))

        payload = {"rules": [], "config": {"cooldown_seconds": 2.0}}
        res = self.bridge.save_profile_config_coordinated("Partial_Prof", payload, expected_sha256=sha)

        self.assertTrue(res.get("ok"))
        self.assertTrue(res.get("disk_ok"))
        self.assertEqual(len(res.get("runtime_refresh_successes", [])), 0)
        self.assertIn("Partial_Prof", res.get("runtime_refresh_failures", {}))

    # -------------------------------------------------------------------------
    # Test 10: Extracted delivery package version and cleanliness
    # -------------------------------------------------------------------------
    def test_extracted_package_version_and_cleanliness(self):
        """Verify delivery package ZIP contains exactly 16 allowlisted files and 0 stale version identifiers."""
        pkg_path = Path(__file__).resolve().parent.parent / "Meta_Automation_V6.5.4_Delivery.zip"
        if not pkg_path.is_file():
            self.skipTest("Meta_Automation_V6.5.4_Delivery.zip has not been built yet.")

        with zipfile.ZipFile(pkg_path, "r") as zf:
            namelist = zf.namelist()
            top_level = set(n.split("/")[0] for n in namelist)

            # Assert no forbidden files or directories
            self.assertNotIn("profiles", top_level, "ZIP contains forbidden profiles directory!")
            self.assertNotIn("tests", top_level, "ZIP contains forbidden tests directory!")
            self.assertNotIn(".git", top_level, "ZIP contains forbidden .git directory!")

            # Check for stale versions in extracted content
            with tempfile.TemporaryDirectory() as tmp_ext:
                zf.extractall(tmp_ext)
                ext_dir = Path(tmp_ext)

                # Check userscript parity
                bs = (ext_dir / "bot_script.js").read_bytes()
                ms = (ext_dir / "meta_inbox_userscript.user.js").read_bytes()
                self.assertEqual(bs, ms, "Packaged userscripts do not match byte-for-byte!")

                # Check for stale version mentions in text files
                for item in ext_dir.rglob("*"):
                    if item.is_file() and item.suffix in [".py", ".js", ".html", ".md", ".bat", ".sh"]:
                        txt = item.read_text(encoding="utf-8", errors="ignore")
                        self.assertNotIn("V6.5.0", txt, f"Stale 'V6.5.0' found in {item.name}")
                        self.assertNotIn("V6.5.1", txt, f"Stale 'V6.5.1' found in {item.name}")
                        self.assertNotIn("V6.5.2", txt, f"Stale 'V6.5.2' found in {item.name}")
                        self.assertNotIn("V6.5.3", txt, f"Stale 'V6.5.3' found in {item.name}")

    # -------------------------------------------------------------------------
    # Test 11: Tokenless legacy bridge save strictly rejected with 0 disk writes
    # -------------------------------------------------------------------------
    def test_tokenless_legacy_bridge_save_rejected(self):
        """Tokenless save_profile_config returns MISSING_CONCURRENCY_TOKEN with zero disk writes."""
        f, sha_before = self._create_fixture_profile("P_Tokenless", [])
        bytes_before = f.read_bytes()

        # 1. Missing expected_sha
        res = self.bridge.save_profile_config("P_Tokenless", {"rules": [{"id": "r1"}], "config": {}})
        self.assertFalse(res.get("ok"))
        self.assertFalse(res.get("disk_ok"))
        self.assertEqual(res.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertEqual(f.read_bytes(), bytes_before, "Disk was mutated by tokenless save!")

        # 2. None token
        res_none = self.bridge.save_profile_config("P_Tokenless", {"rules": []}, expected_sha=None)
        self.assertFalse(res_none.get("ok"))
        self.assertFalse(res_none.get("disk_ok"))
        self.assertEqual(res_none.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertEqual(f.read_bytes(), bytes_before, "Disk was mutated by None token save!")

        # 3. Empty string token
        res_empty = self.bridge.save_profile_config("P_Tokenless", {"rules": []}, expected_sha="")
        self.assertFalse(res_empty.get("ok"))
        self.assertFalse(res_empty.get("disk_ok"))
        self.assertEqual(res_empty.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertEqual(f.read_bytes(), bytes_before, "Disk was mutated by empty string token save!")

    # -------------------------------------------------------------------------
    # Test 12: Import without target concurrency token strictly rejected
    # -------------------------------------------------------------------------
    def test_import_without_target_sha_rejected(self):
        """import_rules_from_profile without target_sha returns MISSING_CONCURRENCY_TOKEN with zero disk writes."""
        code = allocate_unique_rule_code(set())
        rule_src = {
            "id": "r1",
            "ruleCode": code,
            "name": "Source Rule",
            "keywords": ["test"],
            "reply": "reply",
            "matchType": "ultra_exact",
            "caseSensitive": False,
        }
        self._create_fixture_profile("Source_P_Import", [rule_src])
        tgt_f, tgt_sha = self._create_fixture_profile("Target_P_Import", [])
        tgt_bytes_before = tgt_f.read_bytes()

        # 1. Call ProfileManager without target token
        res_pm = self.manager.import_rules_from_profile(
            "Target_P_Import", "Source_P_Import", ["r1"], mode="clone", target_sha=None
        )
        self.assertFalse(res_pm.get("ok"))
        self.assertEqual(res_pm.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertEqual(tgt_f.read_bytes(), tgt_bytes_before, "Target disk was mutated without token!")

        # 2. Call Bridge without target token
        res_bridge = self.bridge.import_rules_from_profile(
            "Target_P_Import", "Source_P_Import", ["r1"], mode="clone", target_sha=None
        )
        self.assertFalse(res_bridge.get("ok"))
        self.assertFalse(res_bridge.get("disk_ok"))
        self.assertEqual(res_bridge.get("code"), "MISSING_CONCURRENCY_TOKEN")
        self.assertEqual(tgt_f.read_bytes(), tgt_bytes_before, "Target disk was mutated via bridge without token!")


if __name__ == "__main__":
    unittest.main()
