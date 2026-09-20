#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — Phase 2: Profile Portability & Admission Quarantine Test Suite
Tests:
1. Pure Folder Portability: A single profile copied to an isolated new root works completely independently with zero external files or shared databases.
2. Duplicate Profile ID Regeneration: Importing a profile with a duplicate profileId generates a fresh UUID.
3. Rule Code Collision Quarantine - Recode Resolution: Independent recoding assigns fresh Base32 codes to colliding rules.
4. Rule Code Collision Quarantine - Link Resolution: Explicit admission links the rule into memberProfileIds.
5. Survivor Flag Repair after Profile Removal: Dropping a profile updates memberProfileIds in surviving profiles.
"""

import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from profile_manager import (
    ProfileManager,
    RuleSchemaValidator,
    atomic_write_json,
    generate_profile_id
)


class TestProfilePortability(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir, sync_v2_enabled=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_pure_folder_portability(self):
        """A profile folder copied to a completely isolated root loads, validates, and saves without peer profiles."""
        self.manager.create_profile("IsolatedNode")
        doc = self.manager.get_profile_config("IsolatedNode")
        code = self.manager.allocator.allocate_code()
        doc["rules"] = [
            {
                "id": "rule_iso_1",
                "ruleCode": code,
                "name": "Self-Contained Rule",
                "active": True,
                "keywords": ["portable"],
                "reply": "I am fully portable",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": False,
                "shared": False,
                "sync": {
                    "revision": 0,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": doc["profileId"],
                    "operationId": "00000000-0000-0000-0000-000000000001",
                    "memberProfileIds": [doc["profileId"]]
                }
            }
        ]
        self.manager.save_profile_config_result("IsolatedNode", doc)

        # Copy "IsolatedNode" directory to a brand new root
        with tempfile.TemporaryDirectory() as foreign_root:
            src_dir = self.base_dir / "IsolatedNode"
            dst_dir = Path(foreign_root) / "IsolatedNode"
            shutil.copytree(src_dir, dst_dir)

            foreign_manager = ProfileManager(base_dir=Path(foreign_root), sync_v2_enabled=True)
            loaded_doc = foreign_manager.get_profile_config("IsolatedNode")
            self.assertIsNotNone(loaded_doc)
            self.assertEqual(loaded_doc["profileId"], doc["profileId"])
            self.assertEqual(len(loaded_doc["rules"]), 1)
            self.assertEqual(loaded_doc["rules"][0]["ruleCode"], code)

            # Assert Schema V2 validation passes cleanly
            valid, errs = RuleSchemaValidator.validate_profile(loaded_doc)
            self.assertTrue(valid, f"Validation errors: {errs}")

            # Mutate and save in isolated environment
            loaded_doc["rules"][0]["reply"] = "Updated in isolation"
            save_res = foreign_manager.save_profile_config_result("IsolatedNode", loaded_doc)
            self.assertTrue(save_res.ok)
            saved_doc = foreign_manager.get_profile_config("IsolatedNode")
            self.assertEqual(saved_doc["rules"][0]["reply"], "Updated in isolation")

    def test_duplicate_profile_id_regeneration_on_admission(self):
        """When an imported folder has the same profileId as an existing profile, admission generates a fresh UUID."""
        self.manager.create_profile("LocalNode")
        local_doc = self.manager.get_profile_config("LocalNode")
        colliding_pid = local_doc["profileId"]

        # Create external profile with identical profileId
        imported_dir = self.base_dir / "ImportedNode"
        imported_dir.mkdir(parents=True, exist_ok=True)
        code = self.manager.allocator.allocate_code()
        external_doc = {
            "schemaVersion": 2,
            "profileId": colliding_pid,  # Duplicate!
            "profileName": "ImportedNode",
            "configRevision": 1,
            "rules": [
                {
                    "id": "rule_ext_1",
                    "ruleCode": code,
                    "name": "External Rule",
                    "active": True,
                    "keywords": ["external"],
                    "reply": "External reply",
                    "matchType": "ultra_exact",
                    "caseSensitive": False,
                    "isLinked": False,
                    "shared": False,
                    "sync": {
                        "revision": 0,
                        "updatedAt": "2026-09-20T12:00:00Z",
                        "updatedByProfileId": colliding_pid,
                        "operationId": "00000000-0000-0000-0000-000000000002",
                        "memberProfileIds": [colliding_pid]
                    }
                }
            ]
        }
        atomic_write_json(imported_dir / "config.json", external_doc)

        admit_res = self.manager.admit_imported_profile("ImportedNode", collision_resolution="recode")
        self.assertNotEqual(admit_res["profileId"], colliding_pid)
        self.assertTrue(RuleSchemaValidator.is_valid_uuid(admit_res["profileId"]))

        # Check refreshed config
        refreshed = self.manager.get_profile_config("ImportedNode")
        self.assertEqual(refreshed["profileId"], admit_res["profileId"])
        self.assertNotEqual(refreshed["profileId"], local_doc["profileId"])

    def test_external_rule_code_collision_recode_resolution(self):
        """When an imported profile's ruleCode collides with an existing profile, recode resolution generates a fresh code."""
        self.manager.create_profile("NodeA")
        doc_a = self.manager.get_profile_config("NodeA")
        code_a = self.manager.allocator.allocate_code()
        doc_a["rules"] = [
            {
                "id": "rule_a",
                "ruleCode": code_a,
                "name": "Existing Rule",
                "active": True,
                "keywords": ["existing"],
                "reply": "Existing Node A reply",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": False,
                "shared": False,
                "sync": {
                    "revision": 0,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": doc_a["profileId"],
                    "operationId": "00000000-0000-0000-0000-000000000003",
                    "memberProfileIds": [doc_a["profileId"]]
                }
            }
        ]
        self.manager.save_profile_config_result("NodeA", doc_a)

        # External folder imported with same ruleCode but from outside (different profileId not in memberProfileIds)
        ext_dir = self.base_dir / "NodeB_Imported"
        ext_dir.mkdir(parents=True, exist_ok=True)
        ext_pid = generate_profile_id()
        ext_doc = {
            "schemaVersion": 2,
            "profileId": ext_pid,
            "profileName": "NodeB_Imported",
            "configRevision": 1,
            "rules": [
                {
                    "id": "rule_b",
                    "ruleCode": code_a,  # Colliding ruleCode!
                    "name": "Foreign Colliding Rule",
                    "active": True,
                    "keywords": ["foreign"],
                    "reply": "Foreign reply",
                    "matchType": "ultra_exact",
                    "caseSensitive": False,
                    "isLinked": False,
                    "shared": False,
                    "sync": {
                        "revision": 0,
                        "updatedAt": "2026-09-20T12:00:00Z",
                        "updatedByProfileId": ext_pid,
                        "operationId": "00000000-0000-0000-0000-000000000004",
                        "memberProfileIds": [ext_pid]
                    }
                }
            ]
        }
        atomic_write_json(ext_dir / "config.json", ext_doc)

        admit_res = self.manager.admit_imported_profile("NodeB_Imported", collision_resolution="recode")
        self.assertEqual(len(admit_res["reCodedRules"]), 1)
        refreshed_b = self.manager.get_profile_config("NodeB_Imported")
        new_code = refreshed_b["rules"][0]["ruleCode"]
        self.assertNotEqual(new_code, code_a)
        self.assertTrue(new_code.startswith("MBS-"))
        self.assertFalse(refreshed_b["rules"][0]["isLinked"])

        # NodeA should still have original code_a
        fresh_a = self.manager.get_profile_config("NodeA")
        self.assertEqual(fresh_a["rules"][0]["ruleCode"], code_a)

    def test_external_rule_code_collision_link_resolution(self):
        """When an imported profile's ruleCode collides and operator chooses 'link', it is admitted into memberProfileIds."""
        self.manager.create_profile("NodeA")
        doc_a = self.manager.get_profile_config("NodeA")
        code_a = self.manager.allocator.allocate_code()
        doc_a["rules"] = [
            {
                "id": "rule_a",
                "ruleCode": code_a,
                "name": "Linked Rule",
                "active": True,
                "keywords": ["common"],
                "reply": "Common reply",
                "matchType": "ultra_exact",
                "caseSensitive": False,
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": 1,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": doc_a["profileId"],
                    "operationId": "00000000-0000-0000-0000-000000000005",
                    "memberProfileIds": [doc_a["profileId"]]
                }
            }
        ]
        self.manager.save_profile_config_result("NodeA", doc_a)

        ext_dir = self.base_dir / "NodeB_Imported"
        ext_dir.mkdir(parents=True, exist_ok=True)
        ext_pid = generate_profile_id()
        ext_doc = {
            "schemaVersion": 2,
            "profileId": ext_pid,
            "profileName": "NodeB_Imported",
            "configRevision": 1,
            "rules": [
                {
                    "id": "rule_b",
                    "ruleCode": code_a,  # Same ruleCode
                    "name": "Candidate Rule",
                    "active": True,
                    "keywords": ["common"],
                    "reply": "Common reply",
                    "matchType": "ultra_exact",
                    "caseSensitive": False,
                    "isLinked": False,
                    "shared": False,
                    "sync": {
                        "revision": 0,
                        "updatedAt": "2026-09-20T12:00:00Z",
                        "updatedByProfileId": ext_pid,
                        "operationId": "00000000-0000-0000-0000-000000000006",
                        "memberProfileIds": [ext_pid]
                    }
                }
            ]
        }
        atomic_write_json(ext_dir / "config.json", ext_doc)

        admit_res = self.manager.admit_imported_profile("NodeB_Imported", collision_resolution="link")
        self.assertIn(code_a, admit_res["linkedRules"])

        refreshed_b = self.manager.get_profile_config("NodeB_Imported")
        self.assertEqual(refreshed_b["rules"][0]["ruleCode"], code_a)
        self.assertTrue(refreshed_b["rules"][0]["isLinked"])
        self.assertIn(ext_pid, refreshed_b["rules"][0]["sync"]["memberProfileIds"])

    def test_survivor_flag_repair_after_profile_removal(self):
        """When a profile directory is removed, surviving profiles have memberProfileIds cleaned up."""
        self.manager.create_profile("Profile1")
        self.manager.create_profile("Profile2")

        doc1 = self.manager.get_profile_config("Profile1")
        doc2 = self.manager.get_profile_config("Profile2")
        pid1 = doc1["profileId"]
        pid2 = doc2["profileId"]

        code = self.manager.allocator.allocate_code()
        rule_proto = {
            "name": "Shared Rule",
            "active": True,
            "keywords": ["shared"],
            "reply": "Shared",
            "matchType": "ultra_exact",
            "caseSensitive": False,
            "isLinked": True,
            "shared": True,
            "sync": {
                "revision": 1,
                "updatedAt": "2026-09-20T12:00:00Z",
                "updatedByProfileId": pid1,
                "operationId": "00000000-0000-0000-0000-000000000007",
                "memberProfileIds": [pid1, pid2]
            }
        }
        doc1["rules"] = [dict(rule_proto, id="r1", ruleCode=code)]
        doc2["rules"] = [dict(rule_proto, id="r2", ruleCode=code)]

        self.manager.save_profile_config_result("Profile1", doc1)
        self.manager.save_profile_config_result("Profile2", doc2)

        # Verify both have [pid1, pid2]
        d1 = self.manager.get_profile_config("Profile1")
        self.assertIn(pid2, d1["rules"][0]["sync"]["memberProfileIds"])

        # Delete Profile2 directory from disk
        shutil.rmtree(self.base_dir / "Profile2")

        # Invoke survivor repair
        self.manager.repair_survivors_after_profile_removal(pid2, {code})

        repaired_1 = self.manager.get_profile_config("Profile1")
        members = repaired_1["rules"][0]["sync"]["memberProfileIds"]
        self.assertNotIn(pid2, members)
        self.assertEqual(members, [pid1])


if __name__ == "__main__":
    unittest.main()
