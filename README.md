# Meta Automation V6.6 Hybrid

This standalone release combines the V6.3.8 browser messaging engine with the
modern multi-profile desktop shell, Crockford `MBS-XXXXXXXX` rule codes, linked
rule synchronization, and context-aware rule fields.

## Launch

- Linux: `./launch_desktop.sh`
- Windows: `launch_desktop.bat`

Install dependencies first with `python -m pip install -r requirements.txt` and
install Playwright Chromium with `python -m playwright install chromium`.

The default attach-mode debugging port is `9660`. Hybrid profile data is stored
separately under `~/.config/meta_inbox_bot_v66_hybrid/profiles` on Linux or
`%USERPROFILE%\MetaInboxBot_V66_Hybrid_Profiles` on Windows.

Run `python3 verify_release.py` to check Python syntax, JSON serialization,
stable-engine markers, forbidden surface-lease markers, and byte parity between
`bot_script.js` and `meta_inbox_userscript.user.js`.
