#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Suite Profile Manager Module (V6.5.0)
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
Provides thread-safe and process-isolated local sandbox management,
immutable rule-code metadata allocation, atomic single-profile persistence,
and synchronous rule import/cloning.
"""

__author__ = "Bishoy Safwat"

import os
import re
import sys
import json
import time
import uuid
import shutil
import secrets
import tempfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Schema & Rule Constants
# ---------------------------------------------------------------------------
CROCKFORD_ALPHABET: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RULE_CODE_REGEX = re.compile(r"^MBS-[0-9A-HJKMNP-TV-Z]{8}$")
RULE_ID_REGEX = re.compile(r"^rule_[0-9a-f]{32}$")
NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\u0600-\u06FF\s-]+$")
VALID_MATCH_TYPES: Set[str] = {"ultra_exact", "contains", "exact", "regex"}

DEFAULT_TEMPLATE_CONFIG: Dict[str, Any] = {
    "rules": [],
    "config": {
        "typingSpeed": 15,
        "minTypingSpeed": 11,
        "maxTypingSpeed": 19,
        "minCooldown": 850,
        "maxCooldown": 1150,
        "scrollThread": True,
        "highlightRows": True,
        "monitoringInterval": 5000,
    },
    "auto_start": False,
}


# ---------------------------------------------------------------------------
# Rule Code Generation & Local Rule Normalization
# ---------------------------------------------------------------------------
def generate_rule_code() -> str:
    """Generate random Crockford Base32 rule code: MBS-[0-9A-HJKMNP-TV-Z]{8}.
    Strictly excludes ambiguous characters I, L, O, and U."""
    code_chars = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(8))
    return f"MBS-{code_chars}"


def allocate_unique_rule_code(existing_codes: Set[str], max_retries: int = 200) -> str:
    """Allocate a unique Crockford Base32 rule code not present in existing_codes.
    Retries upon collision and fails closed if uniqueness cannot be established."""
    for _ in range(max_retries):
        code = generate_rule_code()
        if code not in existing_codes:
            return code
    raise RuntimeError("Failed to allocate a unique ruleCode within profile (collision limit reached).")


def normalize_local_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every local rule has a stable ID, valid Crockford Base32 ruleCode,
    and proper canonical structure.
    - Preserves existing valid ruleCode values without rotating them.
    - Missing, invalid, or duplicate codes receive fresh Crockford Base32 codes.
    - Preserves user-authored literal spaces, commas, and newlines.
    - Does not establish links, revisions, or synchronization metadata."""
    if not isinstance(rules, list):
        return []

    existing_codes: Set[str] = set()
    # Pass 1: Collect valid existing codes
    for r in rules:
        if not isinstance(r, dict):
            continue
        code = r.get("ruleCode")
        if isinstance(code, str) and RULE_CODE_REGEX.match(code):
            if code not in existing_codes:
                existing_codes.add(code)

    # Pass 2: Normalize rules and assign missing/colliding codes
    assigned_codes: Set[str] = set()
    normalized: List[Dict[str, Any]] = []

    for r in rules:
        if not isinstance(r, dict):
            continue
        rule_copy = dict(r)

        # Ensure stable local ID
        rule_id = rule_copy.get("id")
        if not rule_id or not isinstance(rule_id, str):
            rule_copy["id"] = "rule_" + uuid.uuid4().hex

        # Ensure stable ruleCode
        code = rule_copy.get("ruleCode")
        if isinstance(code, str) and RULE_CODE_REGEX.match(code) and code not in assigned_codes:
            assigned_codes.add(code)
        else:
            new_code = allocate_unique_rule_code(existing_codes | assigned_codes)
            assigned_codes.add(new_code)
            rule_copy["ruleCode"] = new_code

        # Ensure matchType defaults to ultra_exact if missing or invalid
        if not rule_copy.get("matchType") or rule_copy.get("matchType") not in VALID_MATCH_TYPES:
            rule_copy["matchType"] = "ultra_exact"

        # Ensure keywords is a list
        if "keywords" not in rule_copy or not isinstance(rule_copy["keywords"], list):
            if isinstance(rule_copy.get("keyword"), str) and rule_copy["keyword"].strip():
                rule_copy["keywords"] = [s.strip() for s in rule_copy["keyword"].split(",") if s.strip()]
            else:
                rule_copy["keywords"] = []

        # Maintain backward-compatible keyword string
        if not rule_copy.get("keyword") and rule_copy["keywords"]:
            rule_copy["keyword"] = ", ".join(rule_copy["keywords"])

        # Default caseSensitive
        if "caseSensitive" not in rule_copy:
            rule_copy["caseSensitive"] = False

        normalized.append(rule_copy)

    return normalized


