#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
Meta Business Suite Inbox Auto-Responder & Unread Restorer (V6.3.2 Enterprise Release)
Author: Bishoy Safwat (Senior Automation Engineer)
=============================================================================
Pure Python Zero-Extension Runner & Native Playwright Injector:
- Eliminates the need for Tampermonkey extension completely.
- Injects bot_script.js natively and persistently via Playwright's add_init_script.
- 3 Primary Operational Modes:
    1. Active Browser Attach (--attach / -a): Connects via CDP to running Chrome.
    2. Isolated Persistent Sandbox (--profile / -p [Name]): Sandboxed Chrome instance.
    3. Concurrent Multi-Tenant Dispatch (--all): Runs multiple isolated page profiles concurrently.
- Instant Zero-Latency Hard-Stop Engine (<10ms breakout).
- Dynamic Tenant Storage Isolation & Zero Cross-Talk.
- Continuous Runtime Anti-Throttling & V8 256MB Lean Memory Capping Architecture.
- Dedicated Standalone ProfileManager with Atomic JSON Persistence.
- Automatic Stale Chrome Lock Cleaning (SingletonLock/Cookie/Socket).
=============================================================================
"""

__author__ = "Bishoy Safwat"

import os
import sys
import json
import time
import signal
import shutil
import asyncio
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

from profile_manager import ProfileManager

telemetry_queue: Optional[asyncio.Queue] = None

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Page,
        Playwright,
        Error as PlaywrightError
    )
except ImportError:
    print("\n\033[91m❌ حزمة playwright غير مثبتة في بيئة بايثون الحالية!\033[0m")
    print("\033[93mيرجى تشغيل الأمر التالي لتثبيتها:\033[0m")
    print("pip install playwright --break-system-packages\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# ANSI Colors for Terminal Output
# ---------------------------------------------------------------------------
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    PURPLE = '\033[35m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# ---------------------------------------------------------------------------
# Global Constants & Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.json"
BOT_SCRIPT_PATH = SCRIPT_DIR / "bot_script.js"

META_INBOX_URL = "https://business.facebook.com/latest/inbox/all"

ANTI_THROTTLING_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=CalculateNativeWinOcclusion",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-breakpad",
    "--disable-component-update",
    "--password-store=basic",
    "--start-maximized",
    "--new-window",
    "--test-type",
]

LEAN_CHROMIUM_ARGS = [
    "--js-flags=--max-old-space-size=256",
    "--disable-background-networking",
    "--disable-renderer-backgrounding",
    "--disable-component-update",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-sync",
    "--disable-features=Translate,OptimizationHints,MediaRouter",
    "--renderer-process-limit=2",
]

# Combined hardened anti-throttling and V8 memory-capping flags
DEFAULT_CHROME_ARGS = list(dict.fromkeys(ANTI_THROTTLING_ARGS + LEAN_CHROMIUM_ARGS))

# Dedicated Profile Manager Instance
PROFILE_MGR = ProfileManager()

# Track active resources for clean signal exit
ACTIVE_CONTEXTS: List[BrowserContext] = []
ACTIVE_PAGES: List[Page] = []
ACTIVE_PROFILE_DIRS: List[Path] = []
SHUTDOWN_EVENT: asyncio.Event = asyncio.Event()

# ---------------------------------------------------------------------------
# Platform-Dependent Profile Resolution (Backed by ProfileManager)
# ---------------------------------------------------------------------------
def get_profiles_base_dir() -> Path:
    return PROFILE_MGR.base_dir

def get_tenant_profile_dir(profile_name: str) -> Path:
    return PROFILE_MGR.get_profile_dir(profile_name)

def get_profile_config_path(profile_name: str) -> Path:
    return PROFILE_MGR.get_profile_config_path(profile_name)

def clean_stale_locks(profile_dir: Path):
    """Safely remove leftover SingletonLock/SingletonCookie/SingletonSocket files."""
    if not profile_dir.exists():
        return
    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for lock in lock_files:
        p = profile_dir / lock
        try:
            if p.exists() or p.is_symlink():
                p.unlink(missing_ok=True)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Chrome Executable Discovery
# ---------------------------------------------------------------------------
def find_chrome_executable() -> Optional[str]:
    """Auto-detect system Google Chrome executable path."""
    if sys.platform.startswith("win"):
        candidates = [
            os.environ.get("ProgramFiles", "C:\\Program Files") + "\\Google\\Chrome\\Application\\chrome.exe",
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)") + "\\Google\\Chrome\\Application\\chrome.exe",
            os.environ.get("LocalAppData", "C:\\Users\\Default\\AppData\\Local") + "\\Google\\Chrome\\Application\\chrome.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
    else:
        candidates = [
            "google-chrome-stable",
            "google-chrome",
            "chromium-browser",
            "chromium",
        ]
        for bin_name in candidates:
            p = shutil.which(bin_name)
            if p:
                return p
    return None

# ---------------------------------------------------------------------------
# Configuration Management
# ---------------------------------------------------------------------------
def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        default_data = {
            "rules": [
                {
                    "id": "rule_price",
                    "keyword": "سعر,كام,بكام,اسعار,تكلفة,تفاصيل,التفاصيل",
                    "reply": "أهلاً بك! تفاصيل الأسعار والعروض متاحة لدينا الآن، يسعدنا تواصلك وسنوافيك بالتفاصيل فوراً.",
                    "matchType": "contains",
                    "active": True
                },
                {
                    "id": "rule_location",
                    "keyword": "مكان,عنوان,الفرع,لوكيشن,موقع,فين,عناوين",
                    "reply": "أهلاً بك! فرعنا متاح لخدمتك دائماً. يمكنك معرفة أقرب موقع والتواصل عبر الرابط أو الرسائل هنا.",
                    "matchType": "contains",
                    "active": True
                },
                {
                    "id": "rule_phone",
                    "keyword": "فون,تليفون,رقم,واتس,واتساب,موبايل",
                    "reply": "أهلاً بك! رقم خدمة العملاء والواتساب متاح لمساعدتك على مدار الساعة، تفضل بالاستفسار في أي وقت.",
                    "matchType": "contains",
                    "active": True
                }
            ],
            "config": {
                "minTypingSpeed": 35,
                "maxTypingSpeed": 65,
                "minCooldown": 1200,
                "maxCooldown": 2200,
                "scrollThread": False,
                "highlightRows": True,
                "monitoringInterval": 6000
            },
            "auto_start": False
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data

    with open(config_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception as e:
            print(f"{Colors.RED}❌ خطأ في قراءة ملف الإعدادات {config_path}: {e}{Colors.END}")
            sys.exit(1)

def save_config(config_path: Path, data: dict):
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{Colors.RED}❌ تعذر حفظ ملف الإعدادات: {e}{Colors.END}")

# ---------------------------------------------------------------------------
# Terminal Logging Helpers
# ---------------------------------------------------------------------------
def format_log(tag: str, msg: str, prefix: str = ""):
    timestamp = time.strftime("%H:%M:%S")
    tag_colors = {
        "INIT": Colors.GRAY,
        "SCAN": Colors.CYAN,
        "MATCH": f"{Colors.GREEN}{Colors.BOLD}",
        "UNREAD": Colors.YELLOW,
        "TYPING": Colors.PURPLE,
        "SCROLL": Colors.CYAN,
        "INFO": Colors.BLUE,
        "WARN": Colors.YELLOW,
        "ERROR": f"{Colors.RED}{Colors.BOLD}",
        "STOP": Colors.RED
    }
    color = tag_colors.get(tag, Colors.END)
    prefix_str = f"{Colors.BOLD}{prefix}{Colors.END} " if prefix else ""
    print(f"{Colors.GRAY}[{timestamp}]{Colors.END} {prefix_str}{color}[{tag}]{Colors.END} {msg}", flush=True)

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
=============================================================================
  أتمتة صندوق بريد Meta Business Suite & استعادة غير مقروء (V6.3.2 المؤسسي)
  Meta Business Suite Pure Python Zero-Extension Runner & Playwright Injector
============================================================================={Colors.END}
  • مشغل بايثون نقي ومستقل بالكامل بدون الحاجة لأي إضافات (Zero-Extension)
  • حقن أصلي دائم للمحرك البرمجي عبر Playwright context.add_init_script
  • دعم كامل لـ 3 أنماط تشغيل: الربط الحي (--attach)، بروفايل معزول (--profile)، أو متعدد (--all)
  • محرك إيقاف طوارئ فوري دون أي تأخير زمني (Instant Hard-Stop <10ms)
  • عزل تخزين الصفحات المتعددة ديناميكياً مع حماية كاملة من تداخل البيانات
  • بنية كبح الذاكرة الفائقة V8 256MB مع تقييد العمليات لتشغيل 5-10 بروفايلات متزامنة
  • تنظيف تلقائي لأقفال كروم التالفة (SingletonLocks) لمنع الإغلاق الصامت
  • واجهة تحكم Apple Prismatic Liquid Glass المتطورة مع إبراز كبسولي زجاجي سائل للمحادثات
=============================================================================
"""
    print(banner)

