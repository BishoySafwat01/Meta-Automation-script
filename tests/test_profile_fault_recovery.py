#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — Phase 2: Fault Recovery & Crash Reconciliation Test Suite
Tests:
1. Normal Save Operation Record Cleanup: verifies .sync_op_*.json is removed after successful save.
2. Interrupted Save Recovery: simulates crash leaving .sync_op_*.json; verifies reconcile_crash_recovery completes repair.
3. Lagging Replica Reconciliation: detects lagging replica at lower revision and fast-forwards to highest revision.
4. Split-Brain Conflict Detection: equal highest revision with different payload hashes fails closed and reports conflict.
"""

import os
import json
import uuid
import tempfile
import unittest
from pathlib import Path

from profile_manager import (
    ProfileManager,
    ProfileSyncCoordinator,
    RuleSchemaMigrator,
    atomic_write_json,
    generate_profile_id,
    hash_rule_allowlist
)


class TestProfileFaultRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir, sync_v2_enabled=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_normal_save_cleans_up_recovery_records(self):
        """A normal coordinated save should create and delete .sync_op_*.json files cleanly."""
        res_a = self.manager.create_profile("ProfileA")
        self.assertTrue(res_a)

        doc_a = self.manager.get_profile_config("ProfileA")
        op_id = str(uuid.uuid4())
        code = self.manager.allocator.allocate_code()
        doc_a["rules"] = [
            {
                "id": "rule_01",
                "ruleCode": code,
                "name": "Normal Rule",
                "active": True,
                "keywords": ["test"],
                "reply": "Normal response",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": False,
                "shared": False,
                "sync": {
                    "revision": 0,
                    "updatedAt": "2026-09-20T00:00:00Z",
                    "updatedByProfileId": doc_a["profileId"],
                    "operationId": op_id,
                    "memberProfileIds": [doc_a["profileId"]]
                }
            }
        ]
        save_res = self.manager.save_profile_config_result("ProfileA", doc_a)
        self.assertTrue(save_res.ok)

        # Assert no .sync_op_*.json files exist
        p_dir = self.base_dir / "ProfileA"
        recovery_files = list(p_dir.glob(".sync_op_*.json"))
        self.assertEqual(len(recovery_files), 0)

    def test_interrupted_save_recovery(self):
        """Simulate crash during multi-profile commit: ProfileA committed, ProfileB lagged with .sync_op file."""
        self.manager.create_profile("ProfileA")
        self.manager.create_profile("ProfileB")

        doc_a = self.manager.get_profile_config("ProfileA")
        doc_b = self.manager.get_profile_config("ProfileB")

        pid_a = doc_a["profileId"]
        pid_b = doc_b["profileId"]
        code = "MBS-CRASHTST"
        op_id = str(uuid.uuid4())

        rule_template = {
            "name": "Crash Rule",
            "active": True,
            "keywords": ["crash_repair"],
            "reply": "Repaired content",
            "matchType": "ultra_exact",
            "caseSensitive": False,
            "isLinked": True,
            "shared": True,
            "sync": {
                "revision": 5,
                "updatedAt": "2026-09-20T12:00:00Z",
                "updatedByProfileId": pid_a,
                "operationId": op_id,
                "memberProfileIds": [pid_a, pid_b]
            }
        }

        # Profile A has new rule committed at revision 10
        doc_a["configRevision"] = 10
        doc_a["rules"] = [dict(rule_template, id="rule_a", ruleCode=code)]
        atomic_write_json(self.base_dir / "ProfileA" / "config.json", doc_a)

        # Profile B remains at old state (revision 1)
        doc_b["configRevision"] = 1
        doc_b["rules"] = []
        atomic_write_json(self.base_dir / "ProfileB" / "config.json", doc_b)

        # Simulate left-behind .sync_op file in ProfileB
        target_doc_b = json.loads(json.dumps(doc_b))
        target_doc_b["configRevision"] = 2
        target_doc_b["rules"] = [dict(rule_template, id="rule_b", ruleCode=code)]

        op_file = self.base_dir / "ProfileB" / f".sync_op_{op_id}.json"
        atomic_write_json(op_file, {
            "operationId": op_id,
            "profileName": "ProfileB",
            "targetRevision": 2,
            "timestamp": "2026-09-20T12:00:00Z",
            "document": target_doc_b
        })
        self.assertTrue(op_file.is_file())

        # Run crash recovery reconciliation
        recon_res = self.manager.reconcile_crash_recovery()
        self.assertTrue(recon_res.get("ok"))
        self.assertIn(f"ProfileB:{op_id}", recon_res.get("repaired", []))

        # Recovery file must be deleted
        self.assertFalse(op_file.exists())

        # ProfileB must now contain the repaired rule at target revision 2
        repaired_b = self.manager.get_profile_config("ProfileB")
        self.assertEqual(repaired_b.get("configRevision"), 2)
        self.assertEqual(len(repaired_b.get("rules", [])), 1)
        self.assertEqual(repaired_b["rules"][0]["reply"], "Repaired content")

    def test_lagging_replica_reconciliation(self):
        """ProfileA has updated linked rule at rev 4, ProfileB is lagging at rev 2 without sync_op file."""
        self.manager.create_profile("ProfileA")
        self.manager.create_profile("ProfileB")

        doc_a = self.manager.get_profile_config("ProfileA")
        doc_b = self.manager.get_profile_config("ProfileB")

        pid_a = doc_a["profileId"]
        pid_b = doc_b["profileId"]
        code = "MBS-LAGREPAIR"
        op_id = str(uuid.uuid4())

        # Leader rule at rev 4
        doc_a["rules"] = [
            {
                "id": "rule_a",
                "ruleCode": code,
                "name": "Leader Rule",
                "active": True,
                "keywords": ["leader_kw"],
                "reply": "Leader reply",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": 4,
                    "updatedAt": "2026-09-20T14:00:00Z",
                    "updatedByProfileId": pid_a,
                    "operationId": op_id,
                    "memberProfileIds": [pid_a, pid_b]
                }
            }
        ]
        doc_a["configRevision"] = 5
        atomic_write_json(self.base_dir / "ProfileA" / "config.json", doc_a)

        # Lagging rule at rev 2
        doc_b["rules"] = [
            {
                "id": "rule_b",
                "ruleCode": code,
                "name": "Lagging Rule",
                "active": False,  # Local field should stay untouched
                "keywords": ["old_kw"],
                "reply": "Old reply",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": 2,
                    "updatedAt": "2026-09-20T10:00:00Z",
                    "updatedByProfileId": pid_b,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [pid_a, pid_b]
                }
            }
        ]
        doc_b["configRevision"] = 3
        atomic_write_json(self.base_dir / "ProfileB" / "config.json", doc_b)

        # Run crash recovery reconciliation
        recon_res = self.manager.reconcile_crash_recovery()
        self.assertTrue(recon_res.get("ok"))
        self.assertIn(f"ProfileB:{code}", recon_res.get("repaired", []))

        # Check Profile B
        refreshed_b = self.manager.get_profile_config("ProfileB")
        self.assertEqual(refreshed_b.get("configRevision"), 4)
        rule_b_repaired = refreshed_b["rules"][0]
        # Synchronized allowlist matches leader
        self.assertEqual(rule_b_repaired["keywords"], ["leader_kw"])
        self.assertEqual(rule_b_repaired["reply"], "Leader reply")
        self.assertEqual(rule_b_repaired["sync"]["revision"], 4)
        # Local field preserved
        self.assertEqual(rule_b_repaired["active"], False)
        self.assertEqual(rule_b_repaired["id"], "rule_b")

    def test_split_brain_conflict_fails_closed(self):
        """Two profiles have linked rule with same code and same revision but different replies."""
        self.manager.create_profile("ProfileA")
        self.manager.create_profile("ProfileB")

        doc_a = self.manager.get_profile_config("ProfileA")
        doc_b = self.manager.get_profile_config("ProfileB")

        pid_a = doc_a["profileId"]
        pid_b = doc_b["profileId"]
        code = "MBS-CONFLICT"

        # Conflict setup: both revision 3, different reply
        doc_a["rules"] = [
            {
                "id": "rule_a",
                "ruleCode": code,
                "name": "Conflicting Rule A",
                "active": True,
                "keywords": ["kw"],
                "reply": "Reply A from Node A",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": 3,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": pid_a,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [pid_a, pid_b]
                }
            }
        ]
        atomic_write_json(self.base_dir / "ProfileA" / "config.json", doc_a)

        doc_b["rules"] = [
            {
                "id": "rule_b",
                "ruleCode": code,
                "name": "Conflicting Rule B",
                "active": True,
                "keywords": ["kw"],
                "reply": "Reply B from Node B",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": 3,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": pid_b,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [pid_a, pid_b]
                }
            }
        ]
        atomic_write_json(self.base_dir / "ProfileB" / "config.json", doc_b)

        recon_res = self.manager.reconcile_crash_recovery()
        self.assertFalse(recon_res.get("ok"))
        conflicts = recon_res.get("conflicts", [])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["ruleCode"], code)
        self.assertEqual(conflicts[0]["revision"], 3)
        self.assertIn("ProfileA", conflicts[0]["profiles"])
        self.assertIn("ProfileB", conflicts[0]["profiles"])

        # Neither file was overwritten
        fresh_a = self.manager.get_profile_config("ProfileA")
        fresh_b = self.manager.get_profile_config("ProfileB")
        self.assertEqual(fresh_a["rules"][0]["reply"], "Reply A from Node A")
        self.assertEqual(fresh_b["rules"][0]["reply"], "Reply B from Node B")


if __name__ == "__main__":
    unittest.main()
