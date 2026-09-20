#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — Phase 2: Cross-Profile Synchronization Engine Test Suite
Tests:
1. Coordinated Propagation across Linked Profiles (allowlist fields)
2. Local Field Preservation (id, name, active, order)
3. Stale Config Revision Rejection (STALE_CONFIG_REVISION)
4. Stale Link Revision Rejection (STALE_LINK_REVISION)
5. No-Op Save Behavior (no spurious revision bumps)
6. Canonical Return State in SaveResult
7. Membership Operations: clone, link, unlink, delete (local & everywhere)
8. Backward Compatibility Wrapper (save_profile_config returning bool)
"""

import os
import json
import uuid
import tempfile
import unittest
from pathlib import Path

from profile_manager import (
    ProfileManager,
    SaveResult,
    generate_rule_code,
    generate_rule_id,
    generate_profile_id
)


class TestProfileSyncEngine(unittest.TestCase):
    """Test cross-profile synchronized propagation and membership operations."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.pm = ProfileManager(base_dir=self.base_dir, sync_v2_enabled=True)

        # Seed two profiles: Cairo and Alexandria
        self.prof_a = self.pm.create_profile("Cairo")
        self.prof_b = self.pm.create_profile("Alexandria")

        # Create initial rule in Cairo
        self.cairo_doc = self.pm.get_profile_config("Cairo")
        self.shared_code = generate_rule_code()
        self.rule_cairo = {
            "id": generate_rule_id(),
            "name": "سعر المشد - القاهرة",
            "ruleCode": self.shared_code,
            "keywords": ["سعر المشد"],
            "keyword": "سعر المشد",
            "contextKeywords": ["مصر"],
            "contextKeyword": "مصر",
            "reply": "السعر 300 ج.م",
            "matchType": "ultra_exact",
            "contextMatchType": "contains",
            "caseSensitive": False,
            "active": True,
            "isLinked": False,
            "shared": False,
            "sync": {
                "revision": 1,
                "updatedAt": "2026-09-20T12:00:00Z",
                "updatedByProfileId": self.cairo_doc["profileId"],
                "operationId": str(uuid.uuid4()),
                "memberProfileIds": [self.cairo_doc["profileId"]]
            }
        }
        self.cairo_doc["rules"] = [self.rule_cairo]
        res_save = self.pm.save_profile_config_result("Cairo", self.cairo_doc)
        self.assertTrue(res_save.ok)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_link_rule_by_code_and_propagate(self):
        """Linking a rule into Alexandria and modifying Cairo propagates allowlist to Alexandria."""
        # 1. Link into Alexandria
        link_res = self.pm.link_rule_by_code(
            target_profile="Alexandria",
            existing_rule_code=self.shared_code,
            draft_overrides={"name": "سعر المشد - إسكندرية", "active": False}
        )
        self.assertTrue(link_res.ok, f"Link failed: {link_res.message}")

        # Verify Alexandria has the linked rule with local name and active=False
        alex_doc = self.pm.get_profile_config("Alexandria")
        self.assertEqual(len(alex_doc["rules"]), 1)
        r_alex = alex_doc["rules"][0]
        self.assertEqual(r_alex["ruleCode"], self.shared_code)
        self.assertEqual(r_alex["name"], "سعر المشد - إسكندرية")
        self.assertFalse(r_alex["active"])
        self.assertTrue(r_alex["isLinked"])
        self.assertTrue(r_alex["shared"])

        # Verify Cairo is now marked isLinked=True
        cairo_doc = self.pm.get_profile_config("Cairo")
        self.assertTrue(cairo_doc["rules"][0]["isLinked"])
        self.assertTrue(cairo_doc["rules"][0]["shared"])

        # 2. Modify allowlist fields in Cairo (keywords and reply)
        cairo_doc["rules"][0]["keywords"] = ["سعر المشد الأصلي", "بكام المشد"]
        cairo_doc["rules"][0]["reply"] = "السعر الجديد 350 ج.م"
        cairo_doc["rules"][0]["matchType"] = "contains"

        # Save Cairo
        save_res = self.pm.save_profile_config_result("Cairo", cairo_doc)
        self.assertTrue(save_res.ok, f"Save failed: {save_res.message}")
        self.assertIn("Alexandria", save_res.changedProfiles)

        # 3. Assert Alexandria disk file was automatically updated with allowlist fields
        alex_disk = self.pm.get_profile_config("Alexandria")
        r_alex_disk = alex_disk["rules"][0]
        self.assertEqual(r_alex_disk["keywords"], ["سعر المشد الأصلي", "بكام المشد"])
        self.assertEqual(r_alex_disk["keyword"], "سعر المشد الأصلي, بكام المشد")
        self.assertEqual(r_alex_disk["reply"], "السعر الجديد 350 ج.م")
        self.assertEqual(r_alex_disk["matchType"], "contains")

        # 4. Assert Alexandria local fields remained preserved!
        self.assertEqual(r_alex_disk["id"], r_alex["id"])
        self.assertEqual(r_alex_disk["name"], "سعر المشد - إسكندرية")
        self.assertFalse(r_alex_disk["active"])

        # Sync revision incremented
        self.assertGreater(r_alex_disk["sync"]["revision"], 1)

    def test_stale_config_revision_rejection(self):
        """Saving with an outdated expected_revision must be rejected with STALE_CONFIG_REVISION."""
        cairo_doc = self.pm.get_profile_config("Cairo")
        current_rev = cairo_doc.get("configRevision", 0)

        # Submit with expected_revision = current_rev - 1
        stale_rev = current_rev - 1
        res = self.pm.save_profile_config_result("Cairo", cairo_doc, expected_revision=stale_rev)
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "STALE_CONFIG_REVISION")

    def test_stale_link_revision_rejection(self):
        """If a target profile has a newer sync revision, source save fails closed with STALE_LINK_REVISION."""
        # Link Alexandria
        self.pm.link_rule_by_code("Alexandria", self.shared_code)

        # Artificially increment Alexandria's sync revision to 10
        alex_doc = self.pm.get_profile_config("Alexandria")
        alex_doc["rules"][0]["sync"]["revision"] = 10
        self.pm.coordinator.save_profile_config_result("Alexandria", alex_doc)

        # Now try to save Cairo which still has revision <= 2
        cairo_doc = self.pm.get_profile_config("Cairo")
        cairo_doc["rules"][0]["reply"] = "Stale attempt"
        res = self.pm.save_profile_config_result("Cairo", cairo_doc)
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "STALE_LINK_REVISION")

    def test_no_op_save_does_not_bump_revisions(self):
        """Saving without allowlist changes must not increment linked target profile revisions."""
        self.pm.link_rule_by_code("Alexandria", self.shared_code)
        alex_before = self.pm.get_profile_config("Alexandria")
        alex_rev_before = alex_before.get("configRevision", 0)
        link_rev_before = alex_before["rules"][0]["sync"]["revision"]

        # Save Cairo with unchanged allowlist (e.g. only modifying auto_start setting)
        cairo_doc = self.pm.get_profile_config("Cairo")
        cairo_doc["auto_start"] = True
        res = self.pm.save_profile_config_result("Cairo", cairo_doc)
        self.assertTrue(res.ok)
        self.assertEqual(res.changedProfiles, [])

        alex_after = self.pm.get_profile_config("Alexandria")
        self.assertEqual(alex_after.get("configRevision", 0), alex_rev_before)
        self.assertEqual(alex_after["rules"][0]["sync"]["revision"], link_rev_before)

    def test_clone_rule_creates_independent_rule(self):
        """Cloning a rule must create fresh IDs and codes; future edits do not propagate."""
        cairo_doc = self.pm.get_profile_config("Cairo")
        cairo_rule_id = cairo_doc["rules"][0]["id"]

        clone_res = self.pm.clone_rule(
            source_profile="Cairo",
            target_profile="Alexandria",
            rule_id=cairo_rule_id
        )
        self.assertTrue(clone_res.ok, f"Clone failed: {clone_res.message}")

        alex_doc = self.pm.get_profile_config("Alexandria")
        self.assertEqual(len(alex_doc["rules"]), 1)
        cloned_r = alex_doc["rules"][0]

        # Must have fresh ID and fresh code
        self.assertNotEqual(cloned_r["id"], cairo_rule_id)
        self.assertNotEqual(cloned_r["ruleCode"], self.shared_code)
        self.assertFalse(cloned_r["isLinked"])

        # Subsequent edits to Cairo do not affect Alexandria
        cairo_doc["rules"][0]["reply"] = "300 -> 999"
        self.pm.save_profile_config_result("Cairo", cairo_doc)

        alex_after = self.pm.get_profile_config("Alexandria")
        self.assertEqual(alex_after["rules"][0]["reply"], "السعر 300 ج.م")

    def test_unlink_rule(self):
        """Unlinking a rule assigns a fresh ruleCode and updates survivors."""
        self.pm.link_rule_by_code("Alexandria", self.shared_code)
        alex_doc = self.pm.get_profile_config("Alexandria")
        alex_rule_id = alex_doc["rules"][0]["id"]

        unlink_res = self.pm.unlink_rule("Alexandria", alex_rule_id)
        self.assertTrue(unlink_res.ok)

        # Alexandria rule now has fresh independent code
        alex_after = self.pm.get_profile_config("Alexandria")
        self.assertNotEqual(alex_after["rules"][0]["ruleCode"], self.shared_code)
        self.assertFalse(alex_after["rules"][0]["isLinked"])

        # Cairo rule now has 0 other members, so isLinked becomes False
        cairo_after = self.pm.get_profile_config("Cairo")
        self.assertFalse(cairo_after["rules"][0]["isLinked"])

    def test_delete_rule_local_vs_everywhere(self):
        """Deleting rule locally removes it from one profile; everywhere deletes from all."""
        # 1. Test local delete
        self.pm.link_rule_by_code("Alexandria", self.shared_code)
        alex_doc = self.pm.get_profile_config("Alexandria")
        alex_rule_id = alex_doc["rules"][0]["id"]

        del_local_res = self.pm.delete_rule("Alexandria", alex_rule_id, everywhere=False)
        self.assertTrue(del_local_res.ok)

        self.assertEqual(len(self.pm.get_profile_config("Alexandria")["rules"]), 0)
        # Cairo still has its rule, but unlinked
        cairo_doc = self.pm.get_profile_config("Cairo")
        self.assertEqual(len(cairo_doc["rules"]), 1)
        self.assertFalse(cairo_doc["rules"][0]["isLinked"])

        # 2. Test delete everywhere
        self.pm.link_rule_by_code("Alexandria", self.shared_code)
        cairo_rule_id = cairo_doc["rules"][0]["id"]
        del_every_res = self.pm.delete_rule("Cairo", cairo_rule_id, everywhere=True)
        self.assertTrue(del_every_res.ok)

        self.assertEqual(len(self.pm.get_profile_config("Cairo")["rules"]), 0)
        self.assertEqual(len(self.pm.get_profile_config("Alexandria")["rules"]), 0)

    def test_backward_compatibility_save_wrapper(self):
        """save_profile_config must return True when sync_v2_enabled=True."""
        cairo_doc = self.pm.get_profile_config("Cairo")
        cairo_doc["rules"][0]["reply"] = "Updated via wrapper"
        success = self.pm.save_profile_config("Cairo", cairo_doc)
        self.assertIs(success, True)

        reloaded = self.pm.get_profile_config("Cairo")
        self.assertEqual(reloaded["rules"][0]["reply"], "Updated via wrapper")


if __name__ == "__main__":
    unittest.main()
