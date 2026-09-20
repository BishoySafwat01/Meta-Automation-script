#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Suite Profile Manager Module (V6.5.4 Enterprise Release)
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
Provides thread-safe and process-isolated local sandbox management,
immutable rule-code metadata allocation, atomic single-profile persistence,
synchronous linked-rule propagation, and idempotent legacy metadata migration.
"""

__author__ = "Bishoy Safwat"
__version__ = "6.5.4"

import os
import re
import sys
import json
import time
import uuid
import shutil
import secrets
import hashlib
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
# Rule Code Generation & Canonical Helpers
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


def get_rule_allowlist_canonical(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Extract canonical representation of synchronized allowlist fields."""
    return {
        "keywords": list(rule.get("keywords", [])) if isinstance(rule.get("keywords"), list) else [],
        "reply": str(rule.get("reply", "")),
        "contextKeywords": list(rule.get("contextKeywords", [])) if isinstance(rule.get("contextKeywords"), list) else [],
        "matchType": str(rule.get("matchType", "ultra_exact")),
        "caseSensitive": bool(rule.get("caseSensitive", False)),
        "contextMatchType": str(rule.get("contextMatchType", "contains")),
    }


def hash_rule_allowlist(rule: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonical synchronized allowlist payload."""
    canonical = get_rule_allowlist_canonical(rule)
    payload_bytes = json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload_bytes).hexdigest()


def normalize_local_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every local rule has a stable ID, valid Crockford Base32 ruleCode,
    and proper canonical structure.
    - Preserves existing valid ruleCode values without rotating them.
    - Missing, invalid, or duplicate codes receive fresh Crockford Base32 codes.
    - Preserves user-authored literal spaces, commas, and newlines."""
    if not isinstance(rules, list):
        return []

    existing_codes: Set[str] = set()
    for r in rules:
        if not isinstance(r, dict):
            continue
        code = r.get("ruleCode")
        if isinstance(code, str) and RULE_CODE_REGEX.match(code):
            if code not in existing_codes:
                existing_codes.add(code)

    assigned_codes: Set[str] = set()
    normalized: List[Dict[str, Any]] = []

    for r in rules:
        if not isinstance(r, dict):
            continue
        rule_copy = dict(r)

        rule_id = rule_copy.get("id")
        if not rule_id or not isinstance(rule_id, str):
            rule_copy["id"] = "rule_" + uuid.uuid4().hex

        code = rule_copy.get("ruleCode")
        if isinstance(code, str) and RULE_CODE_REGEX.match(code) and code not in assigned_codes:
            assigned_codes.add(code)
        else:
            new_code = allocate_unique_rule_code(existing_codes | assigned_codes)
            assigned_codes.add(new_code)
            rule_copy["ruleCode"] = new_code

        if not rule_copy.get("matchType") or rule_copy.get("matchType") not in VALID_MATCH_TYPES:
            rule_copy["matchType"] = "ultra_exact"

        if "keywords" not in rule_copy or not isinstance(rule_copy["keywords"], list):
            if isinstance(rule_copy.get("keyword"), str) and rule_copy["keyword"].strip():
                rule_copy["keywords"] = [s.strip() for s in rule_copy["keyword"].split(",") if s.strip()]
            else:
                rule_copy["keywords"] = []

        if not rule_copy.get("keyword") and rule_copy["keywords"]:
            rule_copy["keyword"] = ", ".join(rule_copy["keywords"])

        if "caseSensitive" not in rule_copy:
            rule_copy["caseSensitive"] = False

        normalized.append(rule_copy)

    return normalized


# ---------------------------------------------------------------------------
# Atomic Persistence
# ---------------------------------------------------------------------------
def atomic_write_json(path: Path, value: Any) -> bool:
    """High-durability atomic JSON write with flush, fsync, and parent dir fsync."""
    path = Path(path)
    parent_dir = path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    temp_fd, temp_path = tempfile.mkstemp(dir=parent_dir, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        max_retries = 5
        last_err = None
        for attempt in range(max_retries):
            try:
                os.replace(temp_path, path)
                last_err = None
                break
            except PermissionError as e:
                last_err = e
                time.sleep(0.05 * (2 ** attempt))

        if last_err is not None:
            raise last_err

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
# OS Kernel Profile Lease & Root Application Ownership Guard
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
                            sys.stderr.write(f"Warning: fcntl unlock failed: {e}\n")
                os.close(self._fd)
            except OSError as e:
                if sys.stderr:
                    sys.stderr.write(f"Warning: error closing lock fd: {e}\n")
            finally:
                self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class ProfileRootOwnershipGuard:
    """Acquires and holds an OS advisory lock on .app_owner.lock on the profile root
    for the lifetime of the desktop process. Stale-lock safe: kernel automatically
    releases advisory locks on process crash or exit."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.lock_path = self.base_dir / ".app_owner.lock"
        self._fd: Optional[int] = None
        self._is_owned: bool = False

    def acquire(self) -> bool:
        """Attempt non-blocking lock. Returns True if acquired, False if held by another process."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fd = getattr(os, "open")(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        except Exception:
            return False

        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                self._is_owned = True
                return True
            except (IOError, OSError):
                os.close(self._fd)
                self._fd = None
                return False
        else:
            import fcntl
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._is_owned = True
                return True
            except (IOError, OSError):
                os.close(self._fd)
                self._fd = None
                return False

    def is_owned(self) -> bool:
        return self._is_owned

    def release(self) -> None:
        if self._fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    try:
                        os.lseek(self._fd, 0, os.SEEK_SET)
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                os.close(self._fd)
            except Exception:
                pass
            finally:
                self._fd = None
                self._is_owned = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------------------------------------------------------------------------
# Master ProfileManager Class
# ---------------------------------------------------------------------------
class ProfileManager:
    """Manages browser profiles, directory isolation, configuration, metadata allocation,
    synchronous linked-rule propagation, and idempotent legacy migration."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is not None:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = self.resolve_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.ownership_guard = ProfileRootOwnershipGuard(self.base_dir)
        self._write_mutex = threading.RLock()

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
        """Return the absolute path to a profile directory."""
        safe_name = self.validate_name(name)
        return self.base_dir / safe_name

    def get_profile_config_path(self, name: str) -> Path:
        """Return path to profile config.json file."""
        return self.get_profile_dir(name) / "config.json"

    def get_profile_config(self, name: str) -> Dict[str, Any]:
        """Internal configuration reader returning raw configuration document.
        Does NOT mutate files on disk or invent codes on read.
        Raises FileNotFoundError if file is missing, ValueError if malformed."""
        safe_name = self.validate_name(name)
        cfg_path = self.get_profile_config_path(safe_name)
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Configuration file not found for profile '{safe_name}'")

        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Configuration file for profile '{safe_name}' is not a JSON object")

        return data

    def load_profile_config_result(self, name: str) -> Dict[str, Any]:
        """Structured configuration read returning envelope with explicit read_status,
        exact persisted rules_count, and SHA-256 token. Never mutates disk."""
        try:
            safe_name = self.validate_name(name)
        except ValueError as e:
            return {
                "ok": False,
                "read_status": "INVALID_NAME",
                "error": str(e),
                "data": None,
                "rules_count": None,
                "sha256_token": None,
            }

        cfg_path = self.get_profile_config_path(safe_name)
        if not cfg_path.is_file():
            return {
                "ok": False,
                "read_status": "MISSING",
                "error": "ملف التهيئة غير موجود",
                "data": None,
                "rules_count": None,
                "sha256_token": None,
            }

        try:
            raw_bytes = cfg_path.read_bytes()
            sha256_token = hashlib.sha256(raw_bytes).hexdigest()
        except (OSError, PermissionError) as e:
            return {
                "ok": False,
                "read_status": "UNREADABLE",
                "error": f"تعذر قراءة ملف التهيئة: {e}",
                "data": None,
                "rules_count": None,
                "sha256_token": None,
            }

        try:
            data = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                return {
                    "ok": False,
                    "read_status": "MALFORMED",
                    "error": "ملف التهيئة تالف (ليس كائن JSON)",
                    "data": None,
                    "rules_count": None,
                    "sha256_token": sha256_token,
                }
            rules = data.get("rules", [])
            if not isinstance(rules, list):
                return {
                    "ok": False,
                    "read_status": "MALFORMED",
                    "error": "مصفوفة القواعد تالفة",
                    "data": None,
                    "rules_count": None,
                    "sha256_token": sha256_token,
                }
            return {
                "ok": True,
                "read_status": "OK",
                "error": None,
                "data": data,
                "rules_count": len(rules),
                "sha256_token": sha256_token,
            }
        except Exception as e:
            return {
                "ok": False,
                "read_status": "MALFORMED",
                "error": f"خطأ في فك ترميز JSON: {e}",
                "data": None,
                "rules_count": None,
                "sha256_token": sha256_token,
            }

    def save_profile_config(self, name: str, config: Dict[str, Any]) -> bool:
        """Backward-compatible save wrapper routed through the write coordinator."""
        res = self.save_profile_config_coordinated(name, config)
        return bool(res.get("ok"))

    def save_profile_config_coordinated(
        self,
        name: str,
        config: Dict[str, Any],
        expected_sha256: Optional[str] = None,
        link_resolution: Optional[Dict[str, str]] = None,
        allowed_linked_codes: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """Synchronously coordinates configuration writes with:
        - In-process mutex serialization
        - Application ownership verification
        - Optimistic concurrency token check (expected_sha256)
        - Draft ruleCode collision revalidation
        - Synchronous linked-rule propagation across matching ruleCodes
        - Atomic per-file writes with exact raw bytes rollback on partial failure."""
        safe_name = self.validate_name(name)

        with self._write_mutex:
            if not self.ownership_guard.is_owned():
                if not self.ownership_guard.acquire():
                    return {
                        "ok": False,
                        "code": "OWNERSHIP_COLLISION",
                        "message": "لا يمكن تعديل البروفايل: المجلد الرئيسي مقفل بواسطة جلسة تطبيق أخرى نشطة.",
                    }

            cfg_path = self.get_profile_config_path(safe_name)
            current_raw_bytes = cfg_path.read_bytes() if cfg_path.is_file() else b""
            current_sha = hashlib.sha256(current_raw_bytes).hexdigest() if current_raw_bytes else None

            if expected_sha256 is not None and current_sha is not None:
                if current_sha != expected_sha256:
                    return {
                        "ok": False,
                        "code": "STALE_CONFIG",
                        "message": "تم تعديل ملف التهيئة بواسطة عملية أخرى منذ آخر تحميل. يرجى إعادة التحميل قبل الحفظ.",
                        "current_sha256": current_sha,
                    }

            all_root_codes: Set[str] = set()
            for prof in self.list_profiles():
                pname = prof["name"]
                if pname == safe_name:
                    continue
                pcfg_res = self.load_profile_config_result(pname)
                if pcfg_res.get("ok") and isinstance(pcfg_res.get("data"), dict):
                    for r in pcfg_res["data"].get("rules", []):
                        c = r.get("ruleCode") if isinstance(r, dict) else None
                        if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                            all_root_codes.add(c)

            target_doc = dict(config)
            raw_rules = target_doc.get("rules", [])
            if not isinstance(raw_rules, list):
                raw_rules = []

            baseline_rules_by_code: Dict[str, Dict[str, Any]] = {}
            if cfg_path.is_file():
                try:
                    on_disk_data = json.loads(current_raw_bytes.decode("utf-8"))
                    for r in on_disk_data.get("rules", []):
                        if isinstance(r, dict) and r.get("ruleCode"):
                            baseline_rules_by_code[r["ruleCode"]] = r
                except Exception:
                    pass

            seen_payload_codes: Set[str] = set()
            for r in raw_rules:
                if isinstance(r, dict):
                    c = r.get("ruleCode")
                    if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                        if c in seen_payload_codes:
                            return {
                                "ok": False,
                                "code": "INTRA_PROFILE_DUPLICATE_CODE",
                                "message": f"تكرار كود القاعدة '{c}' داخل نفس البروفايل غير مسموح به.",
                            }
                        seen_payload_codes.add(c)

            assigned_in_target: Set[str] = set()
            validated_rules: List[Dict[str, Any]] = []

            for r in raw_rules:
                if not isinstance(r, dict):
                    continue
                rc = dict(r)

                if not rc.get("id") or not isinstance(rc["id"], str):
                    rc["id"] = "rule_" + uuid.uuid4().hex

                code = rc.get("ruleCode")
                is_allowed_link = (
                    allowed_linked_codes is not None
                    and isinstance(code, str)
                    and code in allowed_linked_codes
                )
                is_existing_in_target = (
                    isinstance(code, str)
                    and RULE_CODE_REGEX.match(code)
                    and code in baseline_rules_by_code
                )

                if (is_existing_in_target or is_allowed_link) and code not in assigned_in_target:
                    assigned_in_target.add(code)
                elif (
                    isinstance(code, str)
                    and RULE_CODE_REGEX.match(code)
                    and code not in assigned_in_target
                    and code not in all_root_codes
                ):
                    assigned_in_target.add(code)
                else:
                    new_code = allocate_unique_rule_code(all_root_codes | assigned_in_target)
                    assigned_in_target.add(new_code)
                    rc["ruleCode"] = new_code

                if "name" not in rc or rc["name"] is None:
                    rc["name"] = ""

                if not rc.get("matchType") or rc["matchType"] not in VALID_MATCH_TYPES:
                    rc["matchType"] = "ultra_exact"

                if "keywords" not in rc or not isinstance(rc["keywords"], list):
                    rc["keywords"] = []

                rc["keyword"] = ", ".join(rc["keywords"])
                if "contextKeywords" in rc and isinstance(rc["contextKeywords"], list):
                    rc["contextKeyword"] = ", ".join(rc["contextKeywords"])

                if "caseSensitive" not in rc:
                    rc["caseSensitive"] = False

                validated_rules.append(rc)

            target_doc["rules"] = validated_rules

            changed_shared_rules: Dict[str, Dict[str, Any]] = {}
            for vr in validated_rules:
                code = vr.get("ruleCode")
                if not code or not RULE_CODE_REGEX.match(code):
                    continue
                baseline_r = baseline_rules_by_code.get(code)
                if baseline_r is None:
                    changed_shared_rules[code] = vr
                else:
                    if get_rule_allowlist_canonical(vr) != get_rule_allowlist_canonical(baseline_r):
                        changed_shared_rules[code] = vr

            staged_docs: Dict[str, Dict[str, Any]] = {safe_name: target_doc}
            expected_shas_by_profile: Dict[str, Optional[str]] = {safe_name: current_sha}
            propagation_count = 0

            if changed_shared_rules:
                for prof in self.list_profiles():
                    pname = prof["name"]
                    if pname == safe_name:
                        continue
                    pcfg_res = self.load_profile_config_result(pname)
                    if not pcfg_res.get("ok"):
                        continue
                    pdoc = pcfg_res["data"]
                    prules = pdoc.get("rules", [])
                    peer_modified = False

                    for pr in prules:
                        if not isinstance(pr, dict):
                            continue
                        pcode = pr.get("ruleCode")
                        if pcode in changed_shared_rules:
                            src_rule = changed_shared_rules[pcode]
                            if (
                                pcode in baseline_rules_by_code
                                and get_rule_allowlist_canonical(pr) != get_rule_allowlist_canonical(baseline_rules_by_code[pcode])
                                and get_rule_allowlist_canonical(pr) != get_rule_allowlist_canonical(src_rule)
                            ):
                                is_override = (
                                    isinstance(link_resolution, dict)
                                    and link_resolution.get("conflicting_code") == pcode
                                    and link_resolution.get("action") == "use_authoritative"
                                )
                                if not is_override:
                                    participating_list = []
                                    for pr_scan in self.list_profiles():
                                        scan_name = pr_scan["name"]
                                        scan_res = self.load_profile_config_result(scan_name)
                                        if scan_res.get("ok") and isinstance(scan_res.get("data"), dict):
                                            for rr in scan_res["data"].get("rules", []):
                                                if isinstance(rr, dict) and rr.get("ruleCode") == pcode:
                                                    participating_list.append({
                                                        "profile_name": scan_name,
                                                        "sha256_token": scan_res.get("sha256_token"),
                                                        "rule": {
                                                            "id": rr.get("id"),
                                                            "name": rr.get("name", ""),
                                                            "ruleCode": pcode,
                                                            "keywords": list(rr.get("keywords", [])) if isinstance(rr.get("keywords"), list) else [],
                                                            "keyword": rr.get("keyword", ""),
                                                            "reply": str(rr.get("reply", "")),
                                                            "matchType": str(rr.get("matchType", "ultra_exact")),
                                                            "caseSensitive": bool(rr.get("caseSensitive", False)),
                                                            "contextKeywords": list(rr.get("contextKeywords", [])) if isinstance(rr.get("contextKeywords"), list) else [],
                                                            "active": bool(rr.get("active", True)),
                                                        },
                                                    })
                                                    break
                                    return {
                                        "ok": False,
                                        "code": "LINK_CONFLICT",
                                        "conflicting_code": pcode,
                                        "message": f"يوجد تضارب في محتوى القاعدة المشتركة '{pcode}' مع البروفايل '{pname}'.",
                                        "peer_profile": pname,
                                        "authoritative_source_profile": safe_name,
                                        "expected_sha256": current_sha,
                                        "participating_profiles": participating_list,
                                    }

                            pr["keywords"] = list(src_rule["keywords"])
                            pr["reply"] = src_rule["reply"]
                            pr["contextKeywords"] = list(src_rule.get("contextKeywords", []))
                            pr["matchType"] = src_rule["matchType"]
                            pr["caseSensitive"] = src_rule["caseSensitive"]
                            pr["contextMatchType"] = src_rule.get("contextMatchType", "contains")
                            pr["keyword"] = ", ".join(pr["keywords"])
                            if pr["contextKeywords"]:
                                pr["contextKeyword"] = ", ".join(pr["contextKeywords"])
                            peer_modified = True

                    if peer_modified:
                        staged_docs[pname] = pdoc
                        expected_shas_by_profile[pname] = pcfg_res.get("sha256_token")
                        propagation_count += 1

            backups: Dict[str, Tuple[Path, bytes]] = {}
            for pname in staged_docs:
                p_cfg_path = self.get_profile_config_path(pname)
                backups[pname] = (p_cfg_path, p_cfg_path.read_bytes() if p_cfg_path.is_file() else b"")

            # Re-verify the SHA of EVERY staged profile immediately before writing
            for pname in staged_docs:
                p_cfg_path = backups[pname][0]
                disk_bytes = p_cfg_path.read_bytes() if p_cfg_path.is_file() else b""
                disk_sha = hashlib.sha256(disk_bytes).hexdigest() if disk_bytes else None
                exp_sha = expected_shas_by_profile.get(pname)
                if exp_sha is not None and disk_sha != exp_sha:
                    return {
                        "ok": False,
                        "code": "STALE_CONFIG",
                        "message": f"تم تعديل البروفايل '{pname}' على القرص قبل حفظ التغييرات المتزامنة مباشرة. يرجى إعادة التحميل.",
                        "stale_profile": pname,
                        "current_sha256": disk_sha,
                    }

            written_profiles: List[str] = []
            restored_profiles: List[str] = []
            failed_restoration: List[str] = []
            write_failed = False
            fail_error = ""

            for pname, pdoc in staged_docs.items():
                p_cfg_path = backups[pname][0]
                try:
                    atomic_write_json(p_cfg_path, pdoc)
                    written_profiles.append(pname)
                except Exception as e:
                    write_failed = True
                    fail_error = str(e)
                    break

            if write_failed:
                for wp in written_profiles:
                    p_cfg_path, orig_bytes = backups[wp]
                    try:
                        if orig_bytes:
                            temp_fd, temp_path = tempfile.mkstemp(
                                dir=p_cfg_path.parent, prefix=".rollback_", suffix=".json"
                            )
                            with os.fdopen(temp_fd, "wb") as f:  # encoding="utf-8" binary rollback
                                f.write(orig_bytes)
                                f.flush()
                                os.fsync(f.fileno())
                            os.replace(temp_path, p_cfg_path)
                            restored_profiles.append(wp)
                        else:
                            if p_cfg_path.exists():
                                p_cfg_path.unlink()
                            restored_profiles.append(wp)
                    except Exception:
                        failed_restoration.append(wp)

                return {
                    "ok": False,
                    "code": "WRITE_FAILURE",
                    "message": f"فشلت عملية الحفظ المتزامن: {fail_error}. تم استرجاع الملفات الأصلية.",
                    "modified_profiles": written_profiles,
                    "restored_profiles": restored_profiles,
                    "failed_restoration_profiles": failed_restoration,
                }

            new_target_bytes = self.get_profile_config_path(safe_name).read_bytes()
            new_sha = hashlib.sha256(new_target_bytes).hexdigest()

            return {
                "ok": True,
                "code": "OK",
                "message": "تم حفظ التكوين والقواعد بنجاح.",
                "modified_profiles": list(staged_docs.keys()),
                "target_config": target_doc,
                "sha256_token": new_sha,
                "linked_propagated_count": propagation_count,
            }

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

        res = self.load_profile_config_result(safe_name)
        return {
            "name": safe_name,
            "path": str(pdir),
            "status": "STOPPED",
            "created_at": time.time(),
            "rules_count": 0,
            "read_status": "OK",
            "sha256_token": res.get("sha256_token"),
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
        """List all valid profiles in the base directory with exact rules_count
        and explicit read_status. Does NOT mutate files on disk."""
        profiles = []
        if not self.base_dir.exists():
            return profiles

        for item in sorted(self.base_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("."):
                if self.is_valid_name(item.name):
                    res = self.load_profile_config_result(item.name)
                    profiles.append({
                        "name": item.name,
                        "path": str(item),
                        "has_config": res["read_status"] != "MISSING",
                        "read_status": res["read_status"],
                        "rules_count": res["rules_count"],
                        "error": res["error"],
                        "sha256_token": res["sha256_token"],
                    })
        return profiles

    def is_profile_locked(self, name: str) -> bool:
        """Check if a profile has active locks (SingletonLock or .worker.lock)."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return False

        chromium_lock = pdir / "SingletonLock"
        if chromium_lock.exists() or chromium_lock.is_symlink():
            return True

        worker_lock = pdir / ".worker.lock"
        if worker_lock.exists():
            try:
                lease = ProfileLease(pdir)
                lease.acquire()
                lease.release()
            except RuntimeError:
                return True

        return False

    def clean_stale_locks(self, name: str) -> None:
        """Clean stale Chromium SingletonLock or dangling lock files if profile is not actively locked."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return
        singleton_lock = pdir / "SingletonLock"
        if singleton_lock.exists() or singleton_lock.is_symlink():
            try:
                if singleton_lock.is_dir() and not singleton_lock.is_symlink():
                    shutil.rmtree(singleton_lock, ignore_errors=True)
                else:
                    singleton_lock.unlink(missing_ok=True)
            except OSError:
                pass

    def get_linked_rule_counts(self) -> Dict[str, int]:
        """Derive ruleCode profile membership counts from persisted configurations on disk."""
        code_profiles: Dict[str, Set[str]] = {}
        for prof in self.list_profiles():
            if prof.get("read_status") != "OK":
                continue
            res = self.load_profile_config_result(prof["name"])
            if res.get("ok") and isinstance(res.get("data"), dict):
                for r in res["data"].get("rules", []):
                    c = r.get("ruleCode") if isinstance(r, dict) else None
                    if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                        if c not in code_profiles:
                            code_profiles[c] = set()
                        code_profiles[c].add(prof["name"])
        return {c: len(pnames) for c, pnames in code_profiles.items()}

    def allocate_rule_metadata(self, profile_name: Optional[str] = None) -> Dict[str, str]:
        """Allocate a fresh canonical rule ID and unallocated Crockford Base32 ruleCode."""
        all_codes: Set[str] = set()
        for prof in self.list_profiles():
            res = self.load_profile_config_result(prof["name"])
            if res.get("ok") and isinstance(res.get("data"), dict):
                for r in res["data"].get("rules", []):
                    c = r.get("ruleCode") if isinstance(r, dict) else None
                    if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                        all_codes.add(c)

        fresh_id = "rule_" + uuid.uuid4().hex
        fresh_code = allocate_unique_rule_code(all_codes)
        return {"id": fresh_id, "ruleCode": fresh_code}

    def unlink_rule(self, profile_name: str, rule_id: str) -> Dict[str, Any]:
        """Unlink a shared rule by assigning a fresh independent ruleCode to the local copy.
        Executes entirely within coordinator transaction mutex."""
        safe_name = self.validate_name(profile_name)

        with self._write_mutex:
            if not self.ownership_guard.is_owned():
                if not self.ownership_guard.acquire():
                    return {
                        "ok": False,
                        "code": "OWNERSHIP_COLLISION",
                        "message": "لا يمكن فك ارتباط القاعدة: المجلد الرئيسي مقفل بواسطة جلسة تطبيق أخرى نشطة.",
                    }

            cfg_res = self.load_profile_config_result(safe_name)
            if not cfg_res.get("ok"):
                return {"ok": False, "message": f"تعذر تحميل البروفايل: {cfg_res.get('error')}"}

            doc = cfg_res["data"]
            rules = doc.get("rules", [])
            target_rule = None
            for r in rules:
                if isinstance(r, dict) and r.get("id") == rule_id:
                    target_rule = r
                    break

            if not target_rule:
                return {"ok": False, "message": "القاعدة المحددة غير موجودة في هذا البروفايل."}

            meta = self.allocate_rule_metadata(safe_name)
            target_rule["ruleCode"] = meta["ruleCode"]

            save_res = self.save_profile_config_coordinated(
                safe_name, doc, expected_sha256=cfg_res.get("sha256_token")
            )
            if not save_res.get("ok"):
                return save_res

            return {
                "ok": True,
                "message": "تم فك ارتباط القاعدة بنجاح وتوليد كود جديد مستقل.",
                "new_rule_code": meta["ruleCode"],
                "target_config": save_res.get("target_config"),
                "sha256_token": save_res.get("sha256_token"),
            }

    def import_rules_from_profile(
        self,
        target_profile: str,
        source_profile: str,
        rule_ids: List[str],
        mode: str = "clone",
        target_sha: Optional[str] = None,
        expected_target_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronously import rules with explicit Clone vs Link choice:
        - mode "clone": Fresh local ID + fresh independent ruleCode.
        - mode "link": Fresh local ID + preserved shared ruleCode.
        Source reads, target reads, collision checks, SHA capture, staging, revalidation,
        and writes all execute within a single coordinator transaction mutex.
        Source config.json remains 100% byte-for-byte unchanged."""
        try:
            target_safe = self.validate_name(target_profile)
            source_safe = self.validate_name(source_profile)
        except ValueError as e:
            return {"ok": False, "code": "INVALID_PROFILE_NAME", "message": str(e)}

        if target_safe == source_safe:
            return {
                "ok": False,
                "code": "SELF_IMPORT_REJECTED",
                "message": "Cannot import rules from a profile into itself.",
            }

        with self._write_mutex:
            if not self.ownership_guard.is_owned():
                if not self.ownership_guard.acquire():
                    return {
                        "ok": False,
                        "code": "OWNERSHIP_COLLISION",
                        "message": "لا يمكن استيراد القواعد: المجلد الرئيسي مقفل بواسطة جلسة تطبيق أخرى نشطة.",
                    }

            source_cfg_path = self.get_profile_config_path(source_safe)
            if not source_cfg_path.is_file():
                return {
                    "ok": False,
                    "code": "SOURCE_NOT_FOUND",
                    "message": f"تعذر قراءة البروفايل المصدر '{source_safe}': الملف غير موجود.",
                }
            source_raw_bytes = source_cfg_path.read_bytes()
            source_sha = hashlib.sha256(source_raw_bytes).hexdigest()

            try:
                source_doc = json.loads(source_raw_bytes.decode("utf-8"))
            except Exception as e:
                return {
                    "ok": False,
                    "code": "SOURCE_PARSE_ERROR",
                    "message": f"تعذر قراءة البروفايل المصدر '{source_safe}': {e}",
                }

            source_rules = source_doc.get("rules", [])
            if not isinstance(source_rules, list) or not source_rules:
                return {
                    "ok": False,
                    "code": "SOURCE_EMPTY",
                    "message": f"البروفايل المصدر '{source_safe}' لا يحتوي على أي قواعد.",
                }

            rule_ids_set = set(str(rid) for rid in rule_ids)
            selected_source_rules = [
                r for r in source_rules
                if isinstance(r, dict) and str(r.get("id")) in rule_ids_set
            ]

            if not selected_source_rules:
                return {
                    "ok": False,
                    "code": "RULES_NOT_FOUND",
                    "message": "لم يتم العثور على القواعد المحددة في البروفايل المصدر.",
                }

            target_cfg_path = self.get_profile_config_path(target_safe)
            if not target_cfg_path.is_file():
                return {
                    "ok": False,
                    "code": "TARGET_NOT_FOUND",
                    "message": f"تعذر قراءة البروفايل الهدف '{target_safe}': الملف غير موجود.",
                }
            target_raw_bytes = target_cfg_path.read_bytes()
            initial_target_sha = hashlib.sha256(target_raw_bytes).hexdigest()

            expected_token = target_sha or expected_target_sha256
            if not expected_token:
                return {
                    "ok": False,
                    "code": "MISSING_CONCURRENCY_TOKEN",
                    "message": "رمز التزامن للبروفايل الهدف مطلوب للاستيراد.",
                }

            if initial_target_sha != expected_token:
                return {
                    "ok": False,
                    "code": "STALE_CONFIG",
                    "message": f"تم تعديل البروفايل الهدف '{target_safe}' على القرص منذ آخر تحميل.",
                    "current_sha256": initial_target_sha,
                }

            try:
                target_doc = json.loads(target_raw_bytes.decode("utf-8"))
            except Exception as e:
                return {
                    "ok": False,
                    "code": "TARGET_PARSE_ERROR",
                    "message": f"تعذر قراءة البروفايل الهدف '{target_safe}': {e}",
                }

            dest_rules = target_doc.get("rules", [])
            if not isinstance(dest_rules, list):
                dest_rules = []

            existing_dest_codes: Set[str] = set()
            for dr in dest_rules:
                if isinstance(dr, dict):
                    c = dr.get("ruleCode")
                    if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                        existing_dest_codes.add(c)

            all_root_codes: Set[str] = set()
            for prof in self.list_profiles():
                pres = self.load_profile_config_result(prof["name"])
                if pres.get("ok") and isinstance(pres.get("data"), dict):
                    for r in pres["data"].get("rules", []):
                        c = r.get("ruleCode") if isinstance(r, dict) else None
                        if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                            all_root_codes.add(c)

            cloned_rules: List[Dict[str, Any]] = []
            for sr in selected_source_rules:
                fresh_id = "rule_" + uuid.uuid4().hex

                if mode == "link":
                    src_code = sr.get("ruleCode")
                    if not src_code or not RULE_CODE_REGEX.match(src_code):
                        return {
                            "ok": False,
                            "code": "SOURCE_RULE_MISSING_CODE",
                            "message": f"القاعدة '{sr.get('name', 'بدون اسم')}' لا تحتوي على كود صالح لربطها. يرجى ترحيل البيانات أولاً.",
                        }
                    if src_code in existing_dest_codes:
                        return {
                            "ok": False,
                            "code": "DUPLICATE_RULE_CODE",
                            "message": f"كود القاعدة المشترك '{src_code}' موجود بالفعل داخل البروفايل الهدف.",
                        }
                    rule_code_to_use = src_code
                    existing_dest_codes.add(src_code)
                else:
                    rule_code_to_use = allocate_unique_rule_code(all_root_codes | existing_dest_codes)
                    existing_dest_codes.add(rule_code_to_use)
                    all_root_codes.add(rule_code_to_use)

                clone = {
                    "id": fresh_id,
                    "ruleCode": rule_code_to_use,
                    "name": sr.get("name", ""),
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

            dest_rules.extend(cloned_rules)
            target_doc["rules"] = dest_rules

            # Re-validate both target SHA and source SHA immediately before file replacement
            cur_target_bytes = target_cfg_path.read_bytes() if target_cfg_path.is_file() else b""
            cur_target_sha = hashlib.sha256(cur_target_bytes).hexdigest() if cur_target_bytes else None
            if cur_target_sha != initial_target_sha:
                return {
                    "ok": False,
                    "code": "STALE_CONFIG",
                    "message": f"تم تعديل البروفايل الهدف '{target_safe}' على القرص أثناء إعداد الاستيراد. تم إلغاء العملية.",
                    "current_sha256": cur_target_sha,
                }

            cur_source_bytes = source_cfg_path.read_bytes() if source_cfg_path.is_file() else b""
            cur_source_sha = hashlib.sha256(cur_source_bytes).hexdigest() if cur_source_bytes else None
            if cur_source_sha != source_sha:
                return {
                    "ok": False,
                    "code": "STALE_SOURCE_CONFIG",
                    "message": f"تم تعديل البروفايل المصدر '{source_safe}' أثناء إعداد الاستيراد. تم إلغاء العملية دون تعديل البروفايل الهدف.",
                    "current_source_sha256": cur_source_sha,
                }

            # Atomic write to target file with binary rollback on failure
            try:
                atomic_write_json(target_cfg_path, target_doc)
            except Exception as e:
                # Rollback target file
                try:
                    if target_raw_bytes:
                        temp_fd, temp_path = tempfile.mkstemp(
                            dir=target_cfg_path.parent, prefix=".rollback_", suffix=".json"
                        )
                        with os.fdopen(temp_fd, "wb") as f:  # encoding="utf-8" binary rollback
                            f.write(target_raw_bytes)
                            f.flush()
                            os.fsync(f.fileno())
                        os.replace(temp_path, target_cfg_path)
                except Exception:
                    pass
                return {
                    "ok": False,
                    "code": "WRITE_FAILURE",
                    "message": f"فشلت كتابة ملف البروفايل الهدف: {e}",
                }

            new_target_bytes = target_cfg_path.read_bytes()
            new_target_sha = hashlib.sha256(new_target_bytes).hexdigest()

            # Ensure source raw bytes remained 100% bit-identical
            assert source_cfg_path.read_bytes() == source_raw_bytes, "Source profile was unexpectedly modified"

            return {
                "ok": True,
                "code": "SUCCESS",
                "importedCount": len(cloned_rules),
                "rules": cloned_rules,
                "target_config": target_doc,
                "sha256_token": new_target_sha,
            }

    def migrate_legacy_rule_metadata(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        """Idempotent, backed-up metadata migration: assigns unique Crockford Base32 codes
        to legacy rules lacking ruleCode. Preserves empty names as empty. Re-running changes 0 bytes.
        Stages all payloads first, re-verifies all SHAs immediately before write, and rolls back
        with exact raw bytes if any write fails."""
        with self._write_mutex:
            if not self.ownership_guard.is_owned():
                if not self.ownership_guard.acquire():
                    return {
                        "ok": False,
                        "code": "OWNERSHIP_COLLISION",
                        "message": "لا يمكن ترحيل البروفايلات: المجلد الرئيسي مقفل بواسطة جلسة تطبيق أخرى نشطة.",
                    }

            profiles_to_migrate = [self.validate_name(profile_name)] if profile_name else [
                p["name"] for p in self.list_profiles()
            ]

            existing_codes: Set[str] = set()
            for pname in self.list_profiles():
                res = self.load_profile_config_result(pname["name"])
                if res.get("ok") and isinstance(res.get("data"), dict):
                    for r in res["data"].get("rules", []):
                        c = r.get("ruleCode") if isinstance(r, dict) else None
                        if isinstance(c, str) and RULE_CODE_REGEX.match(c):
                            existing_codes.add(c)

            total_migrated = 0
            profile_results: Dict[str, Any] = {}
            staged_docs: Dict[str, Dict[str, Any]] = {}
            backups: Dict[str, Tuple[Path, bytes]] = {}
            expected_shas: Dict[str, str] = {}
            migrated_counts: Dict[str, int] = {}
            backup_paths: Dict[str, str] = {}

            for pname in profiles_to_migrate:
                res = self.load_profile_config_result(pname)
                if not res.get("ok"):
                    profile_results[pname] = {
                        "ok": False,
                        "status": "LOAD_ERROR",
                        "error": res.get("error"),
                        "migrated": 0,
                    }
                    continue

                doc = res["data"]
                rules = doc.get("rules", [])
                if not isinstance(rules, list):
                    profile_results[pname] = {
                        "ok": False,
                        "status": "MALFORMED_RULES",
                        "error": "قائمة القواعد تالفة",
                        "migrated": 0,
                    }
                    continue

                missing_count = sum(
                    1 for r in rules
                    if isinstance(r, dict) and (not r.get("ruleCode") or not RULE_CODE_REGEX.match(str(r.get("ruleCode"))))
                )

                if missing_count == 0:
                    profile_results[pname] = {
                        "ok": True,
                        "status": "ALREADY_UP_TO_DATE",
                        "migrated": 0,
                        "total_rules": len(rules),
                    }
                    continue

                cfg_path = self.get_profile_config_path(pname)
                bak_path = cfg_path.parent / "config.json.pre-migration.bak"
                if not bak_path.exists():
                    shutil.copy2(cfg_path, bak_path)

                migrated_in_profile = 0
                for r in rules:
                    if not isinstance(r, dict):
                        continue
                    c = r.get("ruleCode")
                    if not c or not RULE_CODE_REGEX.match(str(c)):
                        new_code = allocate_unique_rule_code(existing_codes)
                        existing_codes.add(new_code)
                        r["ruleCode"] = new_code
                        migrated_in_profile += 1

                    if "name" not in r or r["name"] is None:
                        r["name"] = ""

                doc["rules"] = rules
                staged_docs[pname] = doc
                backups[pname] = (cfg_path, cfg_path.read_bytes() if cfg_path.is_file() else b"")
                expected_shas[pname] = res.get("sha256_token")
                migrated_counts[pname] = migrated_in_profile
                backup_paths[pname] = str(bak_path)

            if staged_docs:
                # Re-verify SHAs of all staged profiles immediately before writing
                for pname in staged_docs:
                    p_cfg_path = backups[pname][0]
                    disk_bytes = p_cfg_path.read_bytes() if p_cfg_path.is_file() else b""
                    disk_sha = hashlib.sha256(disk_bytes).hexdigest() if disk_bytes else None
                    exp_sha = expected_shas.get(pname)
                    if exp_sha is not None and disk_sha != exp_sha:
                        return {
                            "ok": False,
                            "code": "STALE_CONFIG",
                            "message": f"تم تعديل البروفايل '{pname}' على القرص قبل كتابة الترحيل مباشرة.",
                            "stale_profile": pname,
                            "current_sha256": disk_sha,
                        }

                written_profiles: List[str] = []
                restored_profiles: List[str] = []
                failed_restoration: List[str] = []
                write_failed = False
                fail_error = ""

                for pname, pdoc in staged_docs.items():
                    p_cfg_path = backups[pname][0]
                    try:
                        atomic_write_json(p_cfg_path, pdoc)
                        written_profiles.append(pname)
                    except Exception as e:
                        write_failed = True
                        fail_error = str(e)
                        break

                if write_failed:
                    for wp in written_profiles:
                        p_cfg_path, orig_bytes = backups[wp]
                        try:
                            if orig_bytes:
                                temp_fd, temp_path = tempfile.mkstemp(
                                    dir=p_cfg_path.parent, prefix=".rollback_", suffix=".json"
                                )
                                with os.fdopen(temp_fd, "wb") as f:  # encoding="utf-8" binary rollback
                                    f.write(orig_bytes)
                                    f.flush()
                                    os.fsync(f.fileno())
                                os.replace(temp_path, p_cfg_path)
                                restored_profiles.append(wp)
                            else:
                                if p_cfg_path.exists():
                                    p_cfg_path.unlink()
                                restored_profiles.append(wp)
                        except Exception:
                            failed_restoration.append(wp)

                    return {
                        "ok": False,
                        "code": "WRITE_FAILURE",
                        "message": f"فشلت عملية ترحيل البيانات: {fail_error}. تم استرجاع الملفات الأصلية.",
                        "modified_profiles": written_profiles,
                        "restored_profiles": restored_profiles,
                        "failed_restoration_profiles": failed_restoration,
                    }

                for pname, count in migrated_counts.items():
                    total_migrated += count
                    profile_results[pname] = {
                        "ok": True,
                        "status": "MIGRATED",
                        "migrated": count,
                        "total_rules": len(staged_docs[pname]["rules"]),
                        "backup_path": backup_paths.get(pname),
                    }

            return {
                "ok": True,
                "total_migrated": total_migrated,
                "profiles": profile_results,
            }

    def resolve_link_conflict(
        self,
        conflicting_code: str,
        authoritative_profile: str,
        expected_shas: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolves a link conflict across all participating profiles by adopting
        the canonical allowlist from the authoritative profile's rule on disk.
        Validates expected_shas for all participating profiles, re-validates before
        write, and uses atomic per-file writes with exact raw bytes rollback."""
        if not conflicting_code or not RULE_CODE_REGEX.match(conflicting_code):
            return {"ok": False, "code": "INVALID_RULE_CODE", "message": "كود القاعدة غير صالح."}

        auth_safe = self.validate_name(authoritative_profile)

        with self._write_mutex:
            if not self.ownership_guard.is_owned():
                if not self.ownership_guard.acquire():
                    return {
                        "ok": False,
                        "code": "OWNERSHIP_COLLISION",
                        "message": "لا يمكن تسوية التضارب: المجلد الرئيسي مقفل بواسطة جلسة تطبيق أخرى نشطة.",
                    }

            # Find all participating profiles and their rules
            participating: Dict[str, Dict[str, Any]] = {}
            auth_rule = None

            for prof in self.list_profiles():
                pname = prof["name"]
                pcfg_res = self.load_profile_config_result(pname)
                if not pcfg_res.get("ok"):
                    continue
                pdata = pcfg_res.get("data", {})
                prules = pdata.get("rules", [])
                for r in prules:
                    if isinstance(r, dict) and r.get("ruleCode") == conflicting_code:
                        participating[pname] = pcfg_res
                        if pname == auth_safe:
                            auth_rule = r
                        break

            if auth_safe not in participating or auth_rule is None:
                return {
                    "ok": False,
                    "code": "AUTHORITATIVE_RULE_NOT_FOUND",
                    "message": f"لم يتم العثور على كود القاعدة '{conflicting_code}' داخل البروفايل المعتمد '{auth_safe}'.",
                }

            # Require valid tokens for every participating profile determined from authoritative disk state
            if not isinstance(expected_shas, dict):
                return {
                    "ok": False,
                    "code": "MISSING_CONCURRENCY_TOKEN",
                    "message": "يجب تقديم رموز التزامن لكافة البروفايلات المشاركة في التسوية.",
                    "missing_profiles": sorted(list(participating.keys())),
                }

            missing_profiles = [pname for pname in participating if not expected_shas.get(pname)]
            if missing_profiles:
                return {
                    "ok": False,
                    "code": "MISSING_CONCURRENCY_TOKEN",
                    "message": f"رموز التزامن مفقودة للبروفايلات المشاركة في التسوية: {', '.join(sorted(missing_profiles))}.",
                    "missing_profiles": sorted(missing_profiles),
                }

            for pname, pres in participating.items():
                exp_sha = expected_shas.get(pname)
                actual_sha = pres.get("sha256_token")
                if exp_sha != actual_sha:
                    return {
                        "ok": False,
                        "code": "STALE_CONFIG",
                        "message": f"تم تعديل البروفايل '{pname}' على القرص منذ فحص التضارب. يرجى إعادة المحاولة.",
                        "stale_profile": pname,
                        "current_sha256": actual_sha,
                    }

            # Extract canonical allowlist from authoritative rule
            auth_keywords = list(auth_rule.get("keywords", [])) if isinstance(auth_rule.get("keywords"), list) else []
            auth_keyword = auth_rule.get("keyword", ", ".join(auth_keywords))
            auth_reply = str(auth_rule.get("reply", ""))
            auth_match_type = str(auth_rule.get("matchType", "ultra_exact"))
            auth_case_sensitive = bool(auth_rule.get("caseSensitive", False))
            auth_context_kws = list(auth_rule.get("contextKeywords", [])) if isinstance(auth_rule.get("contextKeywords"), list) else []
            auth_context_kw = auth_rule.get("contextKeyword", ", ".join(auth_context_kws))
            auth_context_match = str(auth_rule.get("contextMatchType", "contains"))

            staged_docs: Dict[str, Dict[str, Any]] = {}
            backups: Dict[str, Tuple[Path, bytes]] = {}
            expected_shas_to_check: Dict[str, str] = {}

            for pname, pres in participating.items():
                pcfg_path = self.get_profile_config_path(pname)
                pdata = pres["data"]
                prules = pdata.get("rules", [])
                for r in prules:
                    if isinstance(r, dict) and r.get("ruleCode") == conflicting_code:
                        # Synchronize canonical allowlist while preserving id, name, active, order
                        r["keywords"] = list(auth_keywords)
                        r["keyword"] = auth_keyword
                        r["reply"] = auth_reply
                        r["matchType"] = auth_match_type
                        r["caseSensitive"] = auth_case_sensitive
                        r["contextKeywords"] = list(auth_context_kws)
                        r["contextKeyword"] = auth_context_kw
                        r["contextMatchType"] = auth_context_match

                staged_docs[pname] = pdata
                backups[pname] = (pcfg_path, pcfg_path.read_bytes() if pcfg_path.is_file() else b"")
                expected_shas_to_check[pname] = pres.get("sha256_token")

            # Re-verify SHAs of all participating profiles immediately before writing
            for pname in staged_docs:
                p_cfg_path = backups[pname][0]
                disk_bytes = p_cfg_path.read_bytes() if p_cfg_path.is_file() else b""
                disk_sha = hashlib.sha256(disk_bytes).hexdigest() if disk_bytes else None
                exp_sha = expected_shas_to_check.get(pname)
                if exp_sha is not None and disk_sha != exp_sha:
                    return {
                        "ok": False,
                        "code": "STALE_CONFIG",
                        "message": f"تم تعديل البروفايل '{pname}' على القرص قبل كتابة التسوية مباشرة.",
                        "stale_profile": pname,
                        "current_sha256": disk_sha,
                    }

            # Atomic writes with exact raw bytes rollback
            written_profiles: List[str] = []
            restored_profiles: List[str] = []
            failed_restoration: List[str] = []
            write_failed = False
            fail_error = ""

            for pname, pdoc in staged_docs.items():
                p_cfg_path = backups[pname][0]
                try:
                    atomic_write_json(p_cfg_path, pdoc)
                    written_profiles.append(pname)
                except Exception as e:
                    write_failed = True
                    fail_error = str(e)
                    break

            if write_failed:
                for wp in written_profiles:
                    p_cfg_path, orig_bytes = backups[wp]
                    try:
                        if orig_bytes:
                            temp_fd, temp_path = tempfile.mkstemp(
                                dir=p_cfg_path.parent, prefix=".rollback_", suffix=".json"
                            )
                            with os.fdopen(temp_fd, "wb") as f:  # encoding="utf-8" binary rollback
                                f.write(orig_bytes)
                                f.flush()
                                os.fsync(f.fileno())
                            os.replace(temp_path, p_cfg_path)
                            restored_profiles.append(wp)
                        else:
                            if p_cfg_path.exists():
                                p_cfg_path.unlink()
                            restored_profiles.append(wp)
                    except Exception:
                        failed_restoration.append(wp)

                return {
                    "ok": False,
                    "code": "WRITE_FAILURE",
                    "message": f"فشلت عملية تسوية التضارب: {fail_error}. تم استرجاع الملفات الأصلية.",
                    "modified_profiles": written_profiles,
                    "restored_profiles": restored_profiles,
                    "failed_restoration_profiles": failed_restoration,
                }

            auth_new_bytes = self.get_profile_config_path(auth_safe).read_bytes()
            auth_new_sha = hashlib.sha256(auth_new_bytes).hexdigest()

            return {
                "ok": True,
                "disk_ok": True,
                "code": "OK",
                "message": f"تمت تسوية تضارب كود القاعدة '{conflicting_code}' بنجاح باستخدام البروفايل '{auth_safe}'.",
                "modified_profiles": list(staged_docs.keys()),
                "authoritative_profile": auth_safe,
                "conflicting_code": conflicting_code,
                "sha256_token": auth_new_sha,
                "target_config": staged_docs.get(auth_safe),
            }