# ---------------------------------------------------------------------------
# Automation Engine Injection & IPC Bridge Setup
# ---------------------------------------------------------------------------
async def setup_page_bridges(
    page: Page,
    settings: dict,
    config_path: Path,
    tenant_name: str = "",
    event_queue: Optional[asyncio.Queue] = None
):
    """Expose Python bridge functions to the browser page."""
    prefix = f"[{tenant_name}]" if tenant_name else ""

    async def py_log_handler(tag, message):
        format_log(tag, message, prefix=prefix)

    async def py_update_stats_handler(stats):
        eval_c = stats.get("evaluated", 0)
        match_c = stats.get("matched", 0)
        unread_c = stats.get("unreadRestored", 0)
        skip_c = stats.get("skippedOutbound", 0)
        label = f"{prefix} " if prefix else ""
        sys.stdout.write(
            f"\r{label}{Colors.BOLD}📊 الإحصائيات:{Colors.END} [فحص: {eval_c}] | "
            f"[{Colors.GREEN}رد: {match_c}{Colors.END}] | "
            f"[{Colors.YELLOW}استعادة: {unread_c}{Colors.END}] | "
            f"[{Colors.PURPLE}مستبعد: {skip_c}{Colors.END}]  "
        )
        sys.stdout.flush()
        if event_queue is not None:
            try:
                await event_queue.put({
                    "type": "STATS",
                    "data": stats,
                    "profile_name": tenant_name,
                    "timestamp": time.time()
                })
            except Exception:
                pass

    async def py_save_config_handler(rules_json_str, config_json_str):
        try:
            updated_rules = json.loads(rules_json_str)
            updated_config = json.loads(config_json_str)
            settings["rules"] = updated_rules
            settings["config"] = updated_config
            save_config(config_path, settings)
            format_log("INFO", "تم حفظ وتحديث القواعد والإعدادات في config.json بنجاح.", prefix=prefix)
        except Exception as ex:
            format_log("WARN", f"تعذر تحديث ملف الإعدادات: {ex}", prefix=prefix)

    async def py_state_handler(status_text):
        format_log("INFO", f"حالة المحرك تغيرت إلى: {status_text}", prefix=prefix)
        if event_queue is not None:
            try:
                await event_queue.put({
                    "type": "STATE",
                    "data": {"status": status_text},
                    "profile_name": tenant_name,
                    "timestamp": time.time()
                })
            except Exception:
                pass

    async def py_telemetry_handler(source, payload_str):
        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
            t_type = payload.get("type", "UNKNOWN")
            t_data = payload.get("data")
            t_tenant = payload.get("tenantId", tenant_name or "default")
            payload["profile_name"] = tenant_name or t_tenant

            if event_queue is not None:
                await event_queue.put(payload)
            elif "telemetry_queue" in globals() and globals()["telemetry_queue"] is not None:
                await globals()["telemetry_queue"].put(payload)

            if t_type == "STATE":
                st = t_data.get("status") if isinstance(t_data, dict) else str(t_data)
                format_log("STATE", f"حالة المحرك (Telemetry): {st}", prefix=prefix)
        except Exception as ex:
            format_log("WARN", f"تعذر معالجة حزمة Telemetry: {ex}", prefix=prefix)

    for name, handler in [
        ("pyLog", py_log_handler),
        ("pyUpdateStats", py_update_stats_handler),
        ("pySaveConfig", py_save_config_handler),
        ("pyOnStateChange", py_state_handler)
    ]:
        try:
            await page.expose_function(name, handler)
        except Exception:
            # Function already exposed on this page session
            pass

    try:
        await page.expose_binding("pyEmitTelemetry", py_telemetry_handler)
    except Exception:
        # Binding already exposed on this page session
        pass

