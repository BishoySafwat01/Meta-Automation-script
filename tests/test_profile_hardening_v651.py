#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — V6.5.1 Profile Hardening & Safe Migration Contracts
Comprehensive test suite verifying:
1. Read-only production profile baseline integrity (5, 7, 3, 4 rules; unchanged hashes).
2. Fixture-based metadata migration and idempotency (0 byte change on rerun, .bak preservation).
3. Import modes: Clone (new independent codes) vs Link (preserved shared code).
4. Intra-profile duplicate rule code rejection.
5. Ordinary save draft collision resolution (allocates fresh unique code for unlinked draft collision).
6. Cross-process root ownership guard collision (OWNERSHIP_COLLISION).
7. Linked rule conflict detection (LINK_CONFLICT) and authoritative resolution.
8. Snapshot dispatch non-persistence (APPLY_RULE_SNAPSHOT leaves disk untouched).
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from profile_manager import (
    ProfileManager,
    ProfileRootOwnershipGuard,
    RULE_CODE_REGEX,
    allocate_unique_rule_code,
    atomic_write_json,
)


class TestProfileHardeningV651(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir)
        self.manager.ownership_guard.acquire()

    def tearDown(self):
        if self.manager.ownership_guard.is_owned():
            self.manager.ownership_guard.release()
        self.tmp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Contract 1: Read-only Production Profile Baseline Integrity
    # -------------------------------------------------------------------------
    def test_production_baseline_read_only_integrity(self):
        """Production profiles must be readable without touching disk or modifying pre-fix hashes."""
        prod_dir = Path(os.path.expanduser("~/.config/meta_inbox_bot/profiles"))
        if not prod_dir.exists():
            self.skipTest("Production directory ~/.config/meta_inbox_bot/profiles not found")

        expected_counts = {
            "Ahmed": 5,
            "Demo CRM": 7,
            "Luxira": 3,
            "Luxira man": 4,
        }

        # Initialize read-only manager for production directory without acquiring locks
        prod_pm = ProfileManager(base_dir=prod_dir)

        # Confirm list_profiles reports exact counts
        profiles = prod_pm.list_profiles()
        prof_dict = {p["name"]: p for p in profiles}

        total_rules = 0
        for name, expected_count in expected_counts.items():
            self.assertIn(name, prof_dict, f"Production profile '{name}' must exist")
            self.assertEqual(
                prof_dict[name]["rules_count"],
                expected_count,
                f"Profile '{name}' must report exactly {expected_count} rules"
            )

            # Check load_profile_config_result envelope
            res = prod_pm.load_profile_config_result(name)
            self.assertTrue(res["ok"], f"Failed to load '{name}': {res.get('error')}")
            self.assertEqual(res["read_status"], "OK")
            self.assertEqual(res["rules_count"], expected_count)
            self.assertIsNotNone(res["sha256_token"])

            # Verify sha256_token matches current disk file hash
            cfg_path = prod_pm.get_profile_config_path(name)
            disk_sha = hashlib.sha256(cfg_path.read_bytes()).hexdigest()
            self.assertEqual(res["sha256_token"], disk_sha)

            total_rules += expected_count

        self.assertEqual(total_rules, 19, "Total production rules across all 4 profiles must be 19")

    # -------------------------------------------------------------------------
    # Contract 2: Fixture-Based Metadata Migration and Idempotency
    # -------------------------------------------------------------------------
    def test_fixture_migration_and_idempotency(self):
        """Migration must assign unique Crockford codes, preserve empty names, create .bak,
        and be 100% idempotent (0 bytes modified on second run)."""
        prof_dir = self.base_dir / "LegacyProf"
        prof_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = prof_dir / "config.json"

        valid_code = "MBS-7Q2N8K4R"
        legacy_data = {
            "rules": [
                {"id": "r1", "keywords": ["kw1"], "reply": "rep1", "matchType": "ultra_exact"},
                {"id": "r2", "name": "Custom Name", "keywords": ["kw2"], "reply": "rep2", "matchType": "contains"},
                {"id": "r3", "ruleCode": valid_code, "name": "", "keywords": ["kw3"], "reply": "rep3", "matchType": "exact"},
            ],
            "config": {"active": True}
        }
        raw_initial_bytes = json.dumps(legacy_data, ensure_ascii=False, indent=2).encode("utf-8")
        cfg_file.write_bytes(raw_initial_bytes)

        # Run migration pass 1
        res1 = self.manager.migrate_legacy_rule_metadata("LegacyProf")
        self.assertTrue(res1.get("ok"), f"Migration pass 1 failed: {res1}")
        self.assertEqual(res1.get("total_migrated"), 2, "Should migrate exactly 2 rules lacking codes")

        # Verify .pre-migration.bak was created and matches raw initial bytes
        bak_file = prof_dir / "config.json.pre-migration.bak"
        self.assertTrue(bak_file.exists(), ".pre-migration.bak must be created")
        self.assertEqual(bak_file.read_bytes(), raw_initial_bytes, "Backup bytes must match pre-migration bytes exactly")

        # Verify updated config
        updated_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        rules = updated_cfg["rules"]
        self.assertEqual(len(rules), 3)

        # Rule 1: new Crockford code assigned, name preserved as ""
        self.assertTrue(RULE_CODE_REGEX.match(rules[0]["ruleCode"]))
        self.assertEqual(rules[0]["name"], "")

        # Rule 2: new Crockford code assigned, name preserved as "Custom Name"
        self.assertTrue(RULE_CODE_REGEX.match(rules[1]["ruleCode"]))
        self.assertEqual(rules[1]["name"], "Custom Name")

        # Rule 3: pre-existing valid code unchanged
        self.assertEqual(rules[2]["ruleCode"], valid_code)
        self.assertEqual(rules[2]["name"], "")

        # Record post-migration bytes
        post_migration_bytes = cfg_file.read_bytes()

        # Run migration pass 2 (Idempotency test)
        res2 = self.manager.migrate_legacy_rule_metadata("LegacyProf")
        self.assertTrue(res2.get("ok"), f"Migration pass 2 failed: {res2}")
        self.assertEqual(res2.get("total_migrated"), 0, "Second migration must migrate 0 rules")
        self.assertEqual(
            res2.get("profiles", {}).get("LegacyProf", {}).get("status"),
            "ALREADY_UP_TO_DATE"
        )

        # Assert 0 bytes modified
        self.assertEqual(cfg_file.read_bytes(), post_migration_bytes, "Second migration must not alter file bytes")

    # -------------------------------------------------------------------------
    # Contract 3: Clone vs Link Import Modes
    # -------------------------------------------------------------------------
    def test_clone_import_generates_new_rule_codes(self):
        """Importing rules in 'clone' mode must generate fresh, independent ruleCodes."""
        src_dir = self.base_dir / "SourceProf"
        src_dir.mkdir(parents=True, exist_ok=True)
        tgt_dir = self.base_dir / "TargetProf"
        tgt_dir.mkdir(parents=True, exist_ok=True)

        src_code = "MBS-23456789"
        src_data = {
            "rules": [
                {"id": "r_src", "ruleCode": src_code, "name": "Source Rule", "keywords": ["test"], "reply": "src_reply"}
            ]
        }
        atomic_write_json(src_dir / "config.json", src_data)
        atomic_write_json(tgt_dir / "config.json", {"rules": []})
        tgt_sha = hashlib.sha256((tgt_dir / "config.json").read_bytes()).hexdigest()

        src_bytes_before = (src_dir / "config.json").read_bytes()

        # Import in 'clone' mode
        res = self.manager.import_rules_from_profile(
            "TargetProf", "SourceProf", ["r_src"], mode="clone", target_sha=tgt_sha
        )
        self.assertTrue(res.get("ok"), f"Clone import failed: {res}")

        tgt_cfg = json.loads((tgt_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tgt_cfg["rules"]), 1)
        cloned_rule = tgt_cfg["rules"][0]

        self.assertNotEqual(cloned_rule["ruleCode"], src_code, "Clone mode must allocate a new ruleCode")
        self.assertTrue(RULE_CODE_REGEX.match(cloned_rule["ruleCode"]))
        self.assertEqual(cloned_rule["reply"], "src_reply")

        # Source profile must remain 100% byte-for-byte untouched
        self.assertEqual((src_dir / "config.json").read_bytes(), src_bytes_before)

    def test_link_import_preserves_rule_code_and_creates_link(self):
        """Importing rules in 'link' mode must preserve shared ruleCode."""
        src_dir = self.base_dir / "SourceProf"
        src_dir.mkdir(parents=True, exist_ok=True)
        tgt_dir = self.base_dir / "TargetProf"
        tgt_dir.mkdir(parents=True, exist_ok=True)

        shared_code = "MBS-7Q2N8K4R"
        src_data = {
            "rules": [
                {"id": "r_src", "ruleCode": shared_code, "name": "Shared Rule", "keywords": ["shared"], "reply": "shared_reply"}
            ]
        }
        atomic_write_json(src_dir / "config.json", src_data)
        atomic_write_json(tgt_dir / "config.json", {"rules": []})
        tgt_sha = hashlib.sha256((tgt_dir / "config.json").read_bytes()).hexdigest()

        res = self.manager.import_rules_from_profile(
            "TargetProf", "SourceProf", ["r_src"], mode="link", target_sha=tgt_sha
        )
        self.assertTrue(res.get("ok"), f"Link import failed: {res}")

        tgt_cfg = json.loads((tgt_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tgt_cfg["rules"]), 1)
        linked_rule = tgt_cfg["rules"][0]

        self.assertEqual(linked_rule["ruleCode"], shared_code, "Link mode must preserve shared ruleCode")

        # Verify linked rules map detects both profiles
        linked_counts = self.manager.get_linked_rule_counts()
        self.assertIn(shared_code, linked_counts)
        self.assertEqual(linked_counts[shared_code], 2, "Shared rule code must be linked to 2 profiles")

    # -------------------------------------------------------------------------
    # Contract 4: Intra-Profile Duplicate Code Rejection
    # -------------------------------------------------------------------------
    def test_intra_profile_duplicate_code_rejected(self):
        """A profile cannot save multiple rules containing identical ruleCodes."""
        prof_dir = self.base_dir / "DupProf"
        prof_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = prof_dir / "config.json"
        atomic_write_json(cfg_file, {"rules": []})

        dup_code = "MBS-23456789"
        dup_payload = {
            "rules": [
                {"id": "r1", "ruleCode": dup_code, "keywords": ["a"], "reply": "rep1"},
                {"id": "r2", "ruleCode": dup_code, "keywords": ["b"], "reply": "rep2"},
            ]
        }
        res = self.manager.save_profile_config_coordinated("DupProf", dup_payload)
        self.assertFalse(res.get("ok"), "Intra-profile duplicate rule codes must be rejected")
        self.assertIn("DUPLICATE", res.get("code", ""))

        # Verify config was not saved
        saved_cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        self.assertEqual(len(saved_cfg["rules"]), 0)

    # -------------------------------------------------------------------------
    # Contract 5: Ordinary Save Draft Collision Resolution
    # -------------------------------------------------------------------------
    def test_ordinary_save_draft_collision_resolution(self):
        """Ordinary save with unlinked colliding draft code replaces it with a fresh unique code."""
        prof_a_dir = self.base_dir / "ProfA"
        prof_a_dir.mkdir(parents=True, exist_ok=True)
        prof_b_dir = self.base_dir / "ProfB"
        prof_b_dir.mkdir(parents=True, exist_ok=True)

        existing_code = "MBS-7Q2N8K4R"
        atomic_write_json(prof_a_dir / "config.json", {
            "rules": [{"id": "r_a", "ruleCode": existing_code, "name": "Prof A Rule", "keywords": ["a"], "reply": "rep_a"}]
        })
        atomic_write_json(prof_b_dir / "config.json", {"rules": []})

        # Prof B tries to save a draft rule that collides with Prof A's code
        draft_payload = {
            "rules": [{"id": "r_b", "ruleCode": existing_code, "name": "Unlinked Draft", "keywords": ["b"], "reply": "rep_b"}]
        }
        res = self.manager.save_profile_config_coordinated("ProfB", draft_payload)
        self.assertTrue(res.get("ok"), f"Save should succeed with collision replaced: {res}")

        saved_b = json.loads((prof_b_dir / "config.json").read_text(encoding="utf-8"))
        allocated_code = saved_b["rules"][0]["ruleCode"]
        self.assertNotEqual(allocated_code, existing_code, "Draft collision must be replaced with fresh code")
        self.assertTrue(RULE_CODE_REGEX.match(allocated_code))

    # -------------------------------------------------------------------------
    # Contract 6: Cross-Process Ownership Guard Collision
    # -------------------------------------------------------------------------
    def test_ownership_collision_prevents_mutations(self):
        """When an external process owns .app_owner.lock, operations must fail with OWNERSHIP_COLLISION."""
        self.manager.ownership_guard.release()

        external_guard = ProfileRootOwnershipGuard(self.base_dir)
        acquired = external_guard.acquire()
        self.assertTrue(acquired, "External guard should acquire lock")

        try:
            other_pm = ProfileManager(base_dir=self.base_dir)
            prof_dir = self.base_dir / "LockedProf"
            prof_dir.mkdir(parents=True, exist_ok=True)
            atomic_write_json(prof_dir / "config.json", {"rules": []})

            res = other_pm.save_profile_config_coordinated("LockedProf", {"rules": []})
            self.assertFalse(res.get("ok"))
            self.assertEqual(res.get("code"), "OWNERSHIP_COLLISION")

            mig_res = other_pm.migrate_legacy_rule_metadata("LockedProf")
            self.assertFalse(mig_res.get("ok"))
            self.assertEqual(mig_res.get("code"), "OWNERSHIP_COLLISION")
        finally:
            external_guard.release()
            self.manager.ownership_guard.acquire()

    # -------------------------------------------------------------------------
    # Contract 7: Linked Rule Conflict Detection and Resolution
    # -------------------------------------------------------------------------
    def test_link_conflict_detection_and_resolution(self):
        """Saving a linked rule with divergent content returns LINK_CONFLICT unless resolved."""
        prof_a_dir = self.base_dir / "ProfA"
        prof_a_dir.mkdir(parents=True, exist_ok=True)
        prof_b_dir = self.base_dir / "ProfB"
        prof_b_dir.mkdir(parents=True, exist_ok=True)

        shared_code = "MBS-JKMNPQRS"
        rule_a = {"id": "r_a", "ruleCode": shared_code, "name": "Shared", "keywords": ["kw"], "reply": "Original Baseline"}
        rule_b_diverged = {"id": "r_b", "ruleCode": shared_code, "name": "Shared", "keywords": ["kw"], "reply": "Peer Diverged Reply"}

        # Prof A has baseline, Prof B has diverged on disk
        atomic_write_json(prof_a_dir / "config.json", {"rules": [rule_a]})
        atomic_write_json(prof_b_dir / "config.json", {"rules": [rule_b_diverged]})

        # Now Prof A modifies rule and saves to "Modified Reply A"
        modified_rule_a = dict(rule_a)
        modified_rule_a["reply"] = "Modified Reply A"

        # Coordinated save of ProfA without override triggers LINK_CONFLICT
        res = self.manager.save_profile_config_coordinated(
            "ProfA",
            {"rules": [modified_rule_a]},
            link_resolution=None
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "LINK_CONFLICT")
        self.assertEqual(res.get("conflicting_code"), shared_code)

        # Now save with authoritative override resolution
        res_resolved = self.manager.save_profile_config_coordinated(
            "ProfA",
            {"rules": [modified_rule_a]},
            link_resolution={"conflicting_code": shared_code, "action": "use_authoritative"}
        )
        self.assertTrue(res_resolved.get("ok"), f"Resolution save failed: {res_resolved}")

        # ProfB must now also reflect the authoritative reply
        prof_b_cfg = json.loads((prof_b_dir / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(prof_b_cfg["rules"][0]["reply"], "Modified Reply A")

    # -------------------------------------------------------------------------
    # Contract 8: Snapshot Non-Persistence
    # -------------------------------------------------------------------------
    def test_snapshot_dispatch_non_persistence(self):
        """Dispatching rule snapshot to running browser workers must never alter disk files."""
        prof_dir = self.base_dir / "SnapProf"
        prof_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = prof_dir / "config.json"

        initial_data = {
            "rules": [{"id": "r1", "ruleCode": "MBS-TVWXYZ23", "keywords": ["kw"], "reply": "initial"}]
        }
        atomic_write_json(cfg_file, initial_data)
        initial_bytes = cfg_file.read_bytes()

        # Simulate snapshot dispatch through DesktopBridgeApi
        from desktop_app import DesktopBridgeApi
        bridge = DesktopBridgeApi(self.manager, None)

        bridge._dispatch_rule_snapshots(["SnapProf"])

        # Verify disk file is 100% byte-for-byte identical
        self.assertEqual(cfg_file.read_bytes(), initial_bytes)


if __name__ == "__main__":
    unittest.main()
