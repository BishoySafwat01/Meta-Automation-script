#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — V6.5.0 Contract Tests: Synchronous Rule Import/Cloning
Tests:
1. Self-import is rejected.
2. Import appends without replacing existing rules.
3. Multiple imported rules preserve source order.
4. Imported rules receive fresh IDs.
5. Imported rules receive fresh codes (never copies source codes).
6. Imported IDs and codes do not collide with destination data.
7. Source config.json remains byte-for-byte unchanged.
8. Literal spaces, commas, and newlines remain unchanged.
9. Failed imports leave destination bytes unchanged.
10. Empty-source and missing-source cases fail safely.
11. No link, revision-propagation, journal, or background synchronization state is created.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from profile_manager import (
    ProfileManager,
    RULE_CODE_REGEX,
    atomic_write_json,
)


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestProfileImport(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir)

        # Seed Source Profile with 3 distinct rules
        self.manager.create_profile("SourceProfile")
        src_doc = self.manager.get_profile_config("SourceProfile")
        src_doc["rules"] = [
            {
                "id": "src_rule_1",
                "ruleCode": "MBS-11111111",
                "name": "First Source Rule",
                "keywords": ["  leading space  ", "word, with, comma", "line1\nline2"],
                "reply": "Reply line 1\nReply line 2\nReply with, comma and  spaces ",
                "matchType": "ultra_exact",
                "caseSensitive": True,
            },
            {
                "id": "src_rule_2",
                "ruleCode": "MBS-22222222",
                "name": "Second Source Rule",
                "keywords": ["promo"],
                "reply": "Promo reply",
                "matchType": "contains",
                "caseSensitive": False,
            },
            {
                "id": "src_rule_3",
                "ruleCode": "MBS-33333333",
                "name": "Third Source Rule",
                "keywords": ["support"],
                "reply": "Support reply",
                "matchType": "exact",
                "caseSensitive": False,
            },
        ]
        self.manager.save_profile_config("SourceProfile", src_doc)

        # Seed Destination Profile with 1 existing rule
        self.manager.create_profile("DestProfile")
        dest_doc = self.manager.get_profile_config("DestProfile")
        dest_doc["rules"] = [
            {
                "id": "dest_existing_1",
                "ruleCode": "MBS-DDDDDDDD",
                "name": "Destination Pre-existing Rule",
                "keywords": ["dest_kw"],
                "reply": "Dest reply",
                "matchType": "ultra_exact",
                "caseSensitive": False,
            }
        ]
        self.manager.save_profile_config("DestProfile", dest_doc)
        dest_path = self.manager.get_profile_config_path("DestProfile")
        self.dest_sha = hashlib.sha256(dest_path.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_self_import_is_rejected(self):
        """Importing from a profile into itself must be rejected immediately."""
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="DestProfile",
            rule_ids=["dest_existing_1"],
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "SELF_IMPORT_REJECTED")

    def test_import_appends_without_replacing_existing_rules(self):
        """Importing rules must append them after existing rules without overwriting or deleting."""
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_1", "src_rule_2"],
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["importedCount"], 2)

        updated_dest = self.manager.get_profile_config("DestProfile")
        rules = updated_dest["rules"]
        self.assertEqual(len(rules), 3)  # 1 pre-existing + 2 imported
        self.assertEqual(rules[0]["id"], "dest_existing_1")
        self.assertEqual(rules[0]["ruleCode"], "MBS-DDDDDDDD")

    def test_multiple_imported_rules_preserve_source_order(self):
        """Multiple selected rules must be appended in the exact order they appeared in source."""
        # Select rule 1 and rule 3
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_3", "src_rule_1"],  # Requested out of order or in order
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])

        updated_dest = self.manager.get_profile_config("DestProfile")
        rules = updated_dest["rules"]
        # Imported rules should appear in selected source order
        self.assertEqual(rules[1]["name"], "First Source Rule")
        self.assertEqual(rules[2]["name"], "Third Source Rule")

    def test_imported_rules_receive_fresh_ids_and_codes(self):
        """Imported rules must receive brand-new IDs and codes, never copying the source codes."""
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_1", "src_rule_2"],
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])

        updated_dest = self.manager.get_profile_config("DestProfile")
        imported_rule_1 = updated_dest["rules"][1]
        imported_rule_2 = updated_dest["rules"][2]

        # Fresh IDs
        self.assertNotEqual(imported_rule_1["id"], "src_rule_1")
        self.assertNotEqual(imported_rule_2["id"], "src_rule_2")
        self.assertTrue(imported_rule_1["id"].startswith("rule_"))
        self.assertTrue(imported_rule_2["id"].startswith("rule_"))

        # Fresh ruleCodes matching Crockford pattern
        self.assertTrue(RULE_CODE_REGEX.match(imported_rule_1["ruleCode"]))
        self.assertTrue(RULE_CODE_REGEX.match(imported_rule_2["ruleCode"]))

        # Must NOT equal source codes
        self.assertNotEqual(imported_rule_1["ruleCode"], "MBS-11111111")
        self.assertNotEqual(imported_rule_2["ruleCode"], "MBS-22222222")

        # Destination codes must be mutually unique
        dest_codes = [r["ruleCode"] for r in updated_dest["rules"]]
        self.assertEqual(len(dest_codes), len(set(dest_codes)))

    def test_source_config_remains_byte_for_byte_unchanged(self):
        """Source profile config.json must remain 100% byte-for-byte identical before and after import."""
        src_path = self.manager.get_profile_config_path("SourceProfile")
        hash_before = compute_file_sha256(src_path)

        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_1", "src_rule_2", "src_rule_3"],
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])

        hash_after = compute_file_sha256(src_path)
        self.assertEqual(hash_before, hash_after)

    def test_literal_spaces_commas_newlines_remain_unchanged(self):
        """User-authored literal spaces, commas, and newlines must survive import verbatim."""
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_1"],
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])

        updated_dest = self.manager.get_profile_config("DestProfile")
        imported = updated_dest["rules"][1]

        # Check keywords array
        self.assertIn("  leading space  ", imported["keywords"])
        self.assertIn("word, with, comma", imported["keywords"])
        self.assertIn("line1\nline2", imported["keywords"])

        # Check reply text
        expected_reply = "Reply line 1\nReply line 2\nReply with, comma and  spaces "
        self.assertEqual(imported["reply"], expected_reply)

        # Check caseSensitive
        self.assertEqual(imported["caseSensitive"], True)

    def test_failed_imports_leave_destination_bytes_unchanged(self):
        """If an import fails, the destination config.json must not be modified."""
        dest_path = self.manager.get_profile_config_path("DestProfile")
        hash_before = compute_file_sha256(dest_path)

        # Non-existent rule ID fails
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["non_existent_rule_999"],
            target_sha=self.dest_sha,
        )
        self.assertFalse(res["ok"])
        self.assertEqual(res["code"], "RULES_NOT_FOUND")

        hash_after = compute_file_sha256(dest_path)
        self.assertEqual(hash_before, hash_after)

    def test_empty_source_and_missing_source_fail_safely(self):
        """Missing source or empty source profile returns structured error without crashing."""
        # Missing source
        res_missing = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="NonExistentProfile",
            rule_ids=["rule_1"],
            target_sha=self.dest_sha,
        )
        self.assertFalse(res_missing["ok"])
        self.assertEqual(res_missing["code"], "SOURCE_NOT_FOUND")

        # Empty source
        self.manager.create_profile("EmptyProfile")
        res_empty = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="EmptyProfile",
            rule_ids=["rule_1"],
            target_sha=self.dest_sha,
        )
        self.assertFalse(res_empty["ok"])
        self.assertEqual(res_empty["code"], "SOURCE_EMPTY")

    def test_no_sync_state_created(self):
        """Import must NOT attach any sync metadata, link flags, or revision tracking."""
        res = self.manager.import_rules_from_profile(
            target_profile="DestProfile",
            source_profile="SourceProfile",
            rule_ids=["src_rule_1"],
            target_sha=self.dest_sha,
        )
        self.assertTrue(res["ok"])

        updated_dest = self.manager.get_profile_config("DestProfile")
        imported = updated_dest["rules"][1]

        # No distributed sync keys
        for forbidden_key in ("isLinked", "shared", "sync", "memberProfileIds", "configRevision"):
            self.assertNotIn(forbidden_key, imported)
        self.assertNotIn("configRevision", updated_dest)


if __name__ == "__main__":
    unittest.main()