async def inject_hud_and_rules(
    page: Page,
    bot_js_code: str,
    settings: dict,
    prefix: str = "",
    headless_agent: bool = False
):
    """Inject the HUD and rules into an active page."""
    try:
        # Check if already loaded via add_init_script or prior injection
        is_already_loaded = await page.evaluate("""() => {
            return Boolean(
                window.__MBS_AUTOMATOR_V632_LOADED__ ||
                window.__MBS_AUTOMATOR_ORCHESTRATOR__ ||
                window.__MBS_AUTOMATOR_HUD__
            );
        }""")

        if is_already_loaded:
            # Script already mounted: refresh rules & config via in-page command without re-evaluating the full 146KB script
            await page.evaluate("""
                ({ rules, config, isHeadless }) => {
                    window.__INITIAL_RULES__ = rules;
                    window.__INITIAL_CONFIG__ = config;
                    if (isHeadless) {
                        window.__MBS_HEADLESS_MODE__ = true;
                    }
                    if (typeof window.__MBS_EXEC_COMMAND__ === 'function') {
                        window.__MBS_EXEC_COMMAND__('RELOAD_RULES', rules);
                        window.__MBS_EXEC_COMMAND__('UPDATE_CONFIG', config);
                    }
                }
            """, {"rules": settings.get("rules", []), "config": settings.get("config", {}), "isHeadless": headless_agent})

            if headless_agent:
                format_log("INIT", "✨ تم مزامنة قواعد محرك الأتمتة بنمط الوكيل الرأسي (Headless Agent Mode) بنجاح!", prefix=prefix)
            else:
                format_log("INIT", "✨ تم تحديث ومزامنة القواعد في المتصفح بنجاح!", prefix=prefix)
            return

        # Fresh injection: set initial configuration and evaluate script
        await page.evaluate("""
            ({ rules, config, isHeadless }) => {
                window.__INITIAL_RULES__ = rules;
                window.__INITIAL_CONFIG__ = config;
                if (isHeadless) {
                    window.__MBS_HEADLESS_MODE__ = true;
                }
            }
        """, {"rules": settings.get("rules", []), "config": settings.get("config", {}), "isHeadless": headless_agent})

        await page.evaluate(bot_js_code)
        if headless_agent:
            format_log("INIT", "✨ تم تشغيل محرك الأتمتة بنمط الوكيل الرأسي (Headless Agent Mode) بنجاح!", prefix=prefix)
        else:
            format_log("INIT", "✨ تم تثبيت واجهة التحكم التفاعلية (HUD) بنجاح في المتصفح!", prefix=prefix)
    except Exception as e:
        format_log("ERROR", f"❌ خطأ أثناء حقن محرك الأتمتة: {e}", prefix=prefix)

