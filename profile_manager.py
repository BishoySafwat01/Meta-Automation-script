#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Suite Profile Manager Module (V5.6.0)
Provides thread-safe and process-isolated multi-tenant sandbox management.
"""

import os
import re
import sys
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_TEMPLATE_CONFIG: Dict[str, Any] = {
    "rules": [
        {
            "id": "rule_price",
            "keyword": "سعر,كام,بكام,اسعار,تكلفة,تفاصيل,التفاصيل",
            "reply": "أهلاً بك!  \nممكن تعرفنا مكان حضرتك بالظبط عشان نقولك السعر شامل الشحن ",
            "matchType": "contains",
            "active": True
        },
        {
            "id": "rule_location",
            "keyword": "مكان,عنوان,الفرع,لوكيشن,موقع,فين,عناوين",
            "reply": " فرعنا الرئيسي : https://www.google.com/maps/place/Khlfawy's+metro+station/@30.0972335,31.248073,17z/data=!3m1!4b1!4m6!3m5!1s0x145840140800dc0d:0x208945e92503b0db!8m2!3d30.0972289!4d31.2454981!16s%2Fg%2F11d_1pmqhw?entry=ttu&g_ep=EgoyMDI2MDkwOS4wIKXMDSoASAFQAw%3D%3D\n متاح لخدمتك دائماً. يمكنك معرفة أقرب موقع والتواصل عبر الرابط أو الرسائل هنا.",
            "matchType": "contains",
            "active": True
        },
        {
            "id": "rule_phone",
            "keyword": "فون,تليفون,رقم,واتس,واتساب,موبايل",
            "reply": "أهلاً بك! \nرقم خدمة العملاء والواتساب متاح لمساعدتك \n01119648815\nتفضل بالاستفسار في أي وقت.",
            "matchType": "contains",
            "active": True
        },
        {
            "id": "rule_1789360636812",
            "keyword": "روج",
            "reply": "اهلا بيكي \nتعرفي ان عندنا روج لوكسيرا افضل احمر شفاه ممكن تستعمليه\n وحاليا نازل بعرض مايتفوتش ب350 ج بس متخيله !\n الحقي العرض بسرعه ",
            "matchType": "contains",
            "active": True
        }
    ],
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

    def clean_stale_locks(self, name: str):
        """Clean up stale Chromium lock artifacts if browser is not actively running."""
        pdir = self.get_profile_dir(name)
        if not pdir.exists():
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
            seed = DEFAULT_TEMPLATE_CONFIG
            script_cfg = Path(__file__).resolve().parent / "config.json"
            if script_cfg.is_file():
                try:
                    with open(script_cfg, "r", encoding="utf-8") as f:
                        seed = json.load(f)
                except Exception:
                    pass
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
            return {}
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to read config for profile '{name}': {e}")

    def save_profile_config(self, name: str, data: Dict[str, Any]) -> bool:
        """Persist configuration atomically (temp file write + atomic rename)."""
        pdir = self.get_profile_dir(name)
        pdir.mkdir(parents=True, exist_ok=True)
        target_path = pdir / "config.json"

        temp_fd, temp_path = tempfile.mkstemp(dir=pdir, prefix="config_tmp_", suffix=".json")
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, target_path)
            return True
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise RuntimeError(f"Failed to atomically save config for profile '{name}': {e}")
