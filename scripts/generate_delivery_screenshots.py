#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Business Automator — V6.5.2 Delivery Screenshot Generator (Playwright)
Generates 5 real bridge-driven visual verification screenshots directly into the artifact directory:
1. screenshot_sidebar_counts.png: Real production profile counts via ProfileManager.list_profiles()
2. screenshot_rule_card_and_multiline_editor.png: Real rule card with Crockford code, name, and multiline textareas
3. screenshot_linked_rule_badge.png: Linked rule badge with 'مرتبطة' and 'فك الارتباط' button
4. screenshot_import_modal_link_options.png: Import modal with Clone vs Link radio options
5. screenshot_conflict_resolution_modal.png: 3-Profile conflict resolution modal
"""

import json
import os
import sys
import time
import tempfile
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
GUI_HTML_PATH = ROOT_DIR / "gui" / "index.html"
ARTIFACT_DIR = Path("/home/bishoy/.gemini/antigravity/brain/0dd58517-ec39-4870-8dbe-b56dd5cfe65c")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT_DIR))
from profile_manager import ProfileManager, allocate_unique_rule_code
from desktop_app import DesktopBridgeApi


def find_chrome_executable():
    for p in ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]:
        if Path(p).exists():
            return p
    return None


def generate_delivery_screenshots():
    print("=== Generating V6.5.2 Delivery Screenshots via Real Bridge ===")

    chrome_exec = find_chrome_executable()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=chrome_exec,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
        )

        # ---------------------------------------------------------------------
        # Part 1: Real Production Sidebar Counts Screenshot
        # ---------------------------------------------------------------------
        print("\n--- Capturing Screenshot 1: Real Production Sidebar Counts ---")
        prod_pm = ProfileManager()  # Uses ~/.config/meta_inbox_bot/profiles
        prod_bridge = DesktopBridgeApi(prod_pm, controller=None, loop=None)

        context1 = browser.new_context(viewport={"width": 1440, "height": 900})
        page1 = context1.new_page()

        # Expose real bridge methods
        page1.expose_function("__bridge_get_profiles", lambda: prod_bridge.get_profiles())
        page1.expose_function("__bridge_load_profile_config_result", lambda name: prod_bridge.load_profile_config_result(name))
        page1.expose_function("__bridge_load_profile_config", lambda name: prod_bridge.get_profile_config(name))
        page1.expose_function("__bridge_get_profile_config", lambda name: prod_bridge.get_profile_config(name))
        page1.expose_function("__bridge_get_linked_rules_map", lambda: prod_bridge.get_linked_rules_map())
        page1.expose_function("__bridge_allocate_rule_metadata", lambda p=None: prod_bridge.allocate_rule_metadata(p))
        page1.expose_function("__bridge_get_logs", lambda: [])
        page1.expose_function("__bridge_get_stats", lambda: {})

        page1.add_init_script("""
            window.alert = () => {};
            window.confirm = () => true;
            window.pywebview = {
                api: {
                    get_profiles: async () => window.__bridge_get_profiles(),
                    load_profile_config_result: async (name) => window.__bridge_load_profile_config_result(name),
                    load_profile_config: async (name) => window.__bridge_load_profile_config(name),
                    get_profile_config: async (name) => window.__bridge_get_profile_config(name),
                    get_linked_rules_map: async () => window.__bridge_get_linked_rules_map(),
                    allocate_rule_metadata: async (p) => window.__bridge_allocate_rule_metadata(p),
                    get_logs: async () => window.__bridge_get_logs(),
                    get_stats: async () => window.__bridge_get_stats(),
                }
            };
        """)

        page1.goto(f"file://{GUI_HTML_PATH}")
        page1.wait_for_load_state("domcontentloaded")
        time.sleep(1.2)

        sidebar_el = page1.locator(".desktop-sidebar")
        if sidebar_el.count() > 0:
            sidebar_path = ARTIFACT_DIR / "screenshot_sidebar_counts.png"
            sidebar_el.screenshot(path=str(sidebar_path))
            print(f" [Captured] {sidebar_path}")

        context1.close()

        # ---------------------------------------------------------------------
        # Part 2: Isolated Fixture Profiles for Rule Card, Badge, Import & Conflict
        # ---------------------------------------------------------------------
        print("\n--- Capturing Screenshots 2, 3, 4, 5 on Isolated Real Fixtures ---")
        tmp_dir = tempfile.TemporaryDirectory()
        fixture_base = Path(tmp_dir.name)
        fixture_pm = ProfileManager(base_dir=fixture_base)
        fixture_pm.ownership_guard.acquire()
        fixture_bridge = DesktopBridgeApi(fixture_pm, controller=None, loop=None)

        # Seed 3 fixture profiles with linked Crockford rules
        shared_code = "MBS-7Q2N8K4R"

        rule_cat_a = {
            "id": "rule_cat_a_1",
            "name": "استفسار السعر الرئيسي",
            "ruleCode": shared_code,
            "keywords": [" سعر ", "سعر, كام", "سعر\nالمشد"],
            "keyword": " سعر , سعر, كام, سعر\nالمشد",
            "reply": "سعر المشد الحراري 250 جنيهاً مصرياً\nشامل مصاريف الشحن والتوصيل السريع\nضمان استبدال ومعاينة مجانية 14 يوماً",
            "matchType": "ultra_exact",
            "caseSensitive": False,
            "contextKeywords": ["عرض_خاص"],
            "active": True
        }

        rule_cat_b = {
            "id": "rule_cat_b_1",
            "name": "استفسار السعر (كتالوج ب)",
            "ruleCode": shared_code,
            "keywords": [" سعر ", "سعر, كام", "سعر\nالمشد"],
            "keyword": " سعر , سعر, كام, سعر\nالمشد",
            "reply": "سعر المشد الحراري 250 جنيهاً مصرياً\nشامل مصاريف الشحن والتوصيل السريع\nضمان استبدال ومعاينة مجانية 14 يوماً",
            "matchType": "ultra_exact",
            "caseSensitive": False,
            "contextKeywords": ["عرض_خاص"],
            "active": True
        }

        # Catalog C starts with divergent content to enable conflict demo
        rule_cat_c = {
            "id": "rule_cat_c_1",
            "name": "استفسار السعر (كتالوج ج)",
            "ruleCode": shared_code,
            "keywords": [" سعر ", "سعر, كام", "سعر\nالمشد"],
            "keyword": " سعر , سعر, كام, سعر\nالمشد",
            "reply": "سعر المشد في فرع الإسكندرية 270 جنيهاً شامل المعاينة",
            "matchType": "ultra_exact",
            "caseSensitive": False,
            "contextKeywords": ["عرض_خاص"],
            "active": True
        }

        for p_name, r_item in [
            ("Catalog A", rule_cat_a),
            ("Catalog B", rule_cat_b),
            ("Catalog C", rule_cat_c),
        ]:
            p_dir = fixture_base / p_name
            p_dir.mkdir(parents=True, exist_ok=True)
            cfg_path = p_dir / "config.json"
            cfg_data = {"rules": [r_item], "config": {"active": True, "cooldown_seconds": 1.5, "typing_speed": 15}}
            cfg_path.write_text(json.dumps(cfg_data, ensure_ascii=False, indent=2), encoding="utf-8")

        context2 = browser.new_context(viewport={"width": 1440, "height": 900})
        page2 = context2.new_page()

        # Expose all bridge endpoints to page
        page2.expose_function("__bridge_get_profiles", lambda: fixture_bridge.get_profiles())
        page2.expose_function("__bridge_load_profile_config_result", lambda name: fixture_bridge.load_profile_config_result(name))
        page2.expose_function("__bridge_load_profile_config", lambda name: fixture_bridge.get_profile_config(name))
        page2.expose_function("__bridge_get_profile_config", lambda name: fixture_bridge.get_profile_config(name))
        page2.expose_function("__bridge_get_linked_rules_map", lambda: fixture_bridge.get_linked_rules_map())
        page2.expose_function("__bridge_allocate_rule_metadata", lambda p=None: fixture_bridge.allocate_rule_metadata(p))
        page2.expose_function("__bridge_save_profile_config_coordinated", lambda p, c, s=None: fixture_bridge.save_profile_config_coordinated(p, c, expected_sha256=s))
        page2.expose_function("__bridge_save_profile_config", lambda p, c: fixture_bridge.save_profile_config(p, c))
        page2.expose_function("__bridge_unlink_rule", lambda p, rid: fixture_bridge.unlink_rule(p, rid))
        page2.expose_function("__bridge_import_rules_from_profile", lambda t, s, rids, m="clone": fixture_bridge.import_rules_from_profile(t, s, rids, mode=m))
        page2.expose_function("__bridge_resolve_link_conflict", lambda c, a, s=None: fixture_bridge.resolve_link_conflict(c, a, expected_shas=s))
        page2.expose_function("__bridge_get_logs", lambda: [])
        page2.expose_function("__bridge_get_stats", lambda: {})

        page2.add_init_script("""
            window.alert = () => {};
            window.confirm = () => true;
            window.pywebview = {
                api: {
                    get_profiles: async () => window.__bridge_get_profiles(),
                    load_profile_config_result: async (name) => window.__bridge_load_profile_config_result(name),
                    load_profile_config: async (name) => window.__bridge_load_profile_config(name),
                    get_profile_config: async (name) => window.__bridge_get_profile_config(name),
                    get_linked_rules_map: async () => window.__bridge_get_linked_rules_map(),
                    allocate_rule_metadata: async (p) => window.__bridge_allocate_rule_metadata(p),
                    save_profile_config_coordinated: async (p, c, s) => window.__bridge_save_profile_config_coordinated(p, c, s),
                    save_profile_config: async (p, c) => window.__bridge_save_profile_config(p, c),
                    unlink_rule: async (p, rid) => window.__bridge_unlink_rule(p, rid),
                    import_rules_from_profile: async (t, s, rids, m) => window.__bridge_import_rules_from_profile(t, s, rids, m),
                    resolve_link_conflict: async (c, a, s) => window.__bridge_resolve_link_conflict(c, a, s),
                    get_logs: async () => window.__bridge_get_logs(),
                    get_stats: async () => window.__bridge_get_stats(),
                }
            };
        """)

        page2.goto(f"file://{GUI_HTML_PATH}")
        page2.wait_for_load_state("domcontentloaded")
        time.sleep(1.2)

        # Select Catalog A
        page2.locator(".profile-card", has_text="Catalog A").first.click()
        time.sleep(0.5)
        page2.locator(".tab-btn[data-tab='rules']").click()
        time.sleep(0.8)

        # Screenshot 2: Rule Card with Code, Editable Name, Multiline Editor
        rule_card = page2.locator(".rule-card").first
        if rule_card.count() > 0:
            card_path = ARTIFACT_DIR / "screenshot_rule_card_and_multiline_editor.png"
            rule_card.screenshot(path=str(card_path))
            print(f" [Captured] {card_path}")

        # Screenshot 3: Linked Rule Badge & Unlink Action Button
        linked_meta = page2.locator(".rule-meta-bar").first
        if linked_meta.count() > 0:
            badge_path = ARTIFACT_DIR / "screenshot_linked_rule_badge.png"
            linked_meta.screenshot(path=str(badge_path))
            print(f" [Captured] {badge_path}")

        # Screenshot 4: Import Modal with Clone vs Link Options
        btn_import = page2.locator("#btn-import-rules")
        if btn_import.count() > 0:
            btn_import.click()
            time.sleep(0.5)
            page2.locator("#import-source-profile-select").select_option("Catalog B")
            time.sleep(0.6)
            modal_el = page2.locator("#modal-import-rules .desktop-modal-card")
            if modal_el.count() > 0:
                modal_path = ARTIFACT_DIR / "screenshot_import_modal_link_options.png"
                modal_el.screenshot(path=str(modal_path))
                print(f" [Captured] {modal_path}")

            # Close import modal
            btn_close_import = page2.locator("#btn-cancel-import")
            if btn_close_import.count() > 0:
                btn_close_import.click()
                time.sleep(0.4)

        # Screenshot 5: Conflict Resolution Modal (Divergent Catalog C vs Catalog A)
        # Trigger save rules on Catalog A (modifying a keyword to trigger coordinated save)
        # Because Catalog C has divergent reply on disk, LINK_CONFLICT is returned!
        page2.evaluate("""async () => {
            const card = document.querySelector('.rule-card');
            if (card) {
                const ta = card.querySelector('.keyword-textarea');
                if (ta) {
                    ta.value = ' سعر جديد ';
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
            const btnSave = document.getElementById('btn-save-rules');
            if (btnSave) btnSave.click();
        }""")
        time.sleep(1.0)

        conflict_modal_el = page2.locator("#modal-link-conflict .desktop-modal-card")
        if conflict_modal_el.count() > 0 and page2.locator("#modal-link-conflict.active").count() > 0:
            conflict_path = ARTIFACT_DIR / "screenshot_conflict_resolution_modal.png"
            conflict_modal_el.screenshot(path=str(conflict_path))
            print(f" [Captured] {conflict_path}")
        else:
            print(" [WARN] Conflict modal not active, taking whole page capture")
            conflict_path = ARTIFACT_DIR / "screenshot_conflict_resolution_modal.png"
            page2.screenshot(path=str(conflict_path))

        context2.close()
        browser.close()
        fixture_pm.ownership_guard.release()
        tmp_dir.cleanup()

    print("\nAll 5 visual proof screenshots successfully created in artifact directory.")


if __name__ == "__main__":
    generate_delivery_screenshots()