# ---------------------------------------------------------------------------
# Mode 1: Active Browser Attach (--attach / -a)
# ---------------------------------------------------------------------------
async def run_attach_mode(p: Playwright, port: int, settings: dict, config_path: Path, auto_start: bool):
    print(f"{Colors.CYAN}🚀 جاري الاتصال بمتصفح Chrome المفتوح عبر منفذ CDP {port}...{Colors.END}")

    try:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    except Exception as e:
        print(f"\n{Colors.RED}❌ تعذر الاتصال بالمتصفح عبر منفذ CDP {port}!{Colors.END}")
        print(f"{Colors.GRAY}التفاصيل: {e}{Colors.END}")
        print(f"\n{Colors.YELLOW}👉 تأكد من إغلاق Chrome تماماً ثم تشغيله مع تفعيل منفذ التحكم بالأمر التالي:{Colors.END}")
        if sys.platform.startswith("win"):
            print(f'{Colors.BOLD}chrome.exe --remote-debugging-port={port} --user-data-dir="%USERPROFILE%\\ChromeDevProfile"{Colors.END}\n')
        else:
            print(f'{Colors.BOLD}google-chrome --remote-debugging-port={port}{Colors.END}\n')
        return

    with open(BOT_SCRIPT_PATH, "r", encoding="utf-8") as f:
        bot_js_code = f.read()

    # Search for an open Meta Business Suite tab
    print(f"{Colors.GRAY}🔍 جاري البحث عن تبويب Meta Business Suite مفتوح...{Colors.END}")
    target_page = None
    target_context = None

    for context in browser.contexts:
        for page in context.pages:
            if "business.facebook.com" in page.url:
                target_page = page
                target_context = context
                break
        if target_page:
            break

    if not target_page:
        print(f"\n{Colors.YELLOW}⚠️ لم يتم العثور على تبويب Meta Business Suite مفتوح.{Colors.END}")
        print(f"{Colors.CYAN}🌐 جاري فتح صفحة الصندوق تلقائياً في المتصفح...{Colors.END}")
        inbox_target = META_INBOX_URL
        custom_inbox = settings.get("inboxUrl") or settings.get("config", {}).get("inboxUrl")
        if custom_inbox and isinstance(custom_inbox, str):
            custom_inbox_clean = custom_inbox.strip()
            if custom_inbox_clean.startswith("https://business.facebook.com") or custom_inbox_clean.startswith("https://web.facebook.com") or custom_inbox_clean.startswith("https://www.facebook.com"):
                inbox_target = custom_inbox_clean

        target_context = browser.contexts[0] if browser.contexts else await browser.new_context()
        target_page = await target_context.new_page()
        await target_page.goto(inbox_target)
        print(f"{Colors.GRAY}⏳ بانتظار تحميل الصفحة...{Colors.END}")
        try:
            await target_page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(2)

    # Register persistent init script on context so navigations/refreshes keep HUD
    try:
        await target_context.add_init_script(path=str(BOT_SCRIPT_PATH))
    except Exception:
        pass

    ACTIVE_PAGES.append(target_page)
    await target_page.bring_to_front()
    title = await target_page.title()
    print(f"{Colors.GREEN}✅ تم الاتصال بنجاح بصفحة: {title}{Colors.END}")
    print(f"{Colors.GRAY}🔗 رابط الصفحة: {target_page.url}{Colors.END}")

    await setup_page_bridges(target_page, settings, config_path)
    await inject_hud_and_rules(target_page, bot_js_code, settings)

    # Re-inject on navigation / refresh
    async def on_page_reloaded():
        try:
            await asyncio.sleep(1)
            await inject_hud_and_rules(target_page, bot_js_code, settings)
            if auto_start:
                await asyncio.sleep(0.5)
                await target_page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")
        except Exception:
            pass

    target_page.on("domcontentloaded", lambda: asyncio.create_task(on_page_reloaded()))

    if auto_start:
        print(f"{Colors.YELLOW}⚡ تفعيل بدء الأتمتة التلقائي...{Colors.END}")
        await asyncio.sleep(1)
        await target_page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")

    print(f"\n{Colors.BOLD}🔘 اضغط [Esc] داخل المتصفح أو [Ctrl+C] هنا للإيقاف الآمن في أي لحظة.{Colors.END}\n")

    while not SHUTDOWN_EVENT.is_set():
        if target_page.is_closed():
            print(f"\n{Colors.YELLOW}⚠️ تم إغلاق تبويب Meta Business Suite. جاري إنهاء البرنامج.{Colors.END}")
            break
        await asyncio.sleep(1)

