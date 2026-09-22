#!/usr/bin/env python3
"""Read-only release checks for Meta Automation V6.6 Hybrid."""

from __future__ import annotations

import json
import re
import sys
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_python_syntax() -> None:
    for name in ("desktop_app.py", "profile_manager.py", "main.py", "verify_release.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        compile(source, str(ROOT / name), "exec")


def verify_config_round_trip() -> None:
    payload = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "config.schema.json").read_text(encoding="utf-8"))
    require(schema.get("$schema", "").endswith("2020-12/schema"), "Unexpected JSON Schema draft")
    require(isinstance(payload.get("rules"), list), "rules must be an array")
    require(isinstance(payload.get("config"), dict), "config must be an object")
    require(isinstance(payload.get("auto_start"), bool), "auto_start must be boolean")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    require(json.loads(encoded) == payload, "config JSON serialization is not lossless")
    code_pattern = re.compile(r"^MBS-[0-9A-HJKMNP-TV-Z]{8}$")
    for rule in payload["rules"]:
        if "ruleCode" in rule:
            require(bool(code_pattern.fullmatch(rule["ruleCode"])), "Invalid Crockford ruleCode")

    spec = importlib.util.spec_from_file_location("hybrid_profile_manager", ROOT / "profile_manager.py")
    require(spec is not None and spec.loader is not None, "Unable to load profile manager contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    normalized = module.normalize_local_rules([
        {"active": True, "keywords": ["legacy"], "reply": "ok", "contextKeywords": ["context"]}
    ])
    require(normalized[0]["matchType"] == "contains", "Legacy missing matchType must default to contains")
    require(bool(code_pattern.fullmatch(normalized[0]["ruleCode"])), "Generated ruleCode is invalid")
    require(json.loads(json.dumps(normalized, ensure_ascii=False)) == normalized, "Normalized rules are not JSON serializable")


def verify_engine_contract() -> None:
    bot = (ROOT / "bot_script.js").read_bytes()
    userscript = (ROOT / "meta_inbox_userscript.user.js").read_bytes()
    require(bot == userscript, "Userscript is not byte-identical to bot_script.js")
    text = bot.decode("utf-8")
    for marker in (
        "extendForActiveReply(replyBudgetMs)",
        "normMsg === normKw",
        "finalizeCompletedReply",
        "recentSentMessages",
        "contextKeywords",
        "contextMatchType",
        "matchedRuleCode",
        "APPLY_RULE_SNAPSHOT",
        "RELOAD_CONFIG",
    ):
        require(marker in text, f"Required engine contract is missing: {marker}")
    for forbidden in ("SurfaceLease", "acquireConversationSurfaceLease", "M1 Surface Lease"):
        require(forbidden not in text, f"Forbidden Source B surface-lease marker found: {forbidden}")


def main() -> int:
    checks = (verify_python_syntax, verify_config_round_trip, verify_engine_contract)
    for check in checks:
        check()
        print(f"PASS {check.__name__}")
    print("PASS V6.6 hybrid release gate")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
