#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
⚡ Meta Business Suite Inbox Auto-Responder & Unread Restorer (V4.4 Python Runner)
=============================================================================
Architecture & Features:
- Connects to active Google Chrome via Chrome DevTools Protocol (CDP port 9222).
- Injects a complete Glassmorphism RTL Arabic HUD directly into Meta Business Suite.
- Dynamic First-Unhandled Queue Traversal (eliminates index-shift drift bug).
- Expanded Envelope (✉) Locator (top < 380 + Done Sibling fallback + Toolbar fallback).
- Inbound Boundary Parsing (strictly evaluates incoming customer messages after last agent reply).
- Visual Inspection & Framing (Sky-blue active row, green dashed customer bubble, flashing envelope).
- Complete Arabic Text Normalization & Keyword Matching (exact, word, contains).
- Full Two-Way Synchronization between the browser HUD and config.json.
- Graceful stop via browser [Escape] key, HUD Stop button, or terminal [Ctrl+C].
=============================================================================
"""

import os
import sys
import json
import time
import signal
import argparse
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("\n\033[91m❌ حزمة playwright غير مثبتة في بيئة بايثون الحالية!\033[0m")
    print("\033[93mيرجى تشغيل الأمر التالي لتثبيتها:\033[0m")
    print("pip install playwright --break-system-packages\n")
    sys.exit(1)

# ANSI Colors for Terminal Output
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

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR / "config.json"
BOT_SCRIPT_PATH = SCRIPT_DIR / "bot_script.js"

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
def format_log(tag: str, msg: str):
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
    print(f"{Colors.GRAY}[{timestamp}]{Colors.END} {color}[{tag}]{Colors.END} {msg}")

def print_banner():
    banner = f"""{Colors.CYAN}{Colors.BOLD}
=============================================================================
  ⚡ أتمتة صندوق بريد Meta Business Suite & استعادة غير مقروء (V4.4)
  ⚡ Meta Business Suite Inbox Auto-Responder & Unread Restorer (Production)
============================================================================={Colors.END}
  • الفلترة المتقدمة للمحادثات وقفل الحدود بعد آخر رد
  • واجهة تحكم متكاملة (HUD) مدمجة في صفحة فيسبوك مباشرة
  • لوحة تحكم للقواعد وتعديل سرعات الكتابة والتهدئة
  • حماية من استبعاد المحادثات وتخطي التكرار
