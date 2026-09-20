#!/usr/bin/env python3
"""
Meta Business Suite Inbox Automator & Desktop Hub
===============================================================================
Apple Prismatic Glass Desktop Hub via pywebview (V6.5.3-ENTERPRISE)
Architecture:
- Native desktop shell hosting Apple Prismatic Glass GUI (gui/index.html)
- DesktopBridgeApi exposed to JavaScript
- Dedicated asyncio background thread hosting Playwright & ProfileProcessController
- Thread-safe coroutine execution via asyncio.run_coroutine_threadsafe
- Real-time telemetry forwarding from ProfileProcessController.telemetry_queue
===============================================================================
"""

__author__ = "Bishoy Safwat"

import sys
import os
import json
import time
import asyncio
import threading
import argparse
import warnings
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    import webview
except ImportError:
    webview = None

from profile_manager import ProfileManager
from main import (
    PROCESS_CONTROLLER,
    PROFILE_MGR,
    ProfileProcessController,
    SHUTDOWN_EVENT,
    DEFAULT_CONFIG_PATH
)
from playwright.async_api import async_playwright, Playwright

# Base directories
BASE_DIR = Path(__file__).resolve().parent
GUI_DIR = BASE_DIR / "gui"
INDEX_HTML = GUI_DIR / "index.html"


