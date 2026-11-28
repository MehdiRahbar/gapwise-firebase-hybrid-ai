"""Targeted browser regression checks for the shared Simple/Advanced UI."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PORT = 18301
NODE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "NodeJS-24.20.0" / "node-v24.20.0-win-x64"
ENV = os.environ.copy()
if NODE_DIR.is_dir():
    ENV["PATH"] = str(NODE_DIR) + os.pathsep + ENV.get("PATH", "")
NODE = shutil.which("node.exe" if os.name == "nt" else "node", path=ENV.get("PATH")) or "node"
VITE = ROOT / "node_modules" / "vite" / "bin" / "vite.js"
OUT = ROOT / "evidence"
OUT.mkdir(exist_ok=True)


def wait_for_server():
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.3):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("Vite server did not start")


def assert_unique_ids(page):
    duplicate_ids = page.evaluate(
        """() => {
          const ids = [...document.querySelectorAll('[id]')].map((el) => el.id);
          return [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
        }"""
    )
    assert not duplicate_ids, duplicate_ids


def run():
    server = subprocess.Popen(
        [NODE, str(VITE), "--host", "127.0.0.1", "--port", str(PORT), "--strictPort"],
        cwd=str(ROOT),
        env=ENV,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    results = {}
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            firebase_requests = []
            page_errors = []
            console_errors = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.on(
                "request",
                lambda request: firebase_requests.append(request.url)
                if ("googleapis.com" in request.url or "firebase" in request.url)
                else None,
            )
            page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

            assert page.locator("body").get_attribute("data-view") == "advanced"
            assert page.locator("#viewSimpleBtn").count() == 1
            assert page.locator("#viewAdvancedBtn").count() == 1
            assert page.locator(".simple-accordion").count() >= 6
            assert_unique_ids(page)
            assert page.locator("#appNav").is_visible()
            assert page.locator("#result").is_visible()
            page.screenshot(path=str(OUT / "advanced_desktop_before.png"), full_page=True)
            results["advanced_default"] = "PASS"

            question = page.locator("#question")
            question.fill("State must survive a presentation switch")
            first_unknown = page.locator('.cond-controls button[data-value="unknown"]').first
            first_unknown.click()
            page.locator("#settingsBtn").click()
            page.locator("#cloudConsent").check()
            page.keyboard.press("Escape")
            history_before = page.locator("#auditHistory .history-item").count()

            before_requests = len(firebase_requests)
            page.locator("#viewSimpleBtn").click()
            page.wait_for_function("document.body.dataset.view === 'simple'")
            assert len(firebase_requests) == before_requests
            assert page.locator("#viewSimpleBtn").get_attribute("aria-pressed") == "true"
            assert page.locator("#viewAdvancedBtn").get_attribute("aria-pressed") == "false"
            assert page.locator("#question").input_value() == "State must survive a presentation switch"
            assert first_unknown.get_attribute("aria-pressed") == "true"
            assert page.locator("#cloudConsent").is_checked()
            assert page.locator("#result").is_visible()
            assert page.locator("#simpleProvenance").is_visible()
            assert page.locator("#simpleStatus").is_visible()
            assert page.locator("#auditHistory .history-item").count() >= history_before
            results["switch_to_simple_preserves_state"] = "PASS"

            checklist = page.locator("#checklist-step")
            assert checklist.get_attribute("open") is None
            checklist.locator(":scope > summary").press("Enter")
            assert checklist.get_attribute("open") is not None
            page.wait_for_function("document.querySelector('#checklist-step > summary').getAttribute('aria-expanded') === 'true'")
            checklist.locator(":scope > summary").press("Enter")
            assert checklist.get_attribute("open") is None
            page.wait_for_function("document.querySelector('#checklist-step > summary').getAttribute('aria-expanded') === 'false'")
            results["keyboard_accordion"] = "PASS"

            page.reload(wait_until="networkidle")
            assert page.locator("body").get_attribute("data-view") == "simple"
            assert page.locator("#viewSimpleBtn").get_attribute("aria-pressed") == "true"
            results["preference_persists_after_reload"] = "PASS"

            page.locator("#checklist-step > summary").click()
            page.locator("#sourceDetails > summary").click()
            page.locator("#sourceText").fill("Policy requires an external notarized seal before approval.")
            page.locator("#source-audit-step").evaluate("(el) => { el.open = false; }")
            page.locator("#analyzeBtn").click()
            page.wait_for_function("document.querySelector('#modelSuggestions').hidden === false")
            assert page.locator("#source-audit-step").get_attribute("open") is not None
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(OUT / "simple_after_analysis.png"), full_page=True)
            results["analysis_reveals_review_section"] = "PASS"

            page.locator("#viewAdvancedBtn").click()
            assert page.locator("body").get_attribute("data-view") == "advanced"
            assert page.locator("#appNav").is_visible()
            assert page.locator("#question").is_visible()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(OUT / "advanced_desktop_after.png"), full_page=True)
            results["switch_back_to_advanced"] = "PASS"

            blocked_context = browser.new_context(
                viewport={"width": 1440, "height": 900},
            )
            blocked_context.add_init_script(
                "Object.defineProperty(window, 'localStorage', { get() { throw new Error('storage blocked'); } });"
            )
            blocked_page = blocked_context.new_page()
            blocked_page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
            assert blocked_page.locator("body").get_attribute("data-view") == "advanced"
            results["storage_failure_safe_fallback"] = "PASS"
            blocked_context.close()

            for name, width, height in (("simple_390", 390, 844), ("simple_360", 360, 740)):
                page.set_viewport_size({"width": width, "height": height})
                page.locator("#viewSimpleBtn").click()
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
                assert not overflow, f"horizontal overflow at {width}px"
                results[f"{name}_no_overflow"] = "PASS"

            page.set_viewport_size({"width": 390, "height": 844})
            page.locator("#viewAdvancedBtn").click()
            page.evaluate("window.scrollTo(0, 0)")
            assert not page.locator("body").evaluate("(body) => body.classList.contains('nav-open')")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "advanced_mobile_regression.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 900})
            page.locator("#viewSimpleBtn").click()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(OUT / "simple_desktop_closed.png"), full_page=True)
            page.locator("#checklist-step > summary").click()
            page.locator("#source-audit-step > summary").click()
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(OUT / "simple_desktop_expanded.png"), full_page=True)
            assert not page_errors, page_errors
            assert not console_errors, console_errors
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=5)
    (OUT / "dual_ui_browser_test.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run()

