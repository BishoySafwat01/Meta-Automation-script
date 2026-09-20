#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — V6.5.0 Contract Tests: Local Rule Metadata
Tests:
1. Missing code receives a valid Crockford code.
2. Existing valid code remains unchanged during normal loads and saves.
3. Generated codes contain none of I, L, O, or U.
4. Duplicate generated codes trigger retry.
5. Duplicate persisted codes fail validation / resolve to unique codes.
6. Repeated load/save does not rotate codes.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from profile_manager import (
    ProfileManager,
    CROCKFORD_ALPHABET,
    RULE_CODE_REGEX,
    generate_rule_code,
    allocate_unique_rule_code,
    normalize_local_rules,
)


class TestProfileRuleMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp_dir.name)
        self.manager = ProfileManager(base_dir=self.base_dir)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_missing_code_receives_valid_crockford_code(self):
        """A rule without ruleCode receives a valid Crockford Base32 code upon normalization."""
        raw_rules = [
            {
                "id": "rule_test_1",
                "name": "Test Rule",
                "keywords": ["test"],
                "reply": "Reply text",
                "matchType": "ultra_exact",
            }
        ]
        norm = normalize_local_rules(raw_rules)
        self.assertEqual(len(norm), 1)
        code = norm[0].get("ruleCode")
        self.assertIsNotNone(code)
        self.assertTrue(
            RULE_CODE_REGEX.match(code),
            f"ruleCode '{code}' does not match pattern {RULE_CODE_REGEX.pattern}",
        )

    def test_existing_valid_code_remains_unchanged(self):
        """An existing valid ruleCode must NOT be modified or rotated."""
        valid_code = "MBS-7Q2N8K4R"
        raw_rules = [
            {
                "id": "rule_test_2",
                "ruleCode": valid_code,
                "name": "Existing Valid Code",
                "keywords": ["hello"],
                "reply": "World",
                "matchType": "ultra_exact",
            }
        ]
        norm = normalize_local_rules(raw_rules)
        self.assertEqual(norm[0]["ruleCode"], valid_code)

    def test_generated_codes_exclude_ilou(self):
        """Generated codes must strictly exclude ambiguous characters I, L, O, and U."""
        for _ in range(1000):
            code = generate_rule_code()
            self.assertTrue(RULE_CODE_REGEX.match(code))
            body = code[4:]  # Strip "MBS-"
            for forbidden_char in ("I", "L", "O", "U"):
                self.assertNotIn(
                    forbidden_char,
                    body,
                    f"Forbidden Crockford character '{forbidden_char}' found in '{code}'",
                )

    def test_duplicate_generated_codes_trigger_retry(self):
        """Collision detection must retry code generation when a code collides with existing_codes."""
        existing = {"MBS-11111111", "MBS-22222222"}
        calls = [0]

        def mock_generate():
            calls[0] += 1
            if calls[0] == 1:
                return "MBS-11111111"  # Collides on first attempt
            return "MBS-33333333"  # Succeeds on second attempt

        with patch("profile_manager.generate_rule_code", side_effect=mock_generate):
            allocated = allocate_unique_rule_code(existing)
            self.assertEqual(allocated, "MBS-33333333")
            self.assertEqual(calls[0], 2)

    def test_duplicate_persisted_codes_resolve_to_unique(self):
        """When duplicate ruleCodes exist in the input, normalization ensures all codes become unique."""
        colliding_code = "MBS-7Q2N8K4R"
        raw_rules = [
            {
                "id": "rule_dup_1",
                "ruleCode": colliding_code,
                "name": "Rule 1",
                "keywords": ["a"],
                "reply": "Reply 1",
            },
            {
                "id": "rule_dup_2",
                "ruleCode": colliding_code,
                "name": "Rule 2",
                "keywords": ["b"],
                "reply": "Reply 2",
            },
        ]
        norm = normalize_local_rules(raw_rules)
        self.assertEqual(len(norm), 2)
        code1 = norm[0]["ruleCode"]
        code2 = norm[1]["ruleCode"]
        self.assertNotEqual(code1, code2)
        self.assertTrue(RULE_CODE_REGEX.match(code1))
        self.assertTrue(RULE_CODE_REGEX.match(code2))

    def test_repeated_load_save_does_not_rotate_codes(self):
        """Repeatedly loading and saving a profile must preserve ruleCode values stably."""
        self.manager.create_profile("Profile_Stable_Codes")
        doc = self.manager.get_profile_config("Profile_Stable_Codes")
        doc["rules"] = [
            {
                "id": "rule_stable_1",
                "name": "Rule Alpha",
                "keywords": ["alpha"],
                "reply": "Beta",
                "matchType": "ultra_exact",
            },
            {
                "id": "rule_stable_2",
                "name": "Rule Gamma",
                "keywords": ["gamma"],
                "reply": "Delta",
                "matchType": "contains",
            },
        ]
        # First save allocates codes
        self.manager.save_profile_config("Profile_Stable_Codes", doc)

        doc_after_first = self.manager.get_profile_config("Profile_Stable_Codes")
        code_alpha = doc_after_first["rules"][0]["ruleCode"]
        code_gamma = doc_after_first["rules"][1]["ruleCode"]
        self.assertTrue(RULE_CODE_REGEX.match(code_alpha))
        self.assertTrue(RULE_CODE_REGEX.match(code_gamma))

        # Re-save 5 times
        for _ in range(5):
            reloaded = self.manager.get_profile_config("Profile_Stable_Codes")
            self.manager.save_profile_config("Profile_Stable_Codes", reloaded)

        final_doc = self.manager.get_profile_config("Profile_Stable_Codes")
        self.assertEqual(final_doc["rules"][0]["ruleCode"], code_alpha)
        self.assertEqual(final_doc["rules"][1]["ruleCode"], code_gamma)


if __name__ == "__main__":
    unittest.main()
