#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — Phase 2: Schema V2 & Migration Contracts Test Suite
Tests:
1. Crockford Base32 Generator & Alphabet Exclusion (0-9, A-Z excl. I, L, O, U)
2. Schema V2 Validation & Fail-Closed Errors (duplicate ruleCode, future schemaVersion, missing UUID)
3. Idempotent Migration Engine & Backup Preservation (config.pre-v2.backup.json)
4. Primary matchType Migration to 'ultra_exact' & Compatibility Mirrors
5. Unknown/Additional Properties Preservation
6. Imported External Identity Collision Quarantine & Admission
"""

import os
import json
import uuid
import shutil
import tempfile
import unittest
from pathlib import Path

from profile_manager import (
    ProfileManager,
    RuleSchemaValidator,
    RuleSchemaMigrator,
    RuleCodeAllocator,
    generate_crockford_base32,
    generate_rule_code,
    generate_rule_id,
    generate_profile_id,
    CROCKFORD_ALPHABET,
    CROCKFORD_REGEX,
    RULE_ID_REGEX,
    UUID_REGEX,
    FutureSchemaVersionError,
    DuplicateRuleCodeError,
    DuplicateProfileIdError
)


class TestCrockfordAndIdentityGeneration(unittest.TestCase):
    """Test identity generation, Crockford Base32 alphabet, and regex formats."""

    def test_crockford_alphabet_excludes_confusing_chars(self):
        """Crockford alphabet must exclude I, L, O, U to avoid human operator confusion."""
        self.assertEqual(len(CROCKFORD_ALPHABET), 32)
        for forbidden in ["I", "L", "O", "U"]:
            self.assertNotIn(forbidden, CROCKFORD_ALPHABET)

    def test_rule_code_format(self):
        """Rule code must strictly match MBS-[0-9A-HJKMNP-TV-Z]{8}."""
        for _ in range(100):
            code = generate_rule_code()
            self.assertTrue(bool(CROCKFORD_REGEX.match(code)), f"Code '{code}' does not match Crockford pattern")

    def test_rule_id_format(self):
        """Local rule instance ID must match rule_[0-9a-f]{32}."""
        for _ in range(50):
            r_id = generate_rule_id()
            self.assertTrue(bool(RULE_ID_REGEX.match(r_id)), f"Rule ID '{r_id}' does not match pattern")

    def test_profile_id_format(self):
        """Profile ID must be a standard RFC 4122 UUID v4."""
        for _ in range(50):
            pid = generate_profile_id()
            self.assertTrue(bool(UUID_REGEX.match(pid)), f"Profile ID '{pid}' is not a valid UUID")

    def test_code_allocator_collision_retry(self):
        """Allocator must detect existing codes and retry until a collision-free code is generated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            allocator = RuleCodeAllocator(Path(temp_dir))
            existing = {generate_rule_code() for _ in range(50)}
            existing_snapshot = set(existing)
            new_code = allocator.allocate_code(existing)
            self.assertTrue(bool(CROCKFORD_REGEX.match(new_code)))
            self.assertNotIn(new_code, existing_snapshot)


