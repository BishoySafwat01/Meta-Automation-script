#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Suite Profile Manager Module (V6.4.1)
Author: Bishoy Safwat (Senior Automation & Systems Engineer)
Provides thread-safe and process-isolated multi-tenant sandbox management,
Schema V2 validation, idempotent migration, Crockford Base32 identity allocation,
and cross-profile synchronization engine.
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
import hashlib
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Schema Constants & Enums
# ---------------------------------------------------------------------------
SCHEMA_VERSION: int = 2
CROCKFORD_ALPHABET: str = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CROCKFORD_REGEX = re.compile(r"^MBS-[0-9A-HJKMNP-TV-Z]{8}$")
RULE_ID_REGEX = re.compile(r"^rule_[0-9a-f]{32}$")
UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\u0600-\u06FF\s-]+$")

VALID_MATCH_TYPES: Set[str] = {"ultra_exact", "contains", "exact", "regex"}
SYNCHRONIZED_ALLOWLIST: Set[str] = {"keywords", "reply", "contextKeywords", "matchType"}

DEFAULT_TEMPLATE_CONFIG: Dict[str, Any] = {
    "schemaVersion": SCHEMA_VERSION,
    "rules": [],
    "config": {
        "typingSpeed": 15,
        "minTypingSpeed": 11,
        "maxTypingSpeed": 19,
        "minCooldown": 850,
        "maxCooldown": 1150,
        "scrollThread": True,
        "highlightRows": True,
        "monitoringInterval": 5000
    },
    "auto_start": False
}


# ---------------------------------------------------------------------------
# Structured Exception Hierarchy
# ---------------------------------------------------------------------------
class ProfileSyncError(Exception):
    """Base exception for profile synchronization and schema errors."""
    def __init__(self, code: str, message: str, **kwargs):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = kwargs

    def to_dict(self) -> Dict[str, Any]:
        d = {"ok": False, "code": self.code, "message": self.message}
        d.update(self.details)
        return d


class CatalogBusyError(ProfileSyncError):
    def __init__(self, message: str = "Catalog lock is busy"):
        super().__init__("CATALOG_BUSY", message)


class LinkedProfileBusyError(ProfileSyncError):
    def __init__(self, blocked_profiles: List[str], message: str = "A linked profile is owned by another application instance."):
        super().__init__("LINKED_PROFILE_BUSY", message, blockedProfiles=blocked_profiles)
        self.blockedProfiles = blocked_profiles


class StaleConfigRevisionError(ProfileSyncError):
    def __init__(self, message: str = "Config revision is stale"):
        super().__init__("STALE_CONFIG_REVISION", message)


class StaleLinkRevisionError(ProfileSyncError):
    def __init__(self, message: str = "Linked rule revision is stale"):
        super().__init__("STALE_LINK_REVISION", message)


class DuplicateRuleCodeError(ProfileSyncError):
    def __init__(self, code_val: str, message: str = "Duplicate ruleCode within profile"):
        super().__init__("DUPLICATE_RULE_CODE", message, ruleCode=code_val)


class DuplicateProfileIdError(ProfileSyncError):
    def __init__(self, pid: str, message: str = "Duplicate profileId within profile root"):
        super().__init__("DUPLICATE_PROFILE_ID", message, profileId=pid)


class FutureSchemaVersionError(ProfileSyncError):
    def __init__(self, version: Any, message: str = "Unsupported future schemaVersion"):
        super().__init__("FUTURE_SCHEMA_VERSION", message, schemaVersion=version)


class InvalidRuleError(ProfileSyncError):
    def __init__(self, message: str = "Invalid rule schema"):
        super().__init__("INVALID_RULE", message)


# ---------------------------------------------------------------------------
# Result Data Structures
# ---------------------------------------------------------------------------
@dataclass
class SaveResult:
    """Structured result returned by ProfileSyncCoordinator operations."""
    ok: bool
    code: str = "OK"
    message: str = ""
    sourceProfile: str = ""
    canonicalSourceConfig: Optional[Dict[str, Any]] = None
    configRevision: int = 0
    changedProfiles: List[str] = field(default_factory=list)
    blockedProfiles: List[str] = field(default_factory=list)
    runtimeApplyPayloads: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "sourceProfile": self.sourceProfile,
            "canonicalSourceConfig": self.canonicalSourceConfig,
            "configRevision": self.configRevision,
            "changedProfiles": self.changedProfiles,
            "blockedProfiles": self.blockedProfiles,
            "runtimeApplyPayloads": self.runtimeApplyPayloads,
            "warnings": self.warnings,
            "errors": self.errors
        }


# ---------------------------------------------------------------------------
# Identity Generators
# ---------------------------------------------------------------------------
def generate_crockford_base32(length: int = 8) -> str:
    """Generate random Crockford Base32 string of specified length using secrets."""
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))


def generate_rule_code() -> str:
    """Generate a canonical MBS rule code: MBS-[0-9A-HJKMNP-TV-Z]{8}."""
    return f"MBS-{generate_crockford_base32(8)}"


def generate_rule_id() -> str:
    """Generate a canonical local rule ID: rule_[0-9a-f]{32}."""
    return f"rule_{uuid.uuid4().hex}"


def generate_profile_id() -> str:
    """Generate a canonical RFC 4122 UUID v4 string."""
    return str(uuid.uuid4())