# ---------------------------------------------------------------------------
# Mode 2 & 3: Isolated Sandboxed Profile Launch
# ---------------------------------------------------------------------------
async def launch_persistent_context_safe(
    p: Playwright,
    profile_dir: Path,
    headless: bool = False,
    tenant_name: str = ""
) -> BrowserContext:
    """Launch persistent Chrome context with anti-throttling & lean memory flags."""
    clean_stale_locks(profile_dir)
    ACTIVE_PROFILE_DIRS.append(profile_dir)

    prefix = f"[{tenant_name}]" if tenant_name else ""
    format_log("INIT", f"إطلاق المتصفح المعزول للملف: {profile_dir.name}", prefix=prefix)

    # 1. Try launching with channel="chrome"
    try:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=headless,
            args=DEFAULT_CHROME_ARGS,
            viewport=None,
            no_viewport=True,
        )
        ACTIVE_CONTEXTS.append(context)
        return context
    except Exception as ex_channel:
        format_log("WARN", f"تعذر الإطلاق عبر channel='chrome': {ex_channel}. محاولة البحث عن مسار Chrome...", prefix=prefix)

    # 2. Try auto-detecting Chrome binary path
    chrome_bin = find_chrome_executable()
    if chrome_bin:
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                executable_path=chrome_bin,
                headless=headless,
                args=DEFAULT_CHROME_ARGS,
                viewport=None,
                no_viewport=True,
            )
            ACTIVE_CONTEXTS.append(context)
            return context
        except Exception as ex_exec:
            format_log("ERROR", f"تعذر الإطلاق عبر المسار {chrome_bin}: {ex_exec}", prefix=prefix)

    # 3. Fallback to default chromium bundled with Playwright
    try:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=DEFAULT_CHROME_ARGS,
            viewport=None,
            no_viewport=True,
        )
        ACTIVE_CONTEXTS.append(context)
        return context
    except Exception as ex_default:
        format_log("ERROR", f"فشل إطلاق المتصفح بالكامل للملف {profile_dir.name}: {ex_default}", prefix=prefix)
        raise ex_default

