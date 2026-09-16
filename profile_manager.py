#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Suite Profile Manager Module (V6.3.7)
Provides thread-safe and process-isolated multi-tenant sandbox management.
"""

__author__ = "Bishoy Safwat"

import os
import re
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

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
        "monitoringInterval": 5000
    },
    "auto_start": False
}

NAME_REGEX = re.compile(r"^[a-zA-Z0-9_\u0600-\u06FF\s-]+$")

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

        os.replace(temp_path, path)

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
                    try:
                        self._file_obj.seek(0)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
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


class ProfileManager:
    """Manages browser profiles, directory isolation, configuration, and locks."""

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
                # Check if target PID is still alive on Unix
                try:
                    target = os.readlink(p)
                    # Format is hostname-pid
                    if "-" in target:
                        pid_str = target.split("-")[-1]
                        if pid_str.isdigit():
                            pid = int(pid_str)
                            try:
                                os.kill(pid, 0)
                                return True
                            except OSError:
                                # Process is dead, stale lock
                                pass
                except Exception:
                    return True
            elif p.exists():
                return True
        return False

    def get_profile_lease(self, name: str) -> ProfileLease:
        """Return a ProfileLease instance for the specified profile."""
        return ProfileLease(self.get_profile_dir(name))

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
                # Active OS lease held by another process: do NOT delete locks!
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
        """Safely rename a profile folder if not locked."""
        old_sanitized = self.validate_name(old_name)
        new_sanitized = self.validate_name(new_name)

        old_dir = self.base_dir / old_sanitized
        new_dir = self.base_dir / new_sanitized

        if not old_dir.exists():
            raise FileNotFoundError(f"Source profile '{old_name}' does not exist.")
        if new_dir.exists():
            raise FileExistsError(f"Destination profile '{new_name}' already exists.")
        if self.is_profile_locked(old_sanitized):
            raise RuntimeError(f"Cannot rename profile '{old_name}': Active browser lock detected.")

        old_dir.rename(new_dir)
        return True

    def delete_profile(self, name: str) -> bool:
        """Safely delete profile folder after verifying no active browser locks."""
        sanitized = self.validate_name(name)
        pdir = self.base_dir / sanitized
        if not pdir.exists():
            return False

        if self.is_profile_locked(sanitized):
            raise RuntimeError(f"Cannot delete profile '{name}': Active browser lock detected.")

        shutil.rmtree(pdir)
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
        """Persist configuration atomically with fsync and directory sync."""
        pdir = self.get_profile_dir(name)
        target_path = pdir / "config.json"
        return atomic_write_json(target_path, data)