class TestSchemaV2Validation(unittest.TestCase):
    """Test RuleSchemaValidator against compliant, corrupt, and future configs."""

    def setUp(self):
        self.pid = str(uuid.uuid4())
        self.valid_profile = {
            "schemaVersion": 2,
            "profileId": self.pid,
            "configRevision": 0,
            "config": {"typingSpeed": 15},
            "auto_start": False,
            "rules": [
                {
                    "id": f"rule_{uuid.uuid4().hex}",
                    "name": "استفسار السعر",
                    "ruleCode": "MBS-7K2M9Q4X",
                    "keywords": ["سعر", "بكام"],
                    "keyword": "سعر, بكام",
                    "contextKeywords": ["مشد"],
                    "contextKeyword": "مشد",
                    "reply": "السعر 150 ج.م",
                    "matchType": "ultra_exact",
                    "contextMatchType": "contains",
                    "caseSensitive": False,
                    "active": True,
                    "isLinked": False,
                    "shared": False,
                    "sync": {
                        "revision": 0,
                        "updatedAt": "2026-09-20T12:00:00Z",
                        "updatedByProfileId": self.pid,
                        "operationId": str(uuid.uuid4()),
                        "memberProfileIds": [self.pid]
                    }
                }
            ]
        }

    def test_valid_profile_passes(self):
        ok, errors = RuleSchemaValidator.validate_profile(self.valid_profile)
        self.assertTrue(ok, f"Validation failed with errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_reject_duplicate_rule_code_within_profile(self):
        """A single profile must not contain duplicate ruleCode values."""
        duplicate_rule = dict(self.valid_profile["rules"][0])
        duplicate_rule["id"] = f"rule_{uuid.uuid4().hex}"
        self.valid_profile["rules"].append(duplicate_rule)

        with self.assertRaises(DuplicateRuleCodeError):
            RuleSchemaValidator.validate_profile(self.valid_profile)

    def test_reject_future_schema_version(self):
        """Future schemaVersion (e.g. 3) must be rejected fail-closed."""
        self.valid_profile["schemaVersion"] = 3
        with self.assertRaises(FutureSchemaVersionError):
            RuleSchemaValidator.validate_profile(self.valid_profile)

    def test_reject_invalid_profile_id(self):
        self.valid_profile["profileId"] = "not-a-uuid"
        ok, errors = RuleSchemaValidator.validate_profile(self.valid_profile)
        self.assertFalse(ok)
        self.assertTrue(any("profileId" in e for e in errors))

    def test_reject_invalid_match_type(self):
        self.valid_profile["rules"][0]["matchType"] = "INVALID_MODE"
        ok, errors = RuleSchemaValidator.validate_profile(self.valid_profile)
        self.assertFalse(ok)
        self.assertTrue(any("matchType" in e for e in errors))

    def test_reject_empty_keywords(self):
        self.valid_profile["rules"][0]["keywords"] = []
        ok, errors = RuleSchemaValidator.validate_profile(self.valid_profile)
        self.assertFalse(ok)
        self.assertTrue(any("keywords" in e for e in errors))

    def test_preserves_additional_properties(self):
        """Unknown or operator-specific properties must not be stripped by validation."""
        self.valid_profile["customSetting"] = "custom_value"
        self.valid_profile["rules"][0]["operatorTag"] = "summer_promo"
        ok, errors = RuleSchemaValidator.validate_profile(self.valid_profile)
        self.assertTrue(ok)
        self.assertEqual(self.valid_profile["customSetting"], "custom_value")
        self.assertEqual(self.valid_profile["rules"][0]["operatorTag"], "summer_promo")


class TestIdempotentMigration(unittest.TestCase):
    """Test idempotent migration from v1/legacy schemas to Schema V2."""

    def test_legacy_v1_migration_to_v2(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            pdir = base_dir / "Page_Cairo"
            pdir.mkdir(parents=True)

            legacy_config = {
                "rules": [
                    {
                        "id": "legacy_rule_1",
                        "name": "سعر المشد",
                        "keyword": "سعر المشد, بكام المشد",
                        "contextKeyword": "مصر",
                        "reply": "السعر 300 جنيه",
                        "matchType": "contains",
                        "active": True
                    },
                    {
                        "name": "استفسار الشحن",
                        "keyword": "شحن",
                        "reply": "الشحن مجاني",
                        "matchType": "exact",
                        "active": True
                    }
                ],
                "config": {
                    "typingSpeed": 12
                },
                "auto_start": True
            }

            migrator = RuleSchemaMigrator(base_dir)
            self.assertTrue(migrator.needs_migration(legacy_config))

            migrated, report = migrator.migrate_profile_data(pdir, legacy_config, write_backup=True)

            # 1. Backup created
            backup_file = pdir / "config.pre-v2.backup.json"
            self.assertTrue(backup_file.is_file(), "Backup file was not created")
            with open(backup_file, "r", encoding="utf-8") as bf:
                backup_data = json.load(bf)
            self.assertEqual(backup_data["rules"][0]["matchType"], "contains")

            # 2. Schema V2 fields added
            self.assertEqual(migrated["schemaVersion"], 2)
            self.assertTrue(RuleSchemaValidator.is_valid_uuid(migrated["profileId"]))
            self.assertEqual(migrated["configRevision"], 0)
            self.assertEqual(migrated["auto_start"], True)
            self.assertEqual(migrated["config"]["typingSpeed"], 12)

            # 3. Mandated primary matchType converted to 'ultra_exact'
            self.assertEqual(migrated["rules"][0]["matchType"], "ultra_exact")
            self.assertEqual(migrated["rules"][1]["matchType"], "ultra_exact")
            self.assertEqual(report["priorModes"]["legacy_rule_1"], "contains")

            # 4. Keyword arrays and compatibility mirrors
            self.assertEqual(migrated["rules"][0]["keywords"], ["سعر المشد", "بكام المشد"])
            self.assertEqual(migrated["rules"][0]["keyword"], "سعر المشد, بكام المشد")
            self.assertEqual(migrated["rules"][0]["contextKeywords"], ["مصر"])
            self.assertEqual(migrated["rules"][0]["contextKeyword"], "مصر")

            # 5. Rule codes allocated
            for r in migrated["rules"]:
                self.assertTrue(RuleSchemaValidator.is_valid_rule_code(r["ruleCode"]))
                self.assertTrue(RuleSchemaValidator.is_valid_rule_id(r["id"]))
                self.assertEqual(r["sync"]["revision"], 0)
                self.assertIn(migrated["profileId"], r["sync"]["memberProfileIds"])

            # 6. Idempotence: migrating an already migrated profile must not alter codes or backup
            mtime_before = backup_file.stat().st_mtime
            second_migrated, _ = migrator.migrate_profile_data(pdir, migrated, write_backup=True)
            self.assertEqual(migrated["profileId"], second_migrated["profileId"])
            self.assertEqual(migrated["rules"][0]["ruleCode"], second_migrated["rules"][0]["ruleCode"])
            self.assertEqual(backup_file.stat().st_mtime, mtime_before, "Backup was overwritten on second migration")

    def test_disabled_legacy_rules_handling(self):
        """Legacy rules with empty keywords or missing replies must be safely marked active: False."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pdir = Path(temp_dir) / "TestProf"
            pdir.mkdir(parents=True)
            broken_config = {
                "rules": [
                    {
                        "keyword": "",
                        "reply": "No keyword",
                        "matchType": "contains"
                    },
                    {
                        "keyword": "valid",
                        "reply": "",
                        "matchType": "contains"
                    }
                ]
            }
            migrator = RuleSchemaMigrator(Path(temp_dir))
            migrated, report = migrator.migrate_profile_data(pdir, broken_config, write_backup=False)
            self.assertFalse(migrated["rules"][0]["active"])
            self.assertFalse(migrated["rules"][1]["active"])
            self.assertEqual(len(report["warnings"]), 2)


if __name__ == "__main__":
    unittest.main()