# ---------------------------------------------------------------------------
# Atomic Persistence
# ---------------------------------------------------------------------------
def atomic_write_json(path: Path, value: Any, max_retries: int = 5, retry_delay: float = 0.05) -> bool:
    """High-durability atomic JSON write with flush, fsync, parent dir fsync,
    and exponential backoff on os.replace."""
    path = Path(path)
    parent_dir = path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Retry loop for Windows / antivirus file-locking contention
        last_err = None
        for attempt in range(max_retries):
            try:
                os.replace(temp_path, path)
                last_err = None
                break
            except (OSError, PermissionError) as e:
                last_err = e
                time.sleep(retry_delay * (2 ** attempt))

        if last_err is not None:
            raise last_err

        # POSIX directory fsync
        if hasattr(os, "O_DIRECTORY") and os.name != "nt":
            try:
                dir_fd = getattr(os, "open")(str(parent_dir), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass

        return True
    finally:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# OS Kernel Profile Lease
# ---------------------------------------------------------------------------
class ProfileLease:
    """Acquires an exclusive OS-level kernel file lock on a profile directory.
    Rejects duplicate execution from concurrent browser workers."""

    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir).resolve()
        self.lock_file_path = self.profile_dir / ".worker.lock"
        self._fd: Optional[int] = None

    def acquire(self) -> None:
        """Acquire exclusive non-blocking lock. Raises RuntimeError if already locked."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = getattr(os, "open")(str(self.lock_file_path), os.O_RDWR | os.O_CREAT, 0o600)
        except Exception as e:
            raise RuntimeError(f"PROFILE_LOCK_OPEN_ERROR: Unable to open lock file: {e}")

        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            except (IOError, OSError):
                os.close(self._fd)
                self._fd = None
                raise RuntimeError(
                    f"PROFILE_ALREADY_RUNNING: Profile at '{self.profile_dir}' is locked by another process."
                )
        else:
            import fcntl
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                os.close(self._fd)
                self._fd = None
                raise RuntimeError(
                    f"PROFILE_ALREADY_RUNNING: Profile at '{self.profile_dir}' is locked by another process."
                )

        try:
            os.ftruncate(self._fd, 0)
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.write(self._fd, f"{os.getpid()}\n".encode("utf-8"))
            os.fsync(self._fd)
        except OSError:
            pass

    def release(self) -> None:
        """Release lock file cleanly. Safe for headless streams (sys.stderr=None)."""
        if self._fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    try:
                        os.lseek(self._fd, 0, os.SEEK_SET)
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except (IOError, OSError) as e:
                        if sys.stderr:
                            sys.stderr.write(f"Warning: msvcrt unlock failed: {e}\n")
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                    except (IOError, OSError) as e:
                        if sys.stderr:
                            sys.stderr.write(f"Warning: flock unlock failed: {e}\n")
            finally:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------------------------------------------------------------------------
# Master ProfileManager Class (Single-Profile, Non-Distributed)
# ---------------------------------------------------------------------------
class ProfileManager:
    """Manages browser profiles, directory isolation, configuration, and local rule storage."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is not None:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = self.resolve_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def resolve_base_dir() -> Path:
        """Resolve OS-appropriate default profiles base directory."""
        if sys.platform.startswith("win"):
            userprofile = os.environ.get("USERPROFILE", str(Path.home()))
            return Path(userprofile) / "MetaInboxBot_Profiles"
        return Path.home() / ".config" / "meta_inbox_bot" / "profiles"

    def validate_name(self, name: str) -> str:
        """Validate and sanitize profile name."""
        if not name or not isinstance(name, str):
            raise ValueError("Profile name must be a non-empty string.")
        stripped = name.strip()
        if not stripped:
            raise ValueError("Profile name cannot be empty or whitespace.")
        if not NAME_REGEX.match(stripped):
            raise ValueError(
                f"Invalid profile name: '{name}'. Allowed: letters, Arabic characters, digits, underscores, hyphens, and spaces."
            )
        return stripped

    def is_valid_name(self, name: str) -> bool:
        """Return True if profile name is valid, False otherwise."""
        try:
            self.validate_name(name)
            return True
        except ValueError:
            return False

    def get_profile_dir(self, name: str) -> Path:
        """Return the absolute path to a profile's directory."""
        safe_name = self.validate_name(name)
        return self.base_dir / safe_name

    def get_profile_config_path(self, name: str) -> Path:
        """Return path to profile's config.json file."""
        return self.get_profile_dir(name) / "config.json"

    def get_profile_config(self, name: str) -> Dict[str, Any]:
        """Load and normalize profile config.json.
        Ensures local rules have valid IDs and immutable Crockford Base32 ruleCodes."""
        cfg_path = self.get_profile_config_path(name)
        if not cfg_path.is_file():
            return dict(DEFAULT_TEMPLATE_CONFIG)

        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return dict(DEFAULT_TEMPLATE_CONFIG)

            # Normalize local rules
            raw_rules = data.get("rules", [])
            data["rules"] = normalize_local_rules(raw_rules)
            return data
        except Exception:
            return dict(DEFAULT_TEMPLATE_CONFIG)

    def save_profile_config(self, name: str, config: Dict[str, Any]) -> bool:
        """Atomically persist configuration for profile.
        Normalizes local rules and validates uniqueness before writing.
        Touches ONLY this profile's configuration file."""
        safe_name = self.validate_name(name)
        pdir = self.get_profile_dir(safe_name)
        pdir.mkdir(parents=True, exist_ok=True)
        cfg_path = self.get_profile_config_path(safe_name)

        doc = dict(config)
        if "rules" in doc:
            doc["rules"] = normalize_local_rules(doc["rules"])

        return atomic_write_json(cfg_path, doc)

    def create_profile(self, name: str) -> Dict[str, Any]:
        """Create a new profile directory and seed clean default configuration with rules: []."""
        safe_name = self.validate_name(name)
        pdir = self.get_profile_dir(safe_name)
        pdir.mkdir(parents=True, exist_ok=True)

        cfg_path = self.get_profile_config_path(safe_name)
        if not cfg_path.is_file():
            initial_config = dict(DEFAULT_TEMPLATE_CONFIG)
            initial_config["rules"] = []
            atomic_write_json(cfg_path, initial_config)

        return {
            "name": safe_name,
            "path": str(pdir),
            "status": "STOPPED",
            "created_at": time.time(),
        }

    def delete_profile(self, name: str) -> bool:
        """Permanently delete a profile directory and all its contents."""
        safe_name = self.validate_name(name)
        pdir = self.get_profile_dir(safe_name)
        if pdir.exists() and pdir.is_dir():
            shutil.rmtree(pdir, ignore_errors=True)
            return not pdir.exists()
        return True

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Rename an existing profile directory."""
        old_safe = self.validate_name(old_name)
        new_safe = self.validate_name(new_name)

        old_dir = self.get_profile_dir(old_safe)
        new_dir = self.get_profile_dir(new_safe)

        if not old_dir.exists():
            raise FileNotFoundError(f"Profile '{old_safe}' does not exist.")
        if new_dir.exists():
            raise FileExistsError(f"Profile '{new_safe}' already exists.")

        old_dir.rename(new_dir)
        return new_dir.exists()

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all valid profiles in the base directory."""
        profiles = []
        if not self.base_dir.exists():
            return profiles

        for item in sorted(self.base_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                if self.is_valid_name(item.name):
                    profiles.append({
                        "name": item.name,
                        "path": str(item),
                        "has_config": (item / "config.json").is_file(),
                    })
        return profiles

    def is_profile_locked(self, name: str) -> bool:
        """Check if a profile has active locks (SingletonLock or .worker.lock)."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return False

        # 1. Chromium lock
        chromium_lock = pdir / "SingletonLock"
        if chromium_lock.exists() or chromium_lock.is_symlink():
            return True

        # 2. Worker OS lease
        worker_lock = pdir / ".worker.lock"
        if worker_lock.exists():
            try:
                lease = ProfileLease(pdir)
                lease.acquire()
                lease.release()
            except RuntimeError:
                return True

        return False

    def clean_stale_locks(self, name: str) -> bool:
        """Clean up stale locks for a profile."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return False

        cleaned = False
        chromium_lock = pdir / "SingletonLock"
        if chromium_lock.exists() or chromium_lock.is_symlink():
            try:
                chromium_lock.unlink(missing_ok=True)
                cleaned = True
            except OSError:
                pass

        worker_lock = pdir / ".worker.lock"
        if worker_lock.exists():
            try:
                worker_lock.unlink(missing_ok=True)
                cleaned = True
            except OSError:
                pass

        return cleaned

    # -------------------------------------------------------------------------
    # Synchronous Rule Import (Clone into Local Profile)
    # -------------------------------------------------------------------------
    def import_rules_from_profile(
        self, target_profile: str, source_profile: str, rule_ids: List[str]
    ) -> Dict[str, Any]:
        """Synchronously import/clone selected rules from a source profile into the target profile.
        - Validates source and destination profile paths.
        - Rejects importing from active profile into itself.
        - Loads source configuration without mutating source file.
        - Generates fresh destination-local IDs and unique Crockford Base32 ruleCodes.
        - Appends clones to destination configuration, preserving selected source order.
        - Preserves user-authored whitespace, commas, and newlines.
        - Does NOT link profiles, add provenance, or establish background sync.
        - Source config.json remains byte-for-byte unchanged.
        - Atomically saves destination configuration once."""
        # 1. Validate names
        try:
            target_safe = self.validate_name(target_profile)
            source_safe = self.validate_name(source_profile)
        except ValueError as e:
            return {"ok": False, "code": "INVALID_PROFILE_NAME", "message": str(e)}

        # 2. Reject self-import
        if target_safe == source_safe:
            return {
                "ok": False,
                "code": "SELF_IMPORT_REJECTED",
                "message": "Cannot import rules from a profile into itself.",
            }

        # 3. Validate source existence
        source_dir = self.get_profile_dir(source_safe)
        source_cfg_path = self.get_profile_config_path(source_safe)
        if not source_dir.is_dir() or not source_cfg_path.is_file():
            return {
                "ok": False,
                "code": "SOURCE_NOT_FOUND",
                "message": f"Source profile '{source_safe}' not found or missing config.json.",
            }

        # 4. Validate target existence
        target_dir = self.get_profile_dir(target_safe)
        target_cfg_path = self.get_profile_config_path(target_safe)
        if not target_dir.is_dir() or not target_cfg_path.is_file():
            return {
                "ok": False,
                "code": "TARGET_NOT_FOUND",
                "message": f"Target profile '{target_safe}' not found or missing config.json.",
            }

        # 5. Read source config without mutating it
        try:
            with open(source_cfg_path, "r", encoding="utf-8") as sf:
                source_doc = json.load(sf)
        except Exception as e:
            return {
                "ok": False,
                "code": "SOURCE_READ_ERROR",
                "message": f"Failed to read source profile config: {e}",
            }

        source_rules = source_doc.get("rules", [])
        if not isinstance(source_rules, list) or not source_rules:
            return {
                "ok": False,
                "code": "SOURCE_EMPTY",
                "message": f"Source profile '{source_safe}' has no rules to import.",
            }

        if not rule_ids or not isinstance(rule_ids, list):
            return {
                "ok": False,
                "code": "NO_RULES_SELECTED",
                "message": "No rule IDs provided for import.",
            }

        # 6. Find selected rules preserving source order
        rule_ids_set = set(str(rid) for rid in rule_ids)
        selected_source_rules = [
            r for r in source_rules
            if isinstance(r, dict) and str(r.get("id")) in rule_ids_set
        ]

        if not selected_source_rules:
            return {
                "ok": False,
                "code": "RULES_NOT_FOUND",
                "message": "None of the specified rule IDs exist in the source profile.",
            }

        # 7. Load target config
        try:
            with open(target_cfg_path, "r", encoding="utf-8") as tf:
                target_doc = json.load(tf)
        except Exception as e:
            return {
                "ok": False,
                "code": "TARGET_READ_ERROR",
                "message": f"Failed to read target profile config: {e}",
            }

        dest_rules = target_doc.get("rules", [])
        if not isinstance(dest_rules, list):
            dest_rules = []

        # Collect existing destination ruleCodes and IDs
        existing_dest_codes: Set[str] = set()
        for dr in dest_rules:
            if isinstance(dr, dict):
                c = dr.get("ruleCode")
                if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                    existing_dest_codes.add(c)

        # 8. Clone selected rules with fresh local IDs and codes
        cloned_rules: List[Dict[str, Any]] = []
        for sr in selected_source_rules:
            fresh_id = "rule_" + uuid.uuid4().hex
            fresh_code = allocate_unique_rule_code(existing_dest_codes)
            existing_dest_codes.add(fresh_code)

            # Deep clone user-authored rule fields
            clone = {
                "id": fresh_id,
                "ruleCode": fresh_code,
                "name": sr.get("name", "قاعدة مستوردة"),
                "active": sr.get("active", True),
                "keywords": list(sr.get("keywords", [])) if isinstance(sr.get("keywords"), list) else [],
                "reply": str(sr.get("reply", "")),
                "matchType": sr.get("matchType", "ultra_exact"),
                "caseSensitive": bool(sr.get("caseSensitive", False)),
            }

            if "keyword" in sr and isinstance(sr["keyword"], str):
                clone["keyword"] = sr["keyword"]
            else:
                clone["keyword"] = ", ".join(clone["keywords"])

            if "contextKeywords" in sr and isinstance(sr["contextKeywords"], list):
                clone["contextKeywords"] = list(sr["contextKeywords"])
            if "contextKeyword" in sr and isinstance(sr["contextKeyword"], str):
                clone["contextKeyword"] = sr["contextKeyword"]
            if "contextMatchType" in sr and isinstance(sr["contextMatchType"], str):
                clone["contextMatchType"] = sr["contextMatchType"]

            cloned_rules.append(clone)

        # Append cloned rules to destination rules
        dest_rules.extend(cloned_rules)
        target_doc["rules"] = dest_rules

        # 9. Atomically save target profile once
        save_ok = self.save_profile_config(target_safe, target_doc)
        if not save_ok:
            return {
                "ok": False,
                "code": "TARGET_SAVE_FAILED",
                "message": f"Failed to atomically persist imported rules to profile '{target_safe}'.",
            }

        return {
            "ok": True,
            "code": "SUCCESS",
            "importedCount": len(cloned_rules),
            "rules": cloned_rules,
        }