async def run_tenant_worker(
    p: Playwright,
    profile_name: str,
    settings: dict,
    config_path: Path,
    auto_start: bool = False,
    headless: bool = False,
    headless_agent: bool = False,
    stop_event: Optional[asyncio.Event] = None,
    event_queue: Optional[asyncio.Queue] = None,
    controller: Optional["ProfileProcessController"] = None,
):
    """Run a single tenant inside an isolated persistent Playwright context with memory limits."""
    profile_dir = get_tenant_profile_dir(profile_name)
    prefix = f"[{profile_name}]"

    async def emit_host_log(tag: str, msg: str):
        format_log(tag, msg, prefix=prefix)
        if event_queue is not None:
            try:
                await event_queue.put({
                    "type": "LOG",
                    "data": {"tag": tag, "message": msg},
                    "profile_name": profile_name,
                    "timestamp": time.time()
                })
            except Exception:
                pass

    await emit_host_log("INIT", f"بدء تهيئة البروفايل: {profile_dir}")

    with open(BOT_SCRIPT_PATH, "r", encoding="utf-8") as f:
        bot_js_code = f.read()

    try:
        context = await launch_persistent_context_safe(
            p=p,
            profile_dir=profile_dir,
            headless=headless,
            tenant_name=profile_name
        )
        if controller:
            controller.contexts[profile_name] = context
            pid = controller.get_pid_for_profile(profile_name)
            controller.pids[profile_name] = pid
    except Exception as e:
        await emit_host_log("ERROR", f"تعذر بدء المتصفح للملف {profile_name}: {e}")
        return

    # If headless agent mode is enabled, set flag before scripts load
    if headless_agent:
        await context.add_init_script("window.__MBS_HEADLESS_MODE__ = true;")

    # Add native init script for permanent zero-extension execution
    await context.add_init_script(path=str(BOT_SCRIPT_PATH))

    page = context.pages[0] if context.pages else await context.new_page()
    ACTIVE_PAGES.append(page)
    if controller:
        controller.pages[profile_name] = page

    await setup_page_bridges(
        page,
        settings,
        config_path,
        tenant_name=profile_name,
        event_queue=event_queue
    )

    inbox_target = META_INBOX_URL
    custom_inbox = settings.get("inboxUrl") or settings.get("config", {}).get("inboxUrl")
    if custom_inbox and isinstance(custom_inbox, str):
        custom_inbox_clean = custom_inbox.strip()
        if custom_inbox_clean.startswith("https://business.facebook.com") or custom_inbox_clean.startswith("https://web.facebook.com") or custom_inbox_clean.startswith("https://www.facebook.com"):
            inbox_target = custom_inbox_clean

    await emit_host_log("INIT", f"فتح صفحة الصندوق: {inbox_target}")
    try:
        await page.goto(inbox_target, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        if not SHUTDOWN_EVENT.is_set():
            await emit_host_log("WARN", f"تنبيه أثناء تحميل الرابط: {e}")

    if SHUTDOWN_EVENT.is_set() or (stop_event and stop_event.is_set()) or page.is_closed():
        return

    await asyncio.sleep(2)
    if SHUTDOWN_EVENT.is_set() or (stop_event and stop_event.is_set()) or page.is_closed():
        return

    await inject_hud_and_rules(
        page,
        bot_js_code,
        settings,
        prefix=prefix,
        headless_agent=headless_agent
    )

    # Re-inject on navigation
    async def on_reloaded():
        try:
            await asyncio.sleep(1)
            await inject_hud_and_rules(
                page,
                bot_js_code,
                settings,
                prefix=prefix,
                headless_agent=headless_agent
            )
            if auto_start:
                await asyncio.sleep(0.5)
                await page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")
        except Exception:
            pass

    page.on("domcontentloaded", lambda: asyncio.create_task(on_reloaded()))

    if auto_start:
        await emit_host_log("INFO", "⚡ تفعيل بدء الأتمتة التلقائي...")
        await asyncio.sleep(1)
        await page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")

    await emit_host_log("INFO", "✅ جلسة المتصفح نشطة وتعمل 24/7.")
    await emit_host_log("START", "⚡ بدء تشغيل دورة الأتمتة تلقائياً...")
    try:
        await page.evaluate("""() => {
            if (typeof window.__MBS_EXEC_COMMAND__ === 'function') {
                window.__MBS_EXEC_COMMAND__('START');
            } else if (typeof window.__MBS_AUTOMATOR_START__ === 'function') {
                window.__MBS_AUTOMATOR_START__();
            }
        }""")
    except Exception as e:
        await emit_host_log("WARN", f"تعذر إرسال أمر البدء التلقائي: {e}")

    while not SHUTDOWN_EVENT.is_set() and not (stop_event and stop_event.is_set()):
        if page.is_closed():
            await emit_host_log("WARN", "تم إغلاق نافذة المتصفح بواسطة المشغل.")
            break
        await asyncio.sleep(1)

    try:
        if not page.is_closed():
            await page.evaluate("() => window.__MBS_AUTOMATOR_STOP__ && window.__MBS_AUTOMATOR_STOP__()")
        await context.close()
    except Exception:
        pass
    finally:
        clean_stale_locks(profile_dir)

# ---------------------------------------------------------------------------
# Asynchronous Multi-Worker Process & Telemetry Controller
# ---------------------------------------------------------------------------
class ProfileProcessController:
    """Controls multi-tenant profile workers, individual cancellation, and telemetry dispatch."""

    def __init__(self, playwright_instance: Optional[Playwright] = None):
        self.p = playwright_instance
        self.workers: Dict[str, asyncio.Task] = {}
        self.stop_events: Dict[str, asyncio.Event] = {}
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.pids: Dict[str, Optional[int]] = {}
        self.telemetry_queue: asyncio.Queue = asyncio.Queue()

    def set_playwright(self, p: Playwright):
        self.p = p

    def get_pid_for_profile(self, profile_name: str) -> Optional[int]:
        """Discover Chromium PID for profile via SingletonLock symlink or process check."""
        profile_dir = get_tenant_profile_dir(profile_name)
        lock_file = profile_dir / "SingletonLock"
        if lock_file.is_symlink():
            try:
                target = os.readlink(lock_file)
                if "-" in target:
                    pid_str = target.split("-")[-1]
                    if pid_str.isdigit():
                        return int(pid_str)
            except Exception:
                pass
        return None

    async def start_worker(
        self,
        profile_name: str,
        settings: dict,
        config_path: Path,
        auto_start: bool = False,
        headless: bool = False,
        headless_agent: bool = False,
    ) -> asyncio.Task:
        """Start an individual profile worker with its own cancellation event."""
        if profile_name in self.workers and not self.workers[profile_name].done():
            format_log("WARN", f"جلسة البروفايل {profile_name} تعمل بالفعل.")
            return self.workers[profile_name]

        stop_event = asyncio.Event()
        self.stop_events[profile_name] = stop_event

        async def worker_wrapper():
            try:
                await run_tenant_worker(
                    p=self.p,
                    profile_name=profile_name,
                    settings=settings,
                    config_path=config_path,
                    auto_start=auto_start,
                    headless=headless,
                    headless_agent=headless_agent,
                    stop_event=stop_event,
                    event_queue=self.telemetry_queue,
                    controller=self,
                )
            finally:
                self.workers.pop(profile_name, None)
                self.stop_events.pop(profile_name, None)
                self.contexts.pop(profile_name, None)
                self.pages.pop(profile_name, None)
                self.pids.pop(profile_name, None)

        task = asyncio.create_task(worker_wrapper(), name=f"worker_{profile_name}")
        self.workers[profile_name] = task
        return task

    async def stop_worker(self, profile_name: str) -> bool:
        """Signal an individual profile worker to stop gracefully without affecting other workers."""
        stop_event = self.stop_events.get(profile_name)
        if stop_event:
            format_log("STOP", f"إرسال إشارة التوقف للبروفايل: {profile_name}")
            stop_event.set()
            task = self.workers.get(profile_name)
            if task:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    task.cancel()
            return True
        return False

    async def stop_all(self):
        """Stop all active profile workers gracefully."""
        names = list(self.stop_events.keys())
        for name in names:
            await self.stop_worker(name)

    def list_active(self) -> List[Dict[str, Any]]:
        """Return list of active profile sessions and their process telemetry."""
        result = []
        for name, task in self.workers.items():
            pid = self.pids.get(name) or self.get_pid_for_profile(name)
            result.append({
                "profile_name": name,
                "pid": pid,
                "is_running": not task.done(),
                "has_page": name in self.pages and not self.pages[name].is_closed()
            })
        return result

PROCESS_CONTROLLER = ProfileProcessController()

# ---------------------------------------------------------------------------
# Graceful Shutdown Handler
# ---------------------------------------------------------------------------
async def perform_graceful_shutdown():
    """Stop automator on all pages, close contexts, and clean locks."""
    print(f"\n{Colors.YELLOW}⏹ جاري إيقاف الأتمتة وتنظيف الجلسات بأمان...{Colors.END}")
    SHUTDOWN_EVENT.set()

    for page in ACTIVE_PAGES:
        try:
            if not page.is_closed():
                await page.evaluate("() => window.__MBS_AUTOMATOR_STOP__ && window.__MBS_AUTOMATOR_STOP__()")
        except Exception:
            pass

    for ctx in ACTIVE_CONTEXTS:
        try:
            await ctx.close()
        except Exception:
            pass

    for pdir in ACTIVE_PROFILE_DIRS:
        clean_stale_locks(pdir)

    print(f"{Colors.GREEN}✅ تم إيقاف كافة العمليات وتنظيف أقفال كروم بنجاح.{Colors.END}")

# ---------------------------------------------------------------------------
# Main Supervisor Entrypoint
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description="Meta Business Suite Inbox Automator & Unread Restorer (Pure Python Zero-Extension Runner V6.3.2)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--attach", "-a",
        action="store_true",
        help="Mode 1: Connect via CDP to an already running Google Chrome instance"
    )
    group.add_argument(
        "--profile", "-p",
        type=str,
        help="Mode 2: Launch a single isolated sandboxed profile (e.g. Profile_PageA)"
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Mode 3: Launch concurrent multi-tenant sandboxes (Profile_PageA & Profile_PageB)"
    )

    parser.add_argument("--port", type=int, default=9222, help="Chrome Remote Debugging Port for --attach (default: 9222)")
    parser.add_argument("--config", type=str, default=None, help="Explicit path to config.json file (overrides profile-scoped default)")
    parser.add_argument("--auto-start", action="store_true", help="Start automator immediately without waiting for HUD button")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (for background servers)")
    parser.add_argument("--headless-agent", action="store_true", help="Run in headless agent mode (remote HUD via telemetry)")

    args = parser.parse_args()

    print_banner()

    explicit_config = Path(args.config) if args.config else None

    if not BOT_SCRIPT_PATH.exists():
        print(f"{Colors.RED}❌ ملف المحرك البرمجي {BOT_SCRIPT_PATH} غير موجود!{Colors.END}")
        return

    # Signal handlers for clean interruption
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(perform_graceful_shutdown()))
        except (NotImplementedError, RuntimeError):
            # Windows signal handling fallback
            pass

    async with async_playwright() as p:
        PROCESS_CONTROLLER.set_playwright(p)
        try:
            if args.attach:
                # Mode 1: Active Browser Attach
                config_path = explicit_config or DEFAULT_CONFIG_PATH
                settings = load_config(config_path)
                auto_start = args.auto_start or settings.get("auto_start", False)
                await run_attach_mode(
                    p=p,
                    port=args.port,
                    settings=settings,
                    config_path=config_path,
                    auto_start=auto_start
                )
            elif args.profile:
                # Mode 2: Single Isolated Profile Sandbox
                config_path = explicit_config or get_profile_config_path(args.profile)
                settings = load_config(config_path)
                auto_start = args.auto_start or settings.get("auto_start", False)
                await run_tenant_worker(
                    p=p,
                    profile_name=args.profile,
                    settings=settings,
                    config_path=config_path,
                    auto_start=auto_start,
                    headless=args.headless,
                    headless_agent=args.headless_agent,
                    controller=PROCESS_CONTROLLER
                )
            else:
                # Mode 3 (Default or --all): Concurrent Multi-Tenant Dispatch
                print(f"{Colors.CYAN}👥 إطلاق وضبط البروفايلات المعزولة لكافة الصفحات بالتزامن (Multi-Tenant)...{Colors.END}")
                print(f"{Colors.GRAY}مسار البروفايلات: {get_profiles_base_dir()}{Colors.END}\n")

                tenants = ["Profile_PageA", "Profile_PageB"]
                tasks = []
                for t in tenants:
                    t_config_path = explicit_config or get_profile_config_path(t)
                    t_settings = load_config(t_config_path)
                    t_auto_start = args.auto_start or t_settings.get("auto_start", False)
                    tasks.append(
                        run_tenant_worker(
                            p=p,
                            profile_name=t,
                            settings=t_settings,
                            config_path=t_config_path,
                            auto_start=t_auto_start,
                            headless=args.headless,
                            headless_agent=args.headless_agent,
                            controller=PROCESS_CONTROLLER
                        )
                    )
                await asyncio.gather(*tasks, return_exceptions=True)

        except (asyncio.CancelledError, KeyboardInterrupt):
            await perform_graceful_shutdown()
        except Exception as e:
            if not SHUTDOWN_EVENT.is_set():
                print(f"{Colors.RED}❌ حدث خطأ غير متوقع: {e}{Colors.END}")
                await perform_graceful_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
