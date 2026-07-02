"""Headless-Chromium smoke screenshots of each dashboard route.

Requires the server already running (see README). Writes PNGs to the
scratchpad dir passed as argv[1] (default: /tmp/rtm-screens).
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8123"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rtm-screens")
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = [
    ("rankings", "#/rankings?cmd=uco&flow=X&year=2024"),
    ("trend", "#/trend?cmd=pome"),
    ("partners", "#/partners?cmd=pome&flow=X&year=2024&reporter=IDN"),
    ("watchlist", "#/watchlist?region=asia&year=2024"),
    ("signals", "#/signals?cmd=pome&flow=X&year=2024"),
    ("methodology", "#/methodology"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    for name, route in ROUTES:
        page.goto(f"{BASE}/{route}")
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        print(f"wrote {OUT / (name + '.png')}")
    # dark mode pass on one route — click the real toggle, not a JS hack
    page.click("#theme-toggle")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / "rankings_dark.png"), full_page=True)
    print(f"wrote {OUT / 'rankings_dark.png'}")
    browser.close()
    if errors:
        print("CONSOLE ERRORS:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("no console errors")