=============================================================================
"""
    print(banner)

# ---------------------------------------------------------------------------
# Main Execution Engine
# ---------------------------------------------------------------------------
def run():
    parser = argparse.ArgumentParser(description="Meta Business Suite Inbox Automator & Unread Restorer")
    parser.add_argument("--port", type=int, default=9222, help="Chrome Remote Debugging Port (default: 9222)")
    parser.add_argument("--config", type=str, default=str(DEFAULT_CONFIG_PATH), help="Path to config.json file")
    parser.add_argument("--auto-start", action="store_true", help="Start automator immediately without waiting for HUD button")
    args = parser.parse_args()

    print_banner()

    config_path = Path(args.config)
    settings = load_config(config_path)

    auto_start = args.auto_start or settings.get("auto_start", False)

    if not BOT_SCRIPT_PATH.exists():
        print(f"{Colors.RED}❌ ملف المحرك البرمجي {BOT_SCRIPT_PATH} غير موجود!{Colors.END}")
        return

    with open(BOT_SCRIPT_PATH, "r", encoding="utf-8") as f:
        bot_js_code = f.read()

    print(f"{Colors.CYAN}🚀 جاري الاتصال بمتصفح Chrome المفتوح عبر منفذ CDP {args.port}...{Colors.END}")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{args.port}")
        except Exception as e:
            print(f"\n{Colors.RED}❌ تعذر الاتصال بالمتصفح! التفاصيل: {e}{Colors.END}")
            print(f"\n{Colors.YELLOW}👉 تأكد من تشغيل Google Chrome مع تفعيل منفذ التحكم بالأمر التالي:{Colors.END}")
            print(f"{Colors.BOLD}google-chrome --remote-debugging-port={args.port}{Colors.END}")
            print(f"\nأو في نظام ويندوز:")
            print(f'chrome.exe --remote-debugging-port={args.port} --user-data-dir="C:\\chrome-dev-profile"')
            return

        # البحث عن تبويب Meta Business Suite
        print(f"{Colors.GRAY}🔍 جاري البحث عن تبويب Meta Business Suite مفتوح...{Colors.END}")
        target_page = None

        for context in browser.contexts:
            for page in context.pages:
                if "business.facebook.com" in page.url:
                    target_page = page
                    break
            if target_page:
                break

        if not target_page:
            print(f"\n{Colors.YELLOW}⚠️ لم يتم العثور على تبويب Meta Business Suite مفتوح.{Colors.END}")
            print(f"{Colors.CYAN}🌐 جاري فتح صفحة الصندوق تلقائياً في المتصفح...{Colors.END}")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            target_page = context.new_page()
            target_page.goto("https://business.facebook.com/latest/inbox/all")
            print(f"{Colors.GRAY}⏳ بانتظار تحميل الصفحة...{Colors.END}")
            target_page.wait_for_load_state("domcontentloaded")
            time.sleep(3)

        target_page.bring_to_front()
        title = target_page.title()
        print(f"{Colors.GREEN}✅ تم الاتصال بنجاح بصفحة: {title}{Colors.END}")
        print(f"{Colors.GRAY}🔗 رابط الصفحة: {target_page.url}{Colors.END}")

        # -----------------------------------------------------------------------
        # تعريف دوال الربط (Python Bridge Functions)
        # -----------------------------------------------------------------------
        def py_log_handler(tag, message):
            format_log(tag, message)

        def py_update_stats_handler(stats):
            eval_c = stats.get("evaluated", 0)
            match_c = stats.get("matched", 0)
            unread_c = stats.get("unreadRestored", 0)
            skip_c = stats.get("skippedOutbound", 0)
            sys.stdout.write(f"\r{Colors.BOLD}📊 الإحصائيات:{Colors.END} [فحص: {eval_c}] | [{Colors.GREEN}رد: {match_c}{Colors.END}] | [{Colors.YELLOW}استعادة: {unread_c}{Colors.END}] | [{Colors.PURPLE}مستبعد: {skip_c}{Colors.END}]  ")
            sys.stdout.flush()

        def py_save_config_handler(rules_json_str, config_json_str):
            try:
                updated_rules = json.loads(rules_json_str)
                updated_config = json.loads(config_json_str)
                settings["rules"] = updated_rules
                settings["config"] = updated_config
                save_config(config_path, settings)
                format_log("INFO", "تم حفظ وتحديث القواعد والإعدادات في config.json بنجاح.")
            except Exception as ex:
                format_log("WARN", f"تعذر تحديث ملف الإعدادات: {ex}")

        def py_state_handler(status_text):
            format_log("INFO", f"حالة المحرك تغيرت إلى: {status_text}")

        # ربط الدوال بالصفحة
        try:
            target_page.expose_function("pyLog", py_log_handler)
            target_page.expose_function("pyUpdateStats", py_update_stats_handler)
            target_page.expose_function("pySaveConfig", py_save_config_handler)
            target_page.expose_function("pyOnStateChange", py_state_handler)
        except Exception:
            # في حال كانت الدوال ممررة مسبقاً في نفس جلسة التبويب
            pass

        # -----------------------------------------------------------------------
        # حقن المحرك وواجهة التحكم (HUD) في الصفحة
        # -----------------------------------------------------------------------
        def inject_engine():
            try:
                target_page.evaluate("""() => {
                    if (window.__MBS_AUTOMATOR_STOP__) window.__MBS_AUTOMATOR_STOP__();
                    const root = document.getElementById("mbs-inbox-automator-root");
                    if (root) root.remove();
                    delete window.__MBS_AUTOMATOR_V44_LOADED__;
                }""")
                # تمرير القواعد والإعدادات المبدئية
                target_page.evaluate("""
                    ({ rules, config }) => {
                        window.__INITIAL_RULES__ = rules;
                        window.__INITIAL_CONFIG__ = config;
                    }
                """, {"rules": settings.get("rules", []), "config": settings.get("config", {})})

                # حقن الكود الكامل
                target_page.evaluate(bot_js_code)
                print(f"{Colors.GREEN}✨ تم تثبيت واجهة التحكم التفاعلية (HUD) بنجاح في المتصفح!{Colors.END}")
                print(f"{Colors.CYAN}💡 يمكنك التحكم بالكامل من النافذة الظاهرة أسفل يسار الشاشة في كروم.{Colors.END}")
            except Exception as e:
                print(f"{Colors.RED}❌ خطأ أثناء حقن واجهة التحكم: {e}{Colors.END}")

        inject_engine()

        # إعادة الحقن تلقائياً عند تحديث الصفحة (Refresh / Navigation)
        def on_page_reloaded():
            try:
                time.sleep(1)
                inject_engine()
                if auto_start:
                    time.sleep(0.5)
                    target_page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")
            except Exception:
                pass

        target_page.on("domcontentloaded", lambda: on_page_reloaded())

        # بدء الأتمتة تلقائياً إذا كان مفعل
        if auto_start:
            print(f"{Colors.YELLOW}⚡ تفعيل بدء الأتمتة التلقائي...{Colors.END}")
            time.sleep(1)
            target_page.evaluate("() => { setTimeout(() => window.__MBS_AUTOMATOR_START__ && window.__MBS_AUTOMATOR_START__(), 100); }")

        print(f"\n{Colors.BOLD}🔘 اضغط [Esc] داخل المتصفح أو [Ctrl+C] هنا للإيقاف الآمن في أي لحظة.{Colors.END}\n")

        # حلقة المراقبة الأساسية والانتظار
        try:
            while True:
                time.sleep(1)
                # التأكد من بقاء التبويب مفتوحاً
                if target_page.is_closed():
                    print(f"\n{Colors.YELLOW}⚠️ تم إغلاق تبويب Meta Business Suite. جاري إنهاء البرنامج.{Colors.END}")
                    break
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⏹ تم استلام إشارة التوقف (Ctrl+C). جاري إيقاف الأتمتة وتنظيف التأطير...{Colors.END}")
            try:
                if not target_page.is_closed():
                    target_page.evaluate("() => window.__MBS_AUTOMATOR_STOP__ && window.__MBS_AUTOMATOR_STOP__()")
            except Exception:
                pass
            print(f"{Colors.GREEN}✅ تم إيقاف الأتمتة بنجاح.{Colors.END}")

if __name__ == "__main__":
    run()