def get_rule_allowlist_canonical(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Extract canonical representation of synchronized allowlist fields."""
    return {
        "keywords": list(rule.get("keywords", [])),
        "reply": str(rule.get("reply", "")),
        "contextKeywords": list(rule.get("contextKeywords", [])),
        "matchType": str(rule.get("matchType", "ultra_exact"))
    }


def hash_rule_allowlist(rule: Dict[str, Any]) -> str:
    """Compute SHA-256 hash of canonical synchronized allowlist payload."""
    canonical = get_rule_allowlist_canonical(rule)
    payload_bytes = json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload_bytes).hexdigest()


# ---------------------------------------------------------------------------
# File Persistence & OS Leases
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

        # Windows file lock retry with exponential backoff [P2-WIN-01]
        max_retries = 5
        for attempt in range(max_retries):
            try:
                os.replace(temp_path, path)
                break
            except PermissionError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(0.05 * (2 ** attempt))

        # Execute directory fsync on POSIX systems
        if os.name != "nt":
            try:
                dir_fd = getattr(os, "open")(str(parent_dir), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except Exception:
                pass
        return True
    except Exception as e:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        raise RuntimeError(f"Failed to atomically write JSON to '{path}': {e}")


class ProfileLease:
    """Cross-platform OS-level exclusive lease manager for profile directories."""

    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir)
        self.lock_path = self.profile_dir / ".app_profile.lock"
        self._file_obj = None

    def acquire(self):
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._file_obj = open(self.lock_path, "a+", encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"PROFILE_LOCK_OPEN_FAILED: {e}")

        fd = self._file_obj.fileno()
        if os.name == "nt":
            import msvcrt
            try:
                self._file_obj.seek(0)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except (OSError, IOError):
                self._close_file()
                raise RuntimeError("PROFILE_ALREADY_RUNNING")
        else:
            import fcntl
            try:
                flags = fcntl.fcntl(fd, fcntl.F_GETFD)
                fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
            except Exception:
                pass
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (OSError, IOError):
                self._close_file()
                raise RuntimeError("PROFILE_ALREADY_RUNNING")

        try:
            self._file_obj.seek(0)
            self._file_obj.truncate()
            self._file_obj.write(f"{os.getpid()}\n")
            self._file_obj.flush()
        except Exception:
            pass

    def release(self):
        if self._file_obj is not None:
            try:
                fd = self._file_obj.fileno()
                if os.name == "nt":
                    import msvcrt
                    import sys as _sys
                    try:
                        self._file_obj.seek(0)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except OSError as e:
                        if _sys.stderr is not None:
                            _sys.stderr.write(
                                f"[ProfileLease] WARNING: Windows msvcrt unlock error on "
                                f"'{self.lock_path.name}': {e}\n"
                            )
                else:
                    import fcntl
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError as e:
                        import sys as _sys
                        if _sys.stderr is not None:
                            _sys.stderr.write(
                                f"[ProfileLease] WARNING: POSIX flock unlock error on "
                                f"'{self.lock_path.name}': {e}\n"
                            )
            finally:
                self._close_file()

    def _close_file(self):
        if self._file_obj:
            try:
                self._file_obj.close()
            except Exception:
                pass
            self._file_obj = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LeaseAuthority:
    """An unforgeable in-process capability representing a lifetime ProfileLease
    already held by a running worker."""
    def __init__(self, profile_name: str, profile_dir: Path, lease: ProfileLease):
        self.profile_name = profile_name
        self.profile_dir = Path(profile_dir).resolve()
        self.lease = lease


class ProfileCatalogLock:
    """OS-level catalog lease at profiles/.sync.lock.
    Serializes profile-root membership snapshots, migration, code allocation,
    admission, rename/delete, and coordinated commit preparation.
    """
    _local = threading.local()

    def __init__(self, base_dir: Path, timeout: float = 5.0):
        self.base_dir = Path(base_dir).resolve()
        self.lock_path = self.base_dir / ".sync.lock"
        self.timeout = float(timeout)
        self._file_obj = None

    def acquire(self):
        if not hasattr(self._local, "active_locks"):
            self._local.active_locks = {}

        key = str(self.lock_path)
        if key in self._local.active_locks:
            self._local.active_locks[key]["depth"] += 1
            return

        self.base_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._file_obj = open(self.lock_path, "a+", encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"CATALOG_LOCK_OPEN_FAILED: {e}")

        fd = self._file_obj.fileno()
        start = time.monotonic()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._file_obj.seek(0)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    flags = fcntl.fcntl(fd, fcntl.F_GETFD)
                    fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (OSError, IOError):
                if time.monotonic() - start >= self.timeout:
                    try:
                        self._file_obj.close()
                    except Exception:
                        pass
                    self._file_obj = None
                    raise CatalogBusyError(f"Catalog lock timed out after {self.timeout}s on '{self.lock_path}'")
                time.sleep(0.02)

        try:
            self._file_obj.seek(0)
            self._file_obj.truncate()
            self._file_obj.write(f"{os.getpid()}\n")
            self._file_obj.flush()
        except Exception:
            pass

        self._local.active_locks[key] = {
            "depth": 1,
            "file_obj": self._file_obj
        }

    def release(self):
        if not hasattr(self._local, "active_locks"):
            return

        key = str(self.lock_path)
        entry = self._local.active_locks.get(key)
        if not entry:
            return

        entry["depth"] -= 1
        if entry["depth"] <= 0:
            f_obj = entry.get("file_obj") or self._file_obj
            del self._local.active_locks[key]
            if f_obj is not None:
                try:
                    fd = f_obj.fileno()
                    if os.name == "nt":
                        import msvcrt
                        f_obj.seek(0)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                finally:
                    try:
                        f_obj.close()
                    except Exception:
                        pass
            self._file_obj = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# ---------------------------------------------------------------------------
# Code Allocator & Schema Validator
# ---------------------------------------------------------------------------
class RuleCodeAllocator:
    """Scans profile configurations and produces collision-free Crockford Base32 ruleCodes."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()

    def get_all_existing_codes(self) -> Set[str]:
        codes = set()
        if not self.base_dir.exists():
            return codes
        for pdir in self.base_dir.iterdir():
            if pdir.is_dir():
                cfg_path = pdir / "config.json"
                if cfg_path.is_file():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            for r in data.get("rules", []):
                                if isinstance(r, dict):
                                    c = r.get("ruleCode")
                                    if c and isinstance(c, str):
                                        codes.add(c)
                    except Exception:
                        pass
        return codes

    def allocate_code(self, existing_codes: Optional[Set[str]] = None) -> str:
        if existing_codes is None:
            existing_codes = self.get_all_existing_codes()
        for _ in range(2000):
            candidate = generate_rule_code()
            if candidate not in existing_codes:
                existing_codes.add(candidate)
                return candidate
        raise RuntimeError("RULE_CODE_EXHAUSTION: Unable to allocate unique rule code after 2000 attempts")


class RuleSchemaValidator:
    """Canonical schema validator for profile configuration V2."""

    @staticmethod
    def is_valid_uuid(val: Any) -> bool:
        if not isinstance(val, str):
            return False
        return bool(UUID_REGEX.match(val))

    @staticmethod
    def is_valid_rule_code(val: Any) -> bool:
        if not isinstance(val, str):
            return False
        return bool(CROCKFORD_REGEX.match(val))

    @staticmethod
    def is_valid_rule_id(val: Any) -> bool:
        if not isinstance(val, str):
            return False
        return bool(RULE_ID_REGEX.match(val))

    @classmethod
    def validate_profile(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate profile schema v2 structure. Returns (is_valid, errors)."""
        errors = []
        if not isinstance(data, dict):
            return False, ["Profile data must be a JSON object"]

        ver = data.get("schemaVersion")
        if ver != 2:
            if isinstance(ver, int) and ver > 2:
                raise FutureSchemaVersionError(ver, f"Unsupported future schemaVersion: {ver}")
            errors.append(f"schemaVersion must be 2, got {ver}")

        pid = data.get("profileId")
        if not cls.is_valid_uuid(pid):
            errors.append(f"profileId must be a valid UUID string, got {repr(pid)}")

        rev = data.get("configRevision")
        if not isinstance(rev, int) or rev < 0:
            errors.append(f"configRevision must be a non-negative integer, got {repr(rev)}")

        if not isinstance(data.get("rules"), list):
            errors.append("rules must be an array")

        if not isinstance(data.get("config"), dict):
            errors.append("config must be an object")

        if not isinstance(data.get("auto_start", False), bool):
            errors.append("auto_start must be a boolean")

        seen_codes = set()
        seen_ids = set()
        for idx, rule in enumerate(data.get("rules", [])):
            if not isinstance(rule, dict):
                errors.append(f"Rule at index {idx} must be an object")
                continue

            r_id = rule.get("id")
            if not r_id or not isinstance(r_id, str):
                errors.append(f"Rule #{idx}: id must be a non-empty string")
            elif r_id in seen_ids:
                errors.append(f"Rule #{idx}: duplicate rule id '{r_id}' within profile")
            else:
                seen_ids.add(r_id)

            code = rule.get("ruleCode")
            if not cls.is_valid_rule_code(code):
                errors.append(f"Rule #{idx}: ruleCode must match format MBS-[0-9A-HJKMNP-TV-Z]{{8}}, got {repr(code)}")
            elif code in seen_codes:
                errors.append(f"Rule #{idx}: duplicate ruleCode '{code}' within profile")
                raise DuplicateRuleCodeError(code, f"Duplicate ruleCode '{code}' inside profile")
            else:
                seen_codes.add(code)

            kws = rule.get("keywords")
            if not isinstance(kws, list) or len(kws) == 0:
                errors.append(f"Rule #{idx}: keywords must be a non-empty array of strings")
            else:
                for k_idx, kw in enumerate(kws):
                    if not isinstance(kw, str) or len(kw) == 0:
                        errors.append(f"Rule #{idx}: keywords[{k_idx}] must be a non-empty string")

            mt = rule.get("matchType")
            if mt not in VALID_MATCH_TYPES:
                errors.append(f"Rule #{idx}: matchType must be one of {sorted(VALID_MATCH_TYPES)}, got {repr(mt)}")

            cmt = rule.get("contextMatchType")
            if cmt is not None and cmt not in VALID_MATCH_TYPES:
                errors.append(f"Rule #{idx}: contextMatchType must be one of {sorted(VALID_MATCH_TYPES)}, got {repr(cmt)}")

            reply = rule.get("reply")
            if not isinstance(reply, str) or len(reply.strip()) == 0:
                errors.append(f"Rule #{idx}: reply must be a non-empty string")

            sync = rule.get("sync")
            if sync is not None:
                if not isinstance(sync, dict):
                    errors.append(f"Rule #{idx}: sync must be an object")
                else:
                    if not isinstance(sync.get("revision"), int) or sync.get("revision") < 0:
                        errors.append(f"Rule #{idx}: sync.revision must be a non-negative integer")
                    if not cls.is_valid_uuid(sync.get("updatedByProfileId")):
                        errors.append(f"Rule #{idx}: sync.updatedByProfileId must be a valid UUID")
                    if not cls.is_valid_uuid(sync.get("operationId")):
                        errors.append(f"Rule #{idx}: sync.operationId must be a valid UUID")
                    m_pids = sync.get("memberProfileIds")
                    if not isinstance(m_pids, list):
                        errors.append(f"Rule #{idx}: sync.memberProfileIds must be a list of UUIDs")

        return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Idempotent Schema Migrator
# ---------------------------------------------------------------------------
class RuleSchemaMigrator:
    """Idempotent migration engine from Schema V1 (or legacy) to Schema V2."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.allocator = RuleCodeAllocator(self.base_dir)

    def needs_migration(self, profile_data: Dict[str, Any]) -> bool:
        if not isinstance(profile_data, dict):
            return True
        if profile_data.get("schemaVersion") != 2:
            return True
        if not RuleSchemaValidator.is_valid_uuid(profile_data.get("profileId")):
            return True
        if not isinstance(profile_data.get("configRevision"), int):
            return True
        for r in profile_data.get("rules", []):
            if not isinstance(r, dict):
                return True
            if not RuleSchemaValidator.is_valid_rule_code(r.get("ruleCode")):
                return True
            if not isinstance(r.get("keywords"), list):
                return True
            if "sync" not in r:
                return True
        return False

    def migrate_profile_data(
        self,
        profile_dir: Path,
        profile_data: Dict[str, Any],
        existing_codes: Optional[Set[str]] = None,
        write_backup: bool = True
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Migrates a profile's data to Schema V2 idempotently."""
        profile_dir = Path(profile_dir).resolve()
        if existing_codes is None:
            existing_codes = self.allocator.get_all_existing_codes()

        ver = profile_data.get("schemaVersion")
        if isinstance(ver, int) and ver > 2:
            raise FutureSchemaVersionError(ver, f"Cannot migrate profile with future schemaVersion: {ver}")

        # 1. Create same-profile pre-v2 backup once
        backup_path = profile_dir / "config.pre-v2.backup.json"
        if write_backup and not backup_path.exists() and ver != 2:
            atomic_write_json(backup_path, profile_data)

        migrated = json.loads(json.dumps(profile_data))
        migrated["schemaVersion"] = 2

        # 2. Profile identity & revisions
        pid = migrated.get("profileId")
        if not RuleSchemaValidator.is_valid_uuid(pid):
            pid = generate_profile_id()
        migrated["profileId"] = pid

        rev = migrated.get("configRevision")
        if not isinstance(rev, int) or rev < 0:
            rev = 0
        migrated["configRevision"] = rev

        if "config" not in migrated or not isinstance(migrated["config"], dict):
            migrated["config"] = json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG["config"]))
        if "auto_start" not in migrated:
            migrated["auto_start"] = False

        # 3. Rule migration
        report = {
            "profileId": pid,
            "rulesMigrated": 0,
            "priorModes": {},
            "warnings": []
        }

        rules = migrated.get("rules", [])
        if not isinstance(rules, list):
            rules = []

        assigned_codes = set()
        migrated_rules = []
        for idx, r in enumerate(rules):
            if not isinstance(r, dict):
                continue

            r_migrated = dict(r)

            # Local ID: preserve if valid UUID-hex format, else generate fresh
            orig_id = r_migrated.get("id")
            r_id = orig_id
            if not r_id or not RuleSchemaValidator.is_valid_rule_id(r_id):
                r_id = generate_rule_id()
            r_migrated["id"] = r_id

            # Keywords: array authoritative, convert string if needed
            kws = r_migrated.get("keywords")
            if isinstance(kws, list):
                clean_kws = [str(k) for k in kws if str(k).strip() != ""]
            else:
                kw_str = r_migrated.get("keyword")
                if isinstance(kw_str, str) and kw_str.strip():
                    clean_kws = [k.strip() for k in kw_str.split(",") if k.strip()]
                else:
                    clean_kws = []
            r_migrated["keywords"] = clean_kws
            r_migrated["keyword"] = ", ".join(clean_kws)

            # Context keywords
            ctx_kws = r_migrated.get("contextKeywords")
            if isinstance(ctx_kws, list):
                clean_ctx = [str(k) for k in ctx_kws if str(k).strip() != ""]
            else:
                ctx_str = r_migrated.get("contextKeyword")
                if isinstance(ctx_str, str) and ctx_str.strip():
                    clean_ctx = [k.strip() for k in ctx_str.split(",") if k.strip()]
                else:
                    clean_ctx = []
            r_migrated["contextKeywords"] = clean_ctx
            r_migrated["contextKeyword"] = ", ".join(clean_ctx)

            # Prior mode recording & mandate: convert legacy primary to ultra_exact
            prior_mode = r_migrated.get("matchType", "contains")
            if orig_id:
                report["priorModes"][orig_id] = prior_mode
            report["priorModes"][r_id] = prior_mode
            if ver != 2 or r_migrated.get("matchType") not in VALID_MATCH_TYPES:
                r_migrated["matchType"] = "ultra_exact"

            if r_migrated.get("contextMatchType") not in VALID_MATCH_TYPES:
                r_migrated["contextMatchType"] = "contains"

            # Name fallback
            r_name = r_migrated.get("name")
            if not r_name or not isinstance(r_name, str) or not r_name.strip():
                if clean_kws:
                    r_name = clean_kws[0][:160]
                else:
                    r_name = f"قاعدة #{idx + 1}"
            r_migrated["name"] = str(r_name).strip()[:160]

            # RuleCode: preserve if valid and not duplicate, else allocate
            code = r_migrated.get("ruleCode")
            if (
                RuleSchemaValidator.is_valid_rule_code(code)
                and code not in assigned_codes
            ):
                pass
            else:
                code = self.allocator.allocate_code(existing_codes | assigned_codes)
            assigned_codes.add(code)
            existing_codes.add(code)
            r_migrated["ruleCode"] = code

            # Boolean flags
            r_migrated["caseSensitive"] = bool(r_migrated.get("caseSensitive", False))
            active = bool(r_migrated.get("active", True))
            reply = str(r_migrated.get("reply", "")).strip()
            r_migrated["reply"] = reply
            if len(clean_kws) == 0 or not reply:
                active = False
                report["warnings"].append(f"Rule #{idx} ({r_id}) disabled due to missing keyword or reply")
            r_migrated["active"] = active

            r_migrated["isLinked"] = bool(r_migrated.get("isLinked", False))
            r_migrated["shared"] = bool(r_migrated.get("shared", False))

            # Sync metadata
            sync = r_migrated.get("sync")
            if not isinstance(sync, dict) or "revision" not in sync:
                r_migrated["sync"] = {
                    "revision": 0,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "updatedByProfileId": pid,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [pid]
                }
            else:
                sync_members = sync.get("memberProfileIds")
                if not isinstance(sync_members, list) or pid not in sync_members:
                    sync["memberProfileIds"] = list(set((sync_members or []) + [pid]))
                r_migrated["sync"] = sync

            migrated_rules.append(r_migrated)
            report["rulesMigrated"] += 1

        migrated["rules"] = migrated_rules
        return migrated, report


# ---------------------------------------------------------------------------
# Cross-Profile Synchronization Coordinator
# ---------------------------------------------------------------------------
class ProfileSyncCoordinator:
    """Atomic multi-profile persistence and synchronized allowlist propagation engine."""

    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.allocator = RuleCodeAllocator(self.base_dir)
        self.migrator = RuleSchemaMigrator(self.base_dir)

    def scan_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Read and parse config.json for all valid profile directories."""
        profiles = {}
        if not self.base_dir.exists():
            return profiles
        for pdir in sorted(self.base_dir.iterdir()):
            if pdir.is_dir():
                cfg_path = pdir / "config.json"
                if cfg_path.is_file():
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict):
                            profiles[pdir.name] = data
                    except Exception:
                        pass
        return profiles

    def build_linked_index(self, all_profiles: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Build ephemeral mapping: ruleCode -> list of entries with metadata."""
        index: Dict[str, List[Dict[str, Any]]] = {}
        for pname, doc in all_profiles.items():
            pid = doc.get("profileId")
            rev = doc.get("configRevision", 0)
            for idx, r in enumerate(doc.get("rules", [])):
                if not isinstance(r, dict):
                    continue
                code = r.get("ruleCode")
                if code and isinstance(code, str):
                    if code not in index:
                        index[code] = []
                    index[code].append({
                        "profileName": pname,
                        "profileId": pid,
                        "ruleIndex": idx,
                        "rule": r,
                        "configRevision": rev
                    })
        return index

    def recompute_link_metadata(self, all_profiles: Dict[str, Dict[str, Any]]):
        """Recompute isLinked and shared flags across all profiles in root."""
        code_admitted_profiles: Dict[str, Set[str]] = {}
        for pname, doc in all_profiles.items():
            pid = doc.get("profileId")
            for r in doc.get("rules", []):
                if not isinstance(r, dict):
                    continue
                code = r.get("ruleCode")
                if not code:
                    continue
                sync = r.get("sync") or {}
                members = set(sync.get("memberProfileIds") or [pid])
                if pid in members:
                    if code not in code_admitted_profiles:
                        code_admitted_profiles[code] = set()
                    code_admitted_profiles[code].add(pid)

        for pname, doc in all_profiles.items():
            pid = doc.get("profileId")
            for r in doc.get("rules", []):
                if not isinstance(r, dict):
                    continue
                code = r.get("ruleCode")
                if code and len(code_admitted_profiles.get(code, set())) >= 2:
                    r["isLinked"] = True
                    r["shared"] = True
                else:
                    r["isLinked"] = False
                    r["shared"] = False

    def reconcile_crash_recovery(self) -> Dict[str, Any]:
        """Scan for orphaned .sync_op_*.json files and repair interrupted operations.
        Also check for split-brain conflicts (equal highest revision, differing payload hashes)
        and propagate unique highest revisions to lagging linked copies."""
        with ProfileCatalogLock(self.base_dir):
            ops: Dict[str, List[Tuple[Path, Path, Dict[str, Any]]]] = {}
            for pdir in self.base_dir.iterdir():
                if pdir.is_dir():
                    for f in pdir.glob(".sync_op_*.json"):
                        try:
                            with open(f, "r", encoding="utf-8") as rfile:
                                rdata = json.load(rfile)
                            op_id = rdata.get("operationId")
                            if op_id:
                                if op_id not in ops:
                                    ops[op_id] = []
                                ops[op_id].append((pdir, f, rdata))
                        except Exception:
                            pass

            repaired = []
            for op_id, records in ops.items():
                for pdir, fpath, rdata in records:
                    cfg_path = pdir / "config.json"
                    current_cfg = {}
                    if cfg_path.is_file():
                        try:
                            with open(cfg_path, "r", encoding="utf-8") as cf:
                                current_cfg = json.load(cf)
                        except Exception:
                            pass
                    target_rev = rdata.get("targetRevision", 0)
                    curr_rev = current_cfg.get("configRevision", -1)
                    if curr_rev != target_rev:
                        atomic_write_json(cfg_path, rdata.get("document"))
                        repaired.append(f"{pdir.name}:{op_id}")

                for _, fpath, _ in records:
                    try:
                        fpath.unlink(missing_ok=True)
                    except Exception:
                        pass

            # Cross-profile linked rule reconciliation & conflict detection
            all_profs = self.scan_all_profiles()
            code_map: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
            for pname, pdoc in all_profs.items():
                for r in pdoc.get("rules", []):
                    code = r.get("ruleCode")
                    if code and r.get("isLinked"):
                        code_map.setdefault(code, []).append((pname, r))

            conflicts = []
            lagging_repairs = []
            for code, instances in code_map.items():
                if len(instances) <= 1:
                    continue

                max_rev = max(inst[1].get("sync", {}).get("revision", 0) for inst in instances)
                max_instances = [inst for inst in instances if inst[1].get("sync", {}).get("revision", 0) == max_rev]

                # Check payload hashes among max_rev instances
                hashes = {hash_rule_allowlist(inst[1]) for inst in max_instances}
                if len(hashes) > 1:
                    conflicts.append({
                        "ruleCode": code,
                        "revision": max_rev,
                        "profiles": [inst[0] for inst in max_instances]
                    })
                    continue

                leader_prof, leader_rule = max_instances[0]
                canonical_allowlist = get_rule_allowlist_canonical(leader_rule)
                leader_sync = leader_rule.get("sync", {})

                for pname, lag_rule in instances:
                    lag_rev = lag_rule.get("sync", {}).get("revision", 0)
                    if lag_rev < max_rev:
                        lag_rule.update(canonical_allowlist)
                        s = lag_rule.setdefault("sync", {})
                        s["revision"] = max_rev
                        s["updatedAt"] = leader_sync.get("updatedAt", s.get("updatedAt"))
                        s["updatedByProfileId"] = leader_sync.get("updatedByProfileId", s.get("updatedByProfileId"))
                        s["operationId"] = leader_sync.get("operationId", s.get("operationId"))
                        s["memberProfileIds"] = list(leader_sync.get("memberProfileIds", s.get("memberProfileIds", [])))

                        pdoc = all_profs[pname]
                        pdoc["configRevision"] = pdoc.get("configRevision", 0) + 1
                        cfg_target = self.base_dir / pname / "config.json"
                        atomic_write_json(cfg_target, pdoc)
                        lagging_repairs.append(f"{pname}:{code}")

            repaired.extend(lagging_repairs)
            return {
                "ok": len(conflicts) == 0,
                "repaired": repaired,
                "conflicts": conflicts
            }

    def save_profile_config_result(
        self,
        profile_name: str,
        submitted_config: Dict[str, Any],
        expected_revision: Optional[int] = None,
        lease_authorities: Optional[List[LeaseAuthority]] = None,
        extra_modified_profiles: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> SaveResult:
        """Coordinated save executing strict allowlist propagation, crash recovery snapshots,
        and universal ordered lease acquisition."""
        with ProfileCatalogLock(self.base_dir):
            pdir = (self.base_dir / profile_name).resolve()
            if not pdir.is_dir():
                return SaveResult(ok=False, code="PROFILE_NOT_FOUND", message=f"Profile '{profile_name}' directory not found")

            cfg_path = pdir / "config.json"
            stored_config = {}
            if cfg_path.is_file():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        stored_config = json.load(f)
                except Exception as e:
                    return SaveResult(ok=False, code="CONFIG_READ_ERROR", message=str(e))

            # 1. Stale configRevision check
            stored_rev = stored_config.get("configRevision", 0)
            if expected_revision is not None and stored_rev != expected_revision:
                return SaveResult(
                    ok=False,
                    code="STALE_CONFIG_REVISION",
                    message=f"Stale configRevision: expected {expected_revision}, disk is {stored_rev}",
                    sourceProfile=profile_name,
                    configRevision=stored_rev
                )

            # 2. Canonicalize & validate submitted config
            is_valid, errs = RuleSchemaValidator.validate_profile(submitted_config)
            if not is_valid:
                return SaveResult(ok=False, code="INVALID_RULE", message="; ".join(errs), sourceProfile=profile_name)

            source_pid = submitted_config.get("profileId")

            # 3. Read profile root and build linked index
            all_profiles = self.scan_all_profiles()
            disk_hashes = {
                p: hashlib.sha256(json.dumps(all_profiles[p], sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                for p in all_profiles
            }
            if extra_modified_profiles:
                all_profiles.update(extra_modified_profiles)
            all_profiles[profile_name] = json.loads(json.dumps(submitted_config))
            linked_index = self.build_linked_index(all_profiles)

            # 4. Compare allowlist changes and propagate to admitted linked instances
            stored_rules_by_code = {}
            for r in stored_config.get("rules", []):
                if isinstance(r, dict) and r.get("ruleCode"):
                    stored_rules_by_code[r.get("ruleCode")] = r

            changed_target_profiles: Dict[str, Dict[str, Any]] = {}
            operation_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()

            # Iterate through submitted rules
            for s_rule in submitted_config.get("rules", []):
                code = s_rule.get("ruleCode")
                if not code:
                    continue

                old_source_rule = stored_rules_by_code.get(code)
                allowlist_changed = False
                if not old_source_rule:
                    allowlist_changed = True
                else:
                    if hash_rule_allowlist(s_rule) != hash_rule_allowlist(old_source_rule):
                        allowlist_changed = True

                # Check linked target profiles
                target_instances = linked_index.get(code, [])
                for t_entry in target_instances:
                    t_pname = t_entry["profileName"]
                    if t_pname == profile_name:
                        continue

                    t_rule = t_entry["rule"]
                    t_doc = all_profiles[t_pname]
                    t_pid = t_doc.get("profileId")

                    # Verify admission: source_pid must be in target rule's memberProfileIds
                    t_sync = t_rule.get("sync") or {}
                    t_members = t_sync.get("memberProfileIds") or []
                    if source_pid not in t_members:
                        # External unadmitted collision: skip automatic propagation
                        continue

                    # Stale link revision check
                    s_sync = s_rule.get("sync") or {}
                    s_rev = s_sync.get("revision", 0)
                    t_rev = t_sync.get("revision", 0)
                    if t_rev > s_rev:
                        return SaveResult(
                            ok=False,
                            code="STALE_LINK_REVISION",
                            message=f"Linked rule '{code}' in profile '{t_pname}' has newer revision ({t_rev} > {s_rev})",
                            sourceProfile=profile_name
                        )

                    if allowlist_changed:
                        new_rev = max(s_rev, t_rev) + 1
                        # Update target allowlist fields
                        t_rule["keywords"] = list(s_rule.get("keywords", []))
                        t_rule["keyword"] = ", ".join(t_rule["keywords"])
                        t_rule["reply"] = s_rule.get("reply", "")
                        t_rule["contextKeywords"] = list(s_rule.get("contextKeywords", []))
                        t_rule["contextKeyword"] = ", ".join(t_rule["contextKeywords"])
                        t_rule["matchType"] = s_rule.get("matchType", "ultra_exact")

                        # Preserve local fields: id, name, active, contextMatchType, caseSensitive
                        all_members = sorted(list(set(t_members + (s_sync.get("memberProfileIds") or [source_pid]))))
                        t_rule["sync"] = {
                            "revision": new_rev,
                            "updatedAt": now_iso,
                            "updatedByProfileId": source_pid,
                            "operationId": operation_id,
                            "memberProfileIds": all_members
                        }
                        s_rule["sync"] = {
                            "revision": new_rev,
                            "updatedAt": now_iso,
                            "updatedByProfileId": source_pid,
                            "operationId": operation_id,
                            "memberProfileIds": all_members
                        }

                        if t_pname not in changed_target_profiles:
                            t_doc["configRevision"] = t_doc.get("configRevision", 0) + 1
                            changed_target_profiles[t_pname] = t_doc

            # 5. Recompute isLinked and shared flags across all profiles in root
            self.recompute_link_metadata(all_profiles)

            # Detect any profile whose contents changed from initial disk snapshot
            for pname, doc in all_profiles.items():
                if pname != profile_name:
                    curr_hash = hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                    if curr_hash != disk_hashes.get(pname):
                        if pname not in changed_target_profiles:
                            doc["configRevision"] = doc.get("configRevision", 0) + 1
                            changed_target_profiles[pname] = doc

            # 6. Increment source configRevision
            final_source_doc = all_profiles[profile_name]
            final_source_doc["configRevision"] = stored_rev + 1

            # 7. Identify all profiles requiring disk write
            affected_profiles: Dict[str, Dict[str, Any]] = {profile_name: final_source_doc}
            affected_profiles.update(changed_target_profiles)

            # 8. Sort profile paths lexicographically
            path_map = {name: (self.base_dir / name).resolve() for name in affected_profiles}
            sorted_names = sorted(path_map.keys(), key=lambda n: str(path_map[n]))

            # 9. Multi-tenant non-blocking lease acquisition
            authority_names = set()
            if lease_authorities:
                for auth in lease_authorities:
                    authority_names.add(auth.profile_name)

            acquired_leases: List[ProfileLease] = []
            for name in sorted_names:
                if name in authority_names:
                    # Current process worker already holds lifetime lease: reuse capability
                    continue
                p_lease = ProfileLease(path_map[name])
                try:
                    p_lease.acquire()
                    acquired_leases.append(p_lease)
                except Exception:
                    # Contention: abort before the first write
                    for l in reversed(acquired_leases):
                        try:
                            l.release()
                        except Exception:
                            pass
                    return SaveResult(
                        ok=False,
                        code="LINKED_PROFILE_BUSY",
                        message=f"Profile '{name}' is locked by another process",
                        sourceProfile=profile_name,
                        blockedProfiles=[name]
                    )

            # 10. Durable Commit with Crash Recovery Snapshots
            try:
                # Write per-profile recovery records
                recovery_files = []
                for name, doc in affected_profiles.items():
                    r_file = path_map[name] / f".sync_op_{operation_id}.json"
                    r_data = {
                        "operationId": operation_id,
                        "profileName": name,
                        "targetRevision": doc.get("configRevision"),
                        "timestamp": now_iso,
                        "document": doc
                    }
                    atomic_write_json(r_file, r_data)
                    recovery_files.append(r_file)

                # Atomically write config.json for all affected profiles
                for name, doc in affected_profiles.items():
                    cfg_target = path_map[name] / "config.json"
                    atomic_write_json(cfg_target, doc)

                # Clean up recovery files
                for rf in recovery_files:
                    try:
                        rf.unlink(missing_ok=True)
                    except Exception:
                        pass

            finally:
                # Release all acquired profile leases
                for l in reversed(acquired_leases):
                    try:
                        l.release()
                    except Exception:
                        pass

            # Prepare runtime apply payloads
            runtime_payloads = {
                name: doc.get("rules", []) for name, doc in affected_profiles.items()
            }

            return SaveResult(
                ok=True,
                code="OK",
                message="Profile configuration saved and synchronized successfully",
                sourceProfile=profile_name,
                canonicalSourceConfig=final_source_doc,
                configRevision=final_source_doc.get("configRevision", 0),
                changedProfiles=list(changed_target_profiles.keys()),
                runtimeApplyPayloads=runtime_payloads
            )

    def clone_rule(self, source_profile: str, target_profile: str, rule_id: str) -> SaveResult:
        """Clone a rule to target profile with fresh local ID and fresh Crockford ruleCode."""
        with ProfileCatalogLock(self.base_dir):
            all_profs = self.scan_all_profiles()
            s_doc = all_profs.get(source_profile)
            if not s_doc:
                return SaveResult(ok=False, code="SOURCE_NOT_FOUND", message=f"Source profile '{source_profile}' not found")
            t_doc = all_profs.get(target_profile)
            if not t_doc:
                return SaveResult(ok=False, code="TARGET_NOT_FOUND", message=f"Target profile '{target_profile}' not found")

            # Locate source rule
            s_rule = None
            for r in s_doc.get("rules", []):
                if r.get("id") == rule_id:
                    s_rule = r
                    break
            if not s_rule:
                return SaveResult(ok=False, code="RULE_NOT_FOUND", message=f"Rule '{rule_id}' not found in source profile")

            t_pid = t_doc.get("profileId")
            fresh_code = self.allocator.allocate_code()
            fresh_id = generate_rule_id()

            cloned_rule = {
                "id": fresh_id,
                "name": f"{s_rule.get('name', 'قاعدة')} (نسخة)",
                "ruleCode": fresh_code,
                "keywords": list(s_rule.get("keywords", [])),
                "keyword": ", ".join(s_rule.get("keywords", [])),
                "contextKeywords": list(s_rule.get("contextKeywords", [])),
                "contextKeyword": ", ".join(s_rule.get("contextKeywords", [])),
                "reply": s_rule.get("reply", ""),
                "matchType": s_rule.get("matchType", "ultra_exact"),
                "contextMatchType": s_rule.get("contextMatchType", "contains"),
                "caseSensitive": bool(s_rule.get("caseSensitive", False)),
                "active": bool(s_rule.get("active", True)),
                "isLinked": False,
                "shared": False,
                "sync": {
                    "revision": 0,
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "updatedByProfileId": t_pid,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": [t_pid]
                }
            }

            t_doc_updated = json.loads(json.dumps(t_doc))
            t_doc_updated.setdefault("rules", []).append(cloned_rule)
            return self.save_profile_config_result(target_profile, t_doc_updated)

    def link_rule_by_code(
        self,
        target_profile: str,
        existing_rule_code: str,
        draft_overrides: Optional[Dict[str, Any]] = None
    ) -> SaveResult:
        """Link target profile to an existing logical ruleCode across profiles."""
        with ProfileCatalogLock(self.base_dir):
            if not RuleSchemaValidator.is_valid_rule_code(existing_rule_code):
                return SaveResult(ok=False, code="INVALID_RULE_CODE", message=f"Invalid ruleCode format: {existing_rule_code}")

            all_profs = self.scan_all_profiles()
            t_doc = all_profs.get(target_profile)
            if not t_doc:
                return SaveResult(ok=False, code="TARGET_NOT_FOUND", message=f"Target profile '{target_profile}' not found")

            # Check if target already has this code
            for r in t_doc.get("rules", []):
                if r.get("ruleCode") == existing_rule_code:
                    return SaveResult(ok=False, code="ALREADY_LINKED", message=f"Target profile already has ruleCode '{existing_rule_code}'")

            # Find matching rule with highest sync revision
            matched_rule = None
            for pname, doc in all_profs.items():
                for r in doc.get("rules", []):
                    if r.get("ruleCode") == existing_rule_code:
                        if matched_rule is None or (r.get("sync", {}).get("revision", 0) > matched_rule.get("sync", {}).get("revision", 0)):
                            matched_rule = r

            if not matched_rule:
                return SaveResult(ok=False, code="RULE_NOT_FOUND", message=f"No existing rule found with ruleCode '{existing_rule_code}'")

            t_pid = t_doc.get("profileId")
            fresh_id = generate_rule_id()
            overrides = draft_overrides or {}

            # Create new rule instance in target
            new_rule = {
                "id": fresh_id,
                "name": overrides.get("name") or matched_rule.get("name", "قاعدة مرتبطة"),
                "ruleCode": existing_rule_code,
                "keywords": list(matched_rule.get("keywords", [])),
                "keyword": ", ".join(matched_rule.get("keywords", [])),
                "contextKeywords": list(matched_rule.get("contextKeywords", [])),
                "contextKeyword": ", ".join(matched_rule.get("contextKeywords", [])),
                "reply": matched_rule.get("reply", ""),
                "matchType": matched_rule.get("matchType", "ultra_exact"),
                "contextMatchType": matched_rule.get("contextMatchType", "contains"),
                "caseSensitive": bool(matched_rule.get("caseSensitive", False)),
                "active": bool(overrides.get("active", True)),
                "isLinked": True,
                "shared": True,
                "sync": {
                    "revision": matched_rule.get("sync", {}).get("revision", 0),
                    "updatedAt": datetime.now(timezone.utc).isoformat(),
                    "updatedByProfileId": t_pid,
                    "operationId": str(uuid.uuid4()),
                    "memberProfileIds": sorted(list(set((matched_rule.get("sync", {}).get("memberProfileIds") or []) + [t_pid])))
                }
            }

            extra_modified = {}
            # Update memberProfileIds across all other instances
            for pname, doc in all_profs.items():
                if pname != target_profile:
                    modified = False
                    for r in doc.get("rules", []):
                        if r.get("ruleCode") == existing_rule_code:
                            s = r.setdefault("sync", {})
                            m = set(s.get("memberProfileIds", []))
                            if t_pid not in m:
                                m.add(t_pid)
                                s["memberProfileIds"] = sorted(list(m))
                                r["isLinked"] = True
                                r["shared"] = True
                                modified = True
                    if modified:
                        extra_modified[pname] = doc

            t_doc_updated = json.loads(json.dumps(t_doc))
            t_doc_updated.setdefault("rules", []).append(new_rule)
            return self.save_profile_config_result(
                target_profile,
                t_doc_updated,
                extra_modified_profiles=extra_modified
            )

    def unlink_rule(self, profile_name: str, rule_id: str) -> SaveResult:
        """Unlink rule by assigning fresh ruleCode while preserving local instance."""
        with ProfileCatalogLock(self.base_dir):
            all_profs = self.scan_all_profiles()
            doc = all_profs.get(profile_name)
            if not doc:
                return SaveResult(ok=False, code="PROFILE_NOT_FOUND", message=f"Profile '{profile_name}' not found")

            target_rule = None
            for r in doc.get("rules", []):
                if r.get("id") == rule_id:
                    target_rule = r
                    break
            if not target_rule:
                return SaveResult(ok=False, code="RULE_NOT_FOUND", message=f"Rule '{rule_id}' not found")

            old_code = target_rule.get("ruleCode")
            fresh_code = self.allocator.allocate_code()
            pid = doc.get("profileId")

            # Update target rule to independent code
            target_rule["ruleCode"] = fresh_code
            target_rule["isLinked"] = False
            target_rule["shared"] = False
            target_rule["sync"] = {
                "revision": 0,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "updatedByProfileId": pid,
                "operationId": str(uuid.uuid4()),
                "memberProfileIds": [pid]
            }

            extra_modified = {}
            # Update surviving instances of old_code in other profiles
            for pname, p_doc in all_profs.items():
                if pname == profile_name:
                    continue
                p_mod = False
                for r in p_doc.get("rules", []):
                    if r.get("ruleCode") == old_code:
                        s = r.setdefault("sync", {})
                        m = [m_id for m_id in s.get("memberProfileIds", []) if m_id != pid]
                        s["memberProfileIds"] = m
                        p_mod = True
                if p_mod:
                    extra_modified[pname] = p_doc

            return self.save_profile_config_result(
                profile_name,
                doc,
                extra_modified_profiles=extra_modified
            )

    def delete_rule(self, profile_name: str, rule_id: str, everywhere: bool = False) -> SaveResult:
        """Delete rule locally or across all linked profiles."""
        with ProfileCatalogLock(self.base_dir):
            all_profs = self.scan_all_profiles()
            doc = all_profs.get(profile_name)
            if not doc:
                return SaveResult(ok=False, code="PROFILE_NOT_FOUND", message=f"Profile '{profile_name}' not found")

            target_rule = None
            for r in doc.get("rules", []):
                if r.get("id") == rule_id:
                    target_rule = r
                    break
            if not target_rule:
                return SaveResult(ok=False, code="RULE_NOT_FOUND", message=f"Rule '{rule_id}' not found")

            code = target_rule.get("ruleCode")
            pid = doc.get("profileId")

            if everywhere:
                # Delete from all profiles
                changed = []
                for pname, p_doc in all_profs.items():
                    orig_len = len(p_doc.get("rules", []))
                    p_doc["rules"] = [r for r in p_doc.get("rules", []) if r.get("ruleCode") != code]
                    if len(p_doc.get("rules", [])) != orig_len:
                        p_doc["configRevision"] = p_doc.get("configRevision", 0) + 1
                        cfg_target = self.base_dir / pname / "config.json"
                        atomic_write_json(cfg_target, p_doc)
                        changed.append(pname)
                return SaveResult(
                    ok=True,
                    message=f"Rule '{code}' deleted everywhere",
                    changedProfiles=changed
                )
            else:
                # Delete locally and clean up memberships
                doc["rules"] = [r for r in doc.get("rules", []) if r.get("id") != rule_id]
                extra_modified = {}
                for pname, p_doc in all_profs.items():
                    if pname == profile_name:
                        continue
                    p_mod = False
                    for r in p_doc.get("rules", []):
                        if r.get("ruleCode") == code:
                            s = r.setdefault("sync", {})
                            m = [m_id for m_id in s.get("memberProfileIds", []) if m_id != pid]
                            s["memberProfileIds"] = m
                            p_mod = True
                    if p_mod:
                        extra_modified[pname] = p_doc

                return self.save_profile_config_result(
                    profile_name,
                    doc,
                    extra_modified_profiles=extra_modified
                )

    def repair_survivors_after_profile_removal(self, removed_pid: str, rule_codes: Set[str]):
        """Repair memberProfileIds and link flags after a profile directory is removed."""
        all_profs = self.scan_all_profiles()
        for pname, p_doc in all_profs.items():
            doc_modified = False
            for r in p_doc.get("rules", []):
                code = r.get("ruleCode")
                if code in rule_codes:
                    s = r.setdefault("sync", {})
                    m = s.get("memberProfileIds", [])
                    if removed_pid in m:
                        s["memberProfileIds"] = [x for x in m if x != removed_pid]
                        doc_modified = True
            if doc_modified:
                p_doc["configRevision"] = p_doc.get("configRevision", 0) + 1
                atomic_write_json(self.base_dir / pname / "config.json", p_doc)

    def admit_imported_profile(
        self,
        profile_name: str,
        collision_resolution: str = "link"
    ) -> Dict[str, Any]:
        """Admit an external or imported profile folder into the profile root."""
        with ProfileCatalogLock(self.base_dir):
            pdir = (self.base_dir / profile_name).resolve()
            cfg_path = pdir / "config.json"
            if not cfg_path.is_file():
                raise FileNotFoundError(f"Profile '{profile_name}' config.json not found")

            with open(cfg_path, "r", encoding="utf-8") as f:
                doc = json.load(f)

            # Check profileId collision across root
            all_profs = self.scan_all_profiles()
            pid = doc.get("profileId")
            pid_collided = False
            for pname, other_doc in all_profs.items():
                if pname != profile_name and other_doc.get("profileId") == pid:
                    pid_collided = True
                    break

            if pid_collided or not RuleSchemaValidator.is_valid_uuid(pid):
                pid = generate_profile_id()
                doc["profileId"] = pid

            # Check colliding rule codes
            external_code_members = {}
            for pname, other_doc in all_profs.items():
                if pname != profile_name:
                    for r in other_doc.get("rules", []):
                        c = r.get("ruleCode")
                        if c:
                            s = r.get("sync", {})
                            m_ids = set(s.get("memberProfileIds", []))
                            external_code_members.setdefault(c, set()).update(m_ids)

            re_coded = []
            linked = []
            for r in doc.get("rules", []):
                code = r.get("ruleCode")
                if code in external_code_members:
                    existing_members = external_code_members[code]
                    if pid not in existing_members:
                        if collision_resolution == "recode":
                            fresh = self.allocator.allocate_code()
                            r["ruleCode"] = fresh
                            r["isLinked"] = False
                            r["shared"] = False
                            r["sync"] = {
                                "revision": 0,
                                "updatedAt": datetime.now(timezone.utc).isoformat(),
                                "updatedByProfileId": pid,
                                "operationId": str(uuid.uuid4()),
                                "memberProfileIds": [pid]
                            }
                            re_coded.append(f"{code} -> {fresh}")
                        elif collision_resolution == "link":
                            s = r.setdefault("sync", {})
                            m = set(s.get("memberProfileIds", []))
                            m.add(pid)
                            m.update(existing_members)
                            s["memberProfileIds"] = sorted(list(m))
                            r["isLinked"] = True
                            r["shared"] = True
                            linked.append(code)

                            # Also add pid to existing rules in other profiles
                            for pname, other_doc in all_profs.items():
                                if pname != profile_name:
                                    p_mod = False
                                    for other_r in other_doc.get("rules", []):
                                        if other_r.get("ruleCode") == code:
                                            osync = other_r.setdefault("sync", {})
                                            om = set(osync.get("memberProfileIds", []))
                                            if pid not in om:
                                                om.add(pid)
                                                osync["memberProfileIds"] = sorted(list(om))
                                                p_mod = True
                                    if p_mod:
                                        other_doc["configRevision"] = other_doc.get("configRevision", 0) + 1
                                        atomic_write_json(self.base_dir / pname / "config.json", other_doc)

            doc["configRevision"] = doc.get("configRevision", 0) + 1
            atomic_write_json(cfg_path, doc)
            return {
                "profileName": profile_name,
                "profileId": pid,
                "reCodedRules": re_coded,
                "linkedRules": linked
            }


# ---------------------------------------------------------------------------
# Master ProfileManager Class
# ---------------------------------------------------------------------------
class ProfileManager:
    """Manages browser profiles, directory isolation, configuration, and locks."""

    def __init__(self, base_dir: Optional[Path] = None, sync_v2_enabled: Optional[bool] = None):
        if base_dir is not None:
            self.base_dir = Path(base_dir).resolve()
        else:
            self.base_dir = self.resolve_base_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Host-controlled feature gate default off
        if sync_v2_enabled is not None:
            self.sync_v2_enabled = bool(sync_v2_enabled)
        else:
            self.sync_v2_enabled = (os.environ.get("MBS_ENABLE_SYNC_V2") == "1")

        self.coordinator = ProfileSyncCoordinator(self.base_dir)
        self.migrator = RuleSchemaMigrator(self.base_dir)
        self.allocator = RuleCodeAllocator(self.base_dir)

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
            raise ValueError(f"Invalid profile name: '{name}'. Allowed: letters, Arabic characters, digits, underscores, hyphens, and spaces.")
        return stripped

    def is_valid_name(self, name: str) -> bool:
        """Return True if profile name is valid, False otherwise."""
        try:
            self.validate_name(name)
            return True
        except ValueError:
            return False

    def get_profile_dir(self, name: str) -> Path:
        sanitized = self.validate_name(name)
        return self.base_dir / sanitized

    def get_profile_config_path(self, name: str) -> Path:
        return self.get_profile_dir(name) / "config.json"

    def is_profile_locked(self, name: str) -> bool:
        """Check whether a profile has active browser locks."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return False

        lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
        for lfile in lock_files:
            p = pdir / lfile
            if p.is_symlink():
                try:
                    target = os.readlink(p)
                    if "-" in target:
                        pid_str = target.split("-")[-1]
                        if pid_str.isdigit():
                            pid = int(pid_str)
                            try:
                                os.kill(pid, 0)
                                return True
                            except OSError:
                                pass
                except Exception:
                    return True
            elif p.exists():
                return True
        return False

    def get_profile_lease(self, name: str) -> ProfileLease:
        """Return a ProfileLease instance for the specified profile."""
        return ProfileLease(self.get_profile_dir(name))

    def get_catalog_lock(self, timeout: float = 5.0) -> ProfileCatalogLock:
        """Return a ProfileCatalogLock instance for the profile root."""
        return ProfileCatalogLock(self.base_dir, timeout=timeout)

    def clean_stale_locks(self, name: str, is_leased: bool = False):
        """Clean up stale Chromium lock artifacts only when no other process holds an OS lease."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
            return
        if not is_leased:
            lease = ProfileLease(pdir)
            try:
                lease.acquire()
                lease.release()
            except RuntimeError:
                return
        lock_files = ["SingletonLock", "SingletonSocket", "SingletonCookie"]
        for lfile in lock_files:
            p = pdir / lfile
            try:
                if p.is_symlink() or p.exists():
                    p.unlink(missing_ok=True)
            except Exception:
                pass

    def list_profiles(self) -> List[Dict[str, Any]]:
        """Scan directory root and return profile descriptors with metadata."""
        profiles = []
        if not self.base_dir.exists():
            return profiles

        for item in sorted(self.base_dir.iterdir()):
            if item.is_dir():
                cfg_path = item / "config.json"
                has_cfg = cfg_path.is_file()
                rules_count = 0
                if has_cfg:
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            rules_count = len(data.get("rules", []))
                    except Exception:
                        rules_count = 0

                try:
                    stat_res = item.stat()
                    created_at = getattr(stat_res, "st_birthtime", stat_res.st_ctime)
                except Exception:
                    created_at = 0.0

                profiles.append({
                    "name": item.name,
                    "path": str(item.resolve()),
                    "has_config": has_cfg,
                    "rules_count": rules_count,
                    "created_at": created_at,
                    "is_locked": self.is_profile_locked(item.name)
                })
        return profiles

    def create_profile(self, name: str) -> Dict[str, Any]:
        """Create a new profile directory and seed its isolated default config.json."""
        sanitized = self.validate_name(name)
        pdir = self.base_dir / sanitized
        pdir.mkdir(parents=True, exist_ok=True)

        cfg_path = pdir / "config.json"
        if not cfg_path.is_file():
            seed = json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
            seed["profileId"] = generate_profile_id()
            seed["configRevision"] = 0
            self.save_profile_config(sanitized, seed)

        stat_res = pdir.stat()
        created_at = getattr(stat_res, "st_birthtime", stat_res.st_ctime)
        rules_count = len(self.get_profile_config(sanitized).get("rules", []))

        return {
            "name": sanitized,
            "path": str(pdir.resolve()),
            "has_config": True,
            "rules_count": rules_count,
            "created_at": created_at,
            "is_locked": False
        }

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Safely rename a profile folder under catalog lock."""
        old_sanitized = self.validate_name(old_name)
        new_sanitized = self.validate_name(new_name)

        old_dir = self.base_dir / old_sanitized
        new_dir = self.base_dir / new_sanitized

        with ProfileCatalogLock(self.base_dir):
            if not old_dir.exists():
                raise FileNotFoundError(f"Source profile '{old_name}' does not exist.")
            if new_dir.exists():
                raise FileExistsError(f"Destination profile '{new_name}' already exists.")
            if self.is_profile_locked(old_sanitized):
                raise RuntimeError(f"Cannot rename profile '{old_name}': Active browser lock detected.")

            old_dir.rename(new_dir)
            return True

    def delete_profile(self, name: str) -> bool:
        """Safely delete profile folder under catalog lock and repair surviving memberships."""
        sanitized = self.validate_name(name)
        pdir = self.base_dir / sanitized
        if not pdir.exists():
            return False

        with ProfileCatalogLock(self.base_dir):
            if self.is_profile_locked(sanitized):
                raise RuntimeError(f"Cannot delete profile '{name}': Active browser lock detected.")

            # Read configuration to capture memberships before deletion
            cfg_path = pdir / "config.json"
            rule_codes = set()
            removed_pid = None
            if cfg_path.is_file():
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    removed_pid = data.get("profileId")
                    for r in data.get("rules", []):
                        c = r.get("ruleCode")
                        if c:
                            rule_codes.add(c)
                except Exception:
                    pass

            shutil.rmtree(pdir)

            if removed_pid and rule_codes:
                self.coordinator.repair_survivors_after_profile_removal(removed_pid, rule_codes)

            return True

    def get_profile_config(self, name: str) -> Dict[str, Any]:
        """Read isolated config.json for a profile."""
        cfg_path = self.get_profile_config_path(name)
        if not cfg_path.is_file():
            return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
            if "rules" not in data or not isinstance(data["rules"], list):
                data["rules"] = []
            return data
        except Exception as e:
            raise RuntimeError(f"Failed to read config for profile '{name}': {e}")

    def save_profile_config(self, name: str, data: Dict[str, Any]) -> bool:
        """Persist configuration. If sync_v2_enabled is True, routes through coordinator."""
        if self.sync_v2_enabled:
            res = self.save_profile_config_result(name, data)
            return res.ok
        pdir = self.get_profile_dir(name)
        target_path = pdir / "config.json"
        return atomic_write_json(target_path, data)

    def save_profile_config_result(
        self,
        name: str,
        data: Dict[str, Any],
        expected_revision: Optional[int] = None,
        lease_authorities: Optional[List[LeaseAuthority]] = None
    ) -> SaveResult:
        """Coordinated save entry point returning structured SaveResult."""
        sanitized = self.validate_name(name)
        return self.coordinator.save_profile_config_result(
            sanitized,
            data,
            expected_revision=expected_revision,
            lease_authorities=lease_authorities
        )

    # -----------------------------------------------------------------------
    # Migration & Membership Services
    # -----------------------------------------------------------------------
    def migrate_profile(self, name: str, write_backup: bool = True) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Migrate a single profile to Schema V2 idempotently."""
        sanitized = self.validate_name(name)
        pdir = self.get_profile_dir(sanitized)
        cfg_data = self.get_profile_config(sanitized)
        with ProfileCatalogLock(self.base_dir):
            migrated, rep = self.migrator.migrate_profile_data(pdir, cfg_data, write_backup=write_backup)
            cfg_path = pdir / "config.json"
            atomic_write_json(cfg_path, migrated)
            return migrated, rep

    def migrate_all_profiles(self, write_backup: bool = True) -> Dict[str, Any]:
        """Migrate all profiles in profile root to Schema V2 under catalog lock."""
        with ProfileCatalogLock(self.base_dir):
            existing_codes = self.allocator.get_all_existing_codes()
            results = {}
            for item in sorted(self.base_dir.iterdir()):
                if item.is_dir():
                    cfg_path = item / "config.json"
                    if cfg_path.is_file():
                        try:
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            migrated, rep = self.migrator.migrate_profile_data(
                                item, data, existing_codes=existing_codes, write_backup=write_backup
                            )
                            atomic_write_json(cfg_path, migrated)
                            results[item.name] = rep
                        except Exception as e:
                            results[item.name] = {"error": str(e)}

            all_profs = self.coordinator.scan_all_profiles()
            self.coordinator.recompute_link_metadata(all_profs)
            for pname, doc in all_profs.items():
                atomic_write_json(self.base_dir / pname / "config.json", doc)

            return results

    def clone_rule(self, source_profile: str, target_profile: str, rule_id: str) -> SaveResult:
        return self.coordinator.clone_rule(
            self.validate_name(source_profile),
            self.validate_name(target_profile),
            rule_id
        )

    def link_rule_by_code(
        self,
        target_profile: str,
        existing_rule_code: str,
        draft_overrides: Optional[Dict[str, Any]] = None
    ) -> SaveResult:
        return self.coordinator.link_rule_by_code(
            self.validate_name(target_profile),
            existing_rule_code,
            draft_overrides
        )

    def unlink_rule(self, profile_name: str, rule_id: str) -> SaveResult:
        return self.coordinator.unlink_rule(
            self.validate_name(profile_name),
            rule_id
        )

    def delete_rule(self, profile_name: str, rule_id: str, everywhere: bool = False) -> SaveResult:
        return self.coordinator.delete_rule(
            self.validate_name(profile_name),
            rule_id,
            everywhere=everywhere
        )

    def admit_imported_profile(self, profile_name: str, collision_resolution: str = "link") -> Dict[str, Any]:
        return self.coordinator.admit_imported_profile(
            self.validate_name(profile_name),
            collision_resolution=collision_resolution
        )

    def reconcile_crash_recovery(self) -> Dict[str, Any]:
        return self.coordinator.reconcile_crash_recovery()

    def repair_survivors_after_profile_removal(self, removed_pid: str, rule_codes: Set[str]):
        return self.coordinator.repair_survivors_after_profile_removal(removed_pid, rule_codes)
