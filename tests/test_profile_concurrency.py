#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — Phase 2: Concurrency & Lock Ordering Test Suite
Tests:
1. Multi-Process Catalog Locking (ProfileCatalogLock at profiles/.sync.lock)
2. Concurrent Crockford Base32 Code Allocation (zero collisions across threads)
3. Multi-Tenant Lease Ordering & Busy Target Rejection (LINKED_PROFILE_BUSY)
4. In-Process LeaseAuthority Reuse for Running Workers
"""

import os
import json
import time
import uuid
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from profile_manager import (
    ProfileManager,
    ProfileLease,
    LeaseAuthority,
    ProfileCatalogLock,
    RuleCodeAllocator,
    generate_rule_code,
    generate_rule_id,
    CatalogBusyError
)


class TestProfileConcurrency(unittest.TestCase):
    """Test OS-level catalog locking, concurrency, and lease authority mechanics."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        self.pm = ProfileManager(base_dir=self.base_dir, sync_v2_enabled=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_catalog_lock_mutual_exclusion(self):
        """ProfileCatalogLock must enforce mutual exclusion between separate lock holders."""
        execution_order = []

        def worker_fn(worker_id: int):
            with ProfileCatalogLock(self.base_dir, timeout=2.0):
                execution_order.append(f"start_{worker_id}")
                time.sleep(0.05)
                execution_order.append(f"end_{worker_id}")

        t1 = threading.Thread(target=worker_fn, args=(1,))
        t2 = threading.Thread(target=worker_fn, args=(2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # One worker must completely finish before the other starts
        self.assertEqual(len(execution_order), 4)
        if execution_order[0] == "start_1":
            self.assertEqual(execution_order, ["start_1", "end_1", "start_2", "end_2"])
        else:
            self.assertEqual(execution_order, ["start_2", "end_2", "start_1", "end_1"])

    def test_concurrent_code_allocation_zero_collisions(self):
        """Multiple concurrent threads allocating codes must produce zero duplicate codes."""
        allocator = RuleCodeAllocator(self.base_dir)
        allocated_codes = set()
        lock = threading.Lock()

        def allocate_batch():
            local_set = set()
            for _ in range(50):
                code = allocator.allocate_code(allocated_codes)
                with lock:
                    allocated_codes.add(code)
                local_set.add(code)
            return local_set

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(allocate_batch) for _ in range(5)]
            results = [f.result() for f in futures]

        # Total allocated must equal sum of lengths (zero collision)
        total_count = sum(len(r) for r in results)
        self.assertEqual(total_count, 250)
        self.assertEqual(len(allocated_codes), 250)

    def test_busy_linked_profile_aborts_without_writes(self):
        """If a linked target profile is held by an external process, saving must abort with LINKED_PROFILE_BUSY and zero disk changes."""
        self.pm.create_profile("Profile_A")
        self.pm.create_profile("Profile_B")

        # Create linked rule in Profile_A
        shared_code = generate_rule_code()
        doc_a = self.pm.get_profile_config("Profile_A")
        doc_a["rules"] = [
            {
                "id": generate_rule_id(),
                "name": "Rule in A",
                "ruleCode": shared_code,
                "keywords": ["test"],
                "reply": "reply A",
                "matchType": "ultra_exact",
                "contextMatchType": "contains",
                "caseSensitive": False,
                "active": True,
                "isLinked": False,
                "shared": False,
                "sync": {
                    "revision": 1,
                    "updatedAt": "2026-09-20T12:00:00Z",
                    "updatedByProfileId": doc_a["profileId"],
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [doc_a["profileId"]]
                }
            }
        ]
        self.pm.save_profile_config_result("Profile_A", doc_a)

        # Link to Profile_B
        self.pm.link_rule_by_code("Profile_B", shared_code)

        doc_b_disk_before = self.pm.get_profile_config("Profile_B")
        doc_a_disk_before = self.pm.get_profile_config("Profile_A")

        # Simulate external process acquiring Profile_B's OS lease
        pdir_b = self.pm.get_profile_dir("Profile_B")
        external_lease_b = ProfileLease(pdir_b)
        external_lease_b.acquire()

        try:
            # Now attempt to save Profile_A with allowlist changes that must propagate to Profile_B
            doc_a_updated = self.pm.get_profile_config("Profile_A")
            doc_a_updated["rules"][0]["reply"] = "NEW REPLIED FROM A"

            save_res = self.pm.save_profile_config_result("Profile_A", doc_a_updated)

            # Must fail with LINKED_PROFILE_BUSY
            self.assertFalse(save_res.ok)
            self.assertEqual(save_res.code, "LINKED_PROFILE_BUSY")
            self.assertIn("Profile_B", save_res.blockedProfiles)

            # Zero disk changes! Both files on disk must match prior state
            doc_b_disk_after = self.pm.get_profile_config("Profile_B")
            doc_a_disk_after = self.pm.get_profile_config("Profile_A")

            self.assertEqual(doc_b_disk_after["rules"][0]["reply"], doc_b_disk_before["rules"][0]["reply"])
            self.assertEqual(doc_a_disk_after["rules"][0]["reply"], doc_a_disk_before["rules"][0]["reply"])
        finally:
            external_lease_b.release()

    def test_in_process_lease_authority_reuse(self):
        """Worker in current process holding ProfileLease can contribute LeaseAuthority to avoid self-locking failure."""
        self.pm.create_profile("Profile_Worker")
        pdir = self.pm.get_profile_dir("Profile_Worker")
        doc = self.pm.get_profile_config("Profile_Worker")

        # Worker holds lifetime lease
        worker_lease = ProfileLease(pdir)
        worker_lease.acquire()

        try:
            authority = LeaseAuthority("Profile_Worker", pdir, worker_lease)

            doc["rules"] = [
                {
                    "id": generate_rule_id(),
                    "name": "Local Worker Rule",
                    "ruleCode": generate_rule_code(),
                    "keywords": ["مرحبا"],
                    "reply": "أهلا بك",
                    "matchType": "ultra_exact",
                    "contextMatchType": "contains",
                    "caseSensitive": False,
                    "active": True,
                    "isLinked": False,
                    "shared": False,
                    "sync": {
                        "revision": 0,
                        "updatedAt": "2026-09-20T12:00:00Z",
                        "updatedByProfileId": doc["profileId"],
                        "operationId": str(uuid.uuid4()),
                        "memberProfileIds": [doc["profileId"]]
                    }
                }
            ]

            # Save providing lease_authorities
            save_res = self.pm.save_profile_config_result(
                "Profile_Worker",
                doc,
                lease_authorities=[authority]
            )
            self.assertTrue(save_res.ok, f"Save failed with lease authority: {save_res.message}")

            # Verify disk was written
            reloaded = self.pm.get_profile_config("Profile_Worker")
            self.assertEqual(reloaded["rules"][0]["reply"], "أهلا بك")
        finally:
            worker_lease.release()


if __name__ == "__main__":
    unittest.main()