class DesktopBridgeApi:
    """Synchronous API exposed to JavaScript in pywebview."""

    def __init__(
        self,
        profile_manager: Optional[ProfileManager] = None,
        controller: Optional[ProfileProcessController] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        window=None
    ):
        self.pm = profile_manager or PROFILE_MGR
        self.controller = controller or PROCESS_CONTROLLER
        self.loop = loop
        self.window = window

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    def set_window(self, window):
        self.window = window

    def _run_async(self, coro, timeout: float = 15.0):
        """Helper to run a coroutine on the background event loop safely."""
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("Background asyncio loop is not running.")
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    # -------------------------------------------------------------------------
    # Profile CRUD & Metadata
    # -------------------------------------------------------------------------
    def get_profiles(self) -> List[Dict[str, Any]]:
        """List all profiles enriched with real-time process execution status."""
        profiles = self.pm.list_profiles()
        active_map = {}
        if self.controller:
            for item in self.controller.list_active():
                active_map[item["profile_name"]] = item

        for prof in profiles:
            name = prof["name"]
            is_active = name in active_map and active_map[name]["is_running"]
            prof["status"] = "RUNNING" if is_active else "STOPPED"
            prof["pid"] = active_map.get(name, {}).get("pid")
        return profiles

    def create_profile(self, name: str) -> Dict[str, Any]:
        """Create a new profile with atomic configuration seeding."""
        res = self.pm.create_profile(name)
        res["status"] = "STOPPED"
        return res

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """Rename an existing profile, stopping any running worker first."""
        if self.is_worker_running(old_name):
            self.stop_profile(old_name)
        return self.pm.rename_profile(old_name, new_name)

    def delete_profile(self, name: str) -> bool:
        """Delete a profile and its files, stopping worker first if running."""
        if self.is_worker_running(name):
            self.stop_profile(name)
        return self.pm.delete_profile(name)

    def get_profile_config(self, profile_name: str) -> Dict[str, Any]:
        """Retrieve isolated config.json for profile."""
        return self.pm.get_profile_config(profile_name)

    def load_profile_config_result(self, profile_name: str) -> Dict[str, Any]:
        """Retrieve isolated config.json envelope with read_status, rules_count, sha256_token."""
        return self.pm.load_profile_config_result(profile_name)

    def allocate_rule_metadata(self, profile_name: Optional[str] = None) -> Dict[str, str]:
        """Allocate unique canonical id and Crockford Base32 ruleCode."""
        return self.pm.allocate_rule_metadata(profile_name)

    def unlink_rule(self, profile_name: str, rule_id: str) -> Dict[str, Any]:
        """Unlink a shared rule by assigning a fresh independent ruleCode locally."""
        res = self.pm.unlink_rule(profile_name, rule_id)
        if res.get("ok"):
            res["disk_ok"] = True
            succ, fails = self._dispatch_rule_snapshots([profile_name])
            res["runtime_refresh_successes"] = succ
            res["runtime_refresh_failures"] = fails
        else:
            res["disk_ok"] = False
            res["runtime_refresh_successes"] = []
            res["runtime_refresh_failures"] = {}
        return res

    def get_linked_rules_map(self) -> Dict[str, int]:
        """Return mapping of ruleCode to profile count."""
        return self.pm.get_linked_rule_counts()

    def save_profile_config(
        self,
        profile_name: str,
        data: Dict[str, Any],
        expected_sha: Optional[str] = None,
        expected_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deprecated: Use save_profile_config_coordinated instead.
        In V6.5.3, tokenless saves are strictly prohibited. Callers must supply expected_sha."""
        warnings.warn(
            "save_profile_config is deprecated in V6.5.3; use save_profile_config_coordinated instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        token = expected_sha or expected_sha256
        if not token:
            return {
                "ok": False,
                "disk_ok": False,
                "code": "MISSING_CONCURRENCY_TOKEN",
                "message": "Tokenless save is prohibited",
            }
        return self.save_profile_config_coordinated(profile_name, data, expected_sha256=token)

    def save_profile_config_coordinated(
        self,
        profile_name: str,
        data: Dict[str, Any],
        expected_sha256: Optional[str] = None,
        link_resolution: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Atomically persist configuration with concurrency check, peer propagation, and snapshot dispatch."""
        res = self.pm.save_profile_config_coordinated(
            profile_name, data, expected_sha256=expected_sha256, link_resolution=link_resolution
        )
        if res.get("ok"):
            res["disk_ok"] = True
            succ, fails = self._dispatch_runtime_refresh(
                res.get("modified_profiles", []),
                target_profile=profile_name,
                config_payload=data.get("config"),
            )
            res["runtime_refresh_successes"] = succ
            res["runtime_refresh_failures"] = fails
        else:
            res["disk_ok"] = False
            res["runtime_refresh_successes"] = []
            res["runtime_refresh_failures"] = {}
        return res

    def _dispatch_runtime_refresh(
        self,
        modified_profiles: List[str],
        target_profile: Optional[str] = None,
        config_payload: Optional[Any] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """Dispatches runtime refresh commands to active workers of modified profiles.
        - APPLY_RULE_SNAPSHOT is dispatched to all active workers of modified profiles with { rules, sha256_token }.
        - RELOAD_CONFIG is dispatched to target_profile if config_payload is provided.
        Returns (successes, failures)."""
        successes: List[str] = []
        failures: Dict[str, str] = {}
        for prof_name in modified_profiles:
            if self.is_worker_running(prof_name):
                try:
                    cfg_res = self.pm.load_profile_config_result(prof_name)
                    rules = cfg_res.get("data", {}).get("rules", []) if cfg_res.get("ok") else []
                    sha = cfg_res.get("sha256_token")
                    payload = {"rules": rules, "sha256_token": sha}
                    sent_snap = self.send_page_command(prof_name, "APPLY_RULE_SNAPSHOT", payload)
                    if not sent_snap:
                        failures[prof_name] = "فشل إرسال لقطة القواعد إلى صفحة المتصفح."
                        continue

                    if prof_name == target_profile and config_payload is not None:
                        sent_cfg = self.send_page_command(prof_name, "RELOAD_CONFIG", config_payload)
                        if not sent_cfg:
                            failures[prof_name] = "فشل تحديث إعدادات الأتمتة في صفحة المتصفح."
                            continue

                    successes.append(prof_name)
                except Exception as e:
                    failures[prof_name] = str(e)
                    print(f"[DesktopBridgeApi] Failed to dispatch runtime refresh to '{prof_name}': {e}")
        return successes, failures

    def _dispatch_rule_snapshots(self, modified_profiles: List[str]) -> Tuple[List[str], Dict[str, str]]:
        """Backward-compatible wrapper for runtime refresh dispatch."""
        return self._dispatch_runtime_refresh(modified_profiles)

    def import_rules_from_profile(
        self,
        target_profile: str,
        source_profile: str,
        rule_ids: List[str],
        mode: str = "clone",
        target_sha: Optional[str] = None,
        expected_target_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synchronously import rules into target profile using 'clone' or 'link' mode."""
        token = target_sha or expected_target_sha256
        if not token:
            return {
                "ok": False,
                "disk_ok": False,
                "code": "MISSING_CONCURRENCY_TOKEN",
                "message": "Target concurrency token is required",
            }
        res = self.pm.import_rules_from_profile(
            target_profile, source_profile, rule_ids, mode=mode, target_sha=token
        )
        if res.get("ok"):
            res["disk_ok"] = True
            succ, fails = self._dispatch_runtime_refresh([target_profile])
            res["runtime_refresh_successes"] = succ
            res["runtime_refresh_failures"] = fails
        else:
            res["disk_ok"] = False
            res["runtime_refresh_successes"] = []
            res["runtime_refresh_failures"] = {}
        return res

    def resolve_link_conflict(
        self,
        conflicting_code: str,
        authoritative_profile: str,
        expected_shas: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Resolves a link conflict across all participating profiles by adopting the authoritative profile's rule."""
        res = self.pm.resolve_link_conflict(conflicting_code, authoritative_profile, expected_shas=expected_shas)
        if res.get("ok"):
            res["disk_ok"] = True
            succ, fails = self._dispatch_runtime_refresh(res.get("modified_profiles", []))
            res["runtime_refresh_successes"] = succ
            res["runtime_refresh_failures"] = fails
        else:
            res["disk_ok"] = False
            res["runtime_refresh_successes"] = []
            res["runtime_refresh_failures"] = {}
        return res

    # -------------------------------------------------------------------------
    # Worker Lifecycle Management
    # -------------------------------------------------------------------------
    def is_worker_running(self, profile_name: str) -> bool:
        """Check if worker for profile is actively running."""
        if not self.controller:
            return False
        return (
            profile_name in self.controller.workers
            and not self.controller.workers[profile_name].done()
        )

    def get_worker_statuses(self) -> Dict[str, str]:
        """Return execution status dictionary for all known profiles."""
        profiles = self.pm.list_profiles()
        statuses = {}
        for p in profiles:
            name = p["name"]
            statuses[name] = "RUNNING" if self.is_worker_running(name) else "STOPPED"
        return statuses

    def start_profile(self, profile_name: str, headless: bool = False) -> Dict[str, Any]:
        """Launch Chromium worker for profile in visible agent mode."""
        if self.is_worker_running(profile_name):
            return {"status": "ALREADY_RUNNING", "profile_name": profile_name}

        cfg_path = self.pm.get_profile_config_path(profile_name)
        settings = self.pm.get_profile_config(profile_name)
        auto_start = settings.get("auto_start", False)

        async def _start():
            task = await self.controller.start_worker(
                profile_name=profile_name,
                settings=settings,
                config_path=cfg_path,
                auto_start=auto_start,
                headless=headless,
                headless_agent=True,
            )
            return task is not None

        try:
            started = self._run_async(_start(), timeout=10.0)
            return {
                "status": "STARTED" if started else "FAILED",
                "profile_name": profile_name
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "profile_name": profile_name,
                "error": str(e)
            }

    def stop_profile(self, profile_name: str) -> Dict[str, Any]:
        """Gracefully signal and stop a profile worker."""
        if not self.is_worker_running(profile_name):
            return {"status": "NOT_RUNNING", "profile_name": profile_name}

        async def _stop():
            return await self.controller.stop_worker(profile_name)

        try:
            stopped = self._run_async(_stop(), timeout=10.0)
            return {
                "status": "STOPPED" if stopped else "FAILED",
                "profile_name": profile_name
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "profile_name": profile_name,
                "error": str(e)
            }

    def send_page_command(self, profile_name: str, command: str, payload: Any = None) -> bool:
        """Dispatch runtime command to target profile's active page via __MBS_EXEC_COMMAND__."""
        if not self.controller:
            return False

        page = self.controller.pages.get(profile_name)
        if not page or page.is_closed():
            return False

        async def _exec():
            try:
                js = f"""() => {{
                    if (typeof window.__MBS_EXEC_COMMAND__ === 'function') {{
                        return window.__MBS_EXEC_COMMAND__({json.dumps(command)}, {json.dumps(payload)});
                    }}
                    if ({json.dumps(command)} === 'START' && typeof window.__MBS_AUTOMATOR_START__ === 'function') {{
                        return window.__MBS_AUTOMATOR_START__();
                    }}
                    if ({json.dumps(command)} === 'STOP' && typeof window.__MBS_AUTOMATOR_STOP__ === 'function') {{
                        return window.__MBS_AUTOMATOR_STOP__();
                    }}
                    return false;
                }}"""
                return await page.evaluate(js)
            except Exception as e:
                print(f"[DesktopBridgeApi] Failed to send command '{command}' to '{profile_name}': {e}")
                return False

        try:
            return bool(self._run_async(_exec(), timeout=5.0))
        except Exception:
            return False

    def start_all_profiles(self) -> Dict[str, Any]:
        """Start all configured profiles concurrently."""
        profiles = self.pm.list_profiles()
        results = {}
        for p in profiles:
            name = p["name"]
            if not self.is_worker_running(name):
                results[name] = self.start_profile(name)
            else:
                results[name] = {"status": "ALREADY_RUNNING", "profile_name": name}
        return results

    def stop_all_profiles(self) -> Dict[str, Any]:
        """Gracefully stop all currently active profile workers."""
        async def _stop_all():
            await self.controller.stop_all()

        try:
            self._run_async(_stop_all(), timeout=15.0)
            return {"status": "ALL_STOPPED"}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}


# -----------------------------------------------------------------------------
# Background Async Engine Thread
# -----------------------------------------------------------------------------
class BackgroundEngine:
    """Manages the background asyncio event loop, Playwright instance, and telemetry queue."""

    def __init__(self, api: DesktopBridgeApi):
        self.api = api
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.ready_event = threading.Event()
        self.shutdown_event = asyncio.Event()
        self.window_ref: List[Any] = [None]

    def set_window(self, window):
        self.window_ref[0] = window
        self.api.set_window(window)

    def start(self):
        self.thread = threading.Thread(target=self._run_loop, name="MBS_AsyncEngine", daemon=True)
        self.thread.start()
        # Wait up to 10 seconds for loop & Playwright readiness
        self.ready_event.wait(timeout=10.0)

    def stop(self):
        if self.loop and self.loop.is_running():
            def _signal():
                self.shutdown_event.set()
                SHUTDOWN_EVENT.set()
            self.loop.call_soon_threadsafe(_signal)

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.api.set_loop(self.loop)

        async def _main_worker():
            async with async_playwright() as p:
                self.api.controller.set_playwright(p)
                self.ready_event.set()

                # Start telemetry forwarding task
                telemetry_task = asyncio.create_task(
                    self._telemetry_forwarder()
                )

                while not self.shutdown_event.is_set():
                    await asyncio.sleep(0.5)

                telemetry_task.cancel()
                try:
                    await self.api.controller.stop_all()
                except Exception:
                    pass

        try:
            self.loop.run_until_complete(_main_worker())
        except Exception as e:
            print(f"[DesktopEngine] Async loop terminated: {e}")
        finally:
            self.loop.close()

    async def _telemetry_forwarder(self):
        """Continuously forwards telemetry events from queue to webview window."""
        while not self.shutdown_event.is_set():
            try:
                try:
                    event = await asyncio.wait_for(
                        self.api.controller.telemetry_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                window = self.window_ref[0]
                if window:
                    try:
                        payload_json = json.dumps(event, ensure_ascii=False)
                        await self.loop.run_in_executor(
                            None,
                            window.evaluate_js,
                            f"window.__RECEIVE_TELEMETRY__ && window.__RECEIVE_TELEMETRY__({payload_json});"
                        )
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.1)


# -----------------------------------------------------------------------------
# Desktop Application Main Entrypoint
# -----------------------------------------------------------------------------
def run_desktop_app(dev_tools: bool = False):
    """Launch pywebview desktop application window with Apple Prismatic Glass UI."""
    if webview is None:
        print("❌ pywebview is not installed. Please run: pip install pywebview")
        sys.exit(1)

    if not INDEX_HTML.is_file():
        print(f"❌ UI file not found: {INDEX_HTML}")
        sys.exit(1)

    api = DesktopBridgeApi()
    if not api.pm.ownership_guard.acquire():
        print(f"❌ ROOT_OWNERSHIP_COLLISION: Another desktop instance is active on profile root: {api.pm.base_dir}")
        sys.exit(1)

    engine = BackgroundEngine(api)
    engine.start()

    window = webview.create_window(
        title="Meta Automation Hub - Apple Prismatic Glass Edition (V6.5.3-ENTERPRISE)",
        url=str(INDEX_HTML.resolve()),
        js_api=api,
        width=1180,
        height=780,
        min_size=(960, 680),
        background_color="#0f172a",
        text_select=True,
    )
    engine.set_window(window)

    try:
        webview.start(debug=dev_tools)
    finally:
        api.pm.ownership_guard.release()
        engine.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Meta Automation Hub - Apple Prismatic Glass Edition Desktop (V6.5.3-ENTERPRISE)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable webview developer tools / inspect")
    parser.add_argument("--test-api", action="store_true", help="Run self-diagnostic test on API bridge without opening window")
    args = parser.parse_args()

    if args.test_api:
        print("Testing DesktopBridgeApi functionality...")
        api = DesktopBridgeApi()
        profiles = api.get_profiles()
        print(f"✅ Bridge API initialized. Found {len(profiles)} profiles.")
        sys.exit(0)

    run_desktop_app(dev_tools=args.debug)


if __name__ == "__main__":
    main()
