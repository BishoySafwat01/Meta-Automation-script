#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — V6.5.0 Contract Tests: Scope-Freeze & Anti-Regression Invariants
Tests:
1. Shipping Python and JavaScript runtime files contain ZERO forbidden distributed sync symbols.
2. The ordinary save path touches ONLY the active profile on disk.
3. ProfileLease enforces exclusive execution per profile without distributed coordination.
"""

import tempfile
import unittest
from pathlib import Path

from profile_manager import ProfileManager, ProfileLease


FORBIDDEN_SYMBOLS = [
    "ProfileCatalogLock",
    ".sync_op_",
    "MBS_ENABLE_SYNC_V2",
    "sync_v2_enabled",
    "LINKED_PROFILE_BUSY",
    "delete_everywhere",
    "reconcile_sync",
]

# Shipping runtime files that must remain strictly free of distributed sync machinery
SHIPPING_RUNTIME_FILES = [
    "profile_manager.py",
    "main.py",
    "desktop_app.py",
    "bot_script.js",
    "meta_inbox_userscript.user.js",
    "gui/app.js",
    "gui/index.html",
]


class TestProfileScopeFreeze(unittest.TestCase):
    def test_shipping_runtime_files_contain_no_forbidden_symbols(self):
        """Shipping Python and JavaScript runtime files must not contain any forbidden symbols."""
        root_dir = Path(__file__).resolve().parent.parent
        violations = []

        for rel_path in SHIPPING_RUNTIME_FILES:
            target_path = root_dir / rel_path
            self.assertTrue(target_path.is_file(), f"Shipping runtime file '{rel_path}' not found")
            content = target_path.read_text(encoding="utf-8")

            for sym in FORBIDDEN_SYMBOLS:
                if sym in content:
                    violations.append(f"{rel_path} contains forbidden symbol: '{sym}'")

        self.assertEqual(
            len(violations),
            0,
            f"Scope freeze violations detected in shipping runtime files:\n" + "\n".join(violations),
        )

    def test_ordinary_save_path_touches_only_active_profile(self):
        """The ordinary save_profile_config path must touch only the target profile's files."""
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td)
            manager = ProfileManager(base_dir=base_dir)

            manager.create_profile("ProfileAlpha")
            manager.create_profile("ProfileBeta")

            alpha_cfg_path = manager.get_profile_config_path("ProfileAlpha")
            beta_cfg_path = manager.get_profile_config_path("ProfileBeta")

            beta_mtime_before = beta_cfg_path.stat().st_mtime_ns
            beta_content_before = beta_cfg_path.read_bytes()

            # Save mutation to ProfileAlpha
            alpha_doc = manager.get_profile_config("ProfileAlpha")
            alpha_doc["rules"].append({
                "name": "Alpha Specific Rule",
                "keywords": ["alpha"],
                "reply": "Alpha Reply",
            })
            save_ok = manager.save_profile_config("ProfileAlpha", alpha_doc)
            self.assertTrue(save_ok)

            # ProfileBeta must be completely untouched
            beta_mtime_after = beta_cfg_path.stat().st_mtime_ns
            beta_content_after = beta_cfg_path.read_bytes()

            self.assertEqual(beta_mtime_before, beta_mtime_after)
            self.assertEqual(beta_content_before, beta_content_after)

    def test_single_profile_lease_integrity(self):
        """ProfileLease provides exclusive process locking per profile directory."""
        with tempfile.TemporaryDirectory() as td:
            pdir = Path(td) / "TestProfile"
            pdir.mkdir(parents=True, exist_ok=True)

            lease1 = ProfileLease(pdir)
            lease1.acquire()

            # Second lease on same directory must raise RuntimeError
            lease2 = ProfileLease(pdir)
            with self.assertRaises(RuntimeError) as ctx:
                lease2.acquire()
            self.assertIn("PROFILE_ALREADY_RUNNING", str(ctx.exception))

            lease1.release()

            # Re-acquisition now succeeds
            lease2.acquire()
            lease2.release()


if __name__ == "__main__":
    unittest.main()
