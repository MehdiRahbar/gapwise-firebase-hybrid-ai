"""Read-only live Firebase Hosting audit for GAPWISE.

This intentionally does not call Gemini/Nano inference, change Firebase state,
or use a persistent browser profile. It uses a clean Playwright context and
stores the audit outside the repository by default.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("GAPWISE_LIVE_AUDIT_OUT", str(ROOT / "_live_site_audit_output")))
OUT.mkdir(parents=True, exist_ok=True)
LIVE_URLS = [
    url.strip()
    for url in os.environ.get(
        "GAPWISE_LIVE_AUDIT_URLS",
        "https://gapwise-hybrid-2026.web.app/,https://gapwise-hybrid-2026.firebaseapp.com/",
    ).split(",")
    if url.strip()
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_bytes(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "GAPWISE-live-site-audit/1.0 (read-only)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return {
                "status": response.status,
                "url": response.geturl(),
                "headers": {k.lower(): v for k, v in response.headers.items()},
                "bytes": len(body),
                "sha256": sha256_bytes(body),
                "body": body,
            }
    except urllib.error.HTTPError as error:
        body = error.read()
        return {
            "status": error.code,
            "url": url,
            "headers": {k.lower(): v for k, v in error.headers.items()},
            "bytes": len(body),
            "sha256": sha256_bytes(body),
            "body": body,
            "error": str(error),
        }
    except Exception as error:  # pragma: no cover - environment/network boundary
        return {"status": None, "url": url, "error": str(error), "bytes": 0, "sha256": None, "body": b""}


def tls_summary(host: str) -> dict[str, Any]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=20) as raw:
            with context.wrap_socket(raw, server_hostname=host) as connection:
                certificate = connection.getpeercert()
                subject = dict(item[0] for item in certificate.get("subject", ()))
                issuer = dict(item[0] for item in certificate.get("issuer", ()))
                return {
                    "status": "PASS",
                    "tlsVersion": connection.version(),
                    "cipher": connection.cipher()[0] if connection.cipher() else None,
                    "subjectCommonName": subject.get("commonName"),
                    "issuerCommonName": issuer.get("commonName"),
                    "notBefore": certificate.get("notBefore"),
                    "notAfter": certificate.get("notAfter"),
                }
    except Exception as error:  # pragma: no cover - environment/network boundary
        return {"status": "FAIL", "error": str(error)}


def asset_paths(html: str) -> list[str]:
    paths = re.findall(
        r"(?:src|href)=\"([^\"]+\.(?:js|css|svg|png|webp|jpe?g|ico|woff2?))\"",
        html,
        flags=re.IGNORECASE,
    )
    return sorted(dict.fromkeys(paths))


def local_asset_manifest() -> dict[str, Any]:
    index = ROOT / "dist" / "index.html"
    html = index.read_text(encoding="utf-8")
    files: dict[str, Any] = {
        "index.html": {
            "path": str(index),
            "bytes": index.stat().st_size,
            "sha256": sha256_bytes(index.read_bytes()),
        },
        "assets": {},
    }
    dist_assets = ROOT / "dist" / "assets"
    all_asset_files = sorted(dist_assets.glob("*")) if dist_assets.is_dir() else []
    for file_path in all_asset_files:
        path = "/assets/" + file_path.name
        if file_path.is_file():
            files["assets"][path] = {
                "path": str(file_path),
                "bytes": file_path.stat().st_size,
                "sha256": sha256_bytes(file_path.read_bytes()),
            }
        else:
            files["assets"][path] = {"path": str(file_path), "missing": True}
    return files


def text_contains(page: Page, phrases: list[str]) -> bool:
    body = page.locator("body").inner_text(timeout=5000).lower()
    return any(phrase.lower() in body for phrase in phrases)


def safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    locator = page.locator(selector).first
    if locator.count() == 0:
        return False
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        return False


def wait_result(page: Page, timeout: int = 5000) -> str:
    try:
        page.locator("#result").wait_for(timeout=timeout)
        return page.locator("#result").inner_text()
    except Exception:
        return ""


def deterministic_flows(page: Page, host_key: str) -> dict[str, Any]:
    results: dict[str, Any] = {}
    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1200)
    initial = wait_result(page)
    results["workbench_open"] = page.locator("#workbench").count() == 1 or page.locator("#question").count() == 1
    results["initial_result_contains_ask"] = "MORE INFORMATION REQUIRED" in initial

    nav_toggle = page.locator("#navToggle")
    if nav_toggle.count():
        expanded_before = nav_toggle.get_attribute("aria-expanded")
        toggled = safe_click(page, "#navToggle")
        page.wait_for_timeout(100)
        expanded_after = nav_toggle.get_attribute("aria-expanded") if toggled else None
        results["sidebar_toggle"] = {
            "available": toggled,
            "before": expanded_before,
            "after": expanded_after,
            "pass": toggled and expanded_before != expanded_after,
        }
        if toggled:
            safe_click(page, "#navToggle")
    else:
        results["sidebar_toggle"] = {
            "available": False,
            "before": None,
            "after": None,
            "pass": False,
            "reason": "#navToggle is absent from the live DOM",
        }

    sample_loaded = safe_click(page, "#examples button[data-index='0']") or safe_click(page, "#loadSampleSourceBtn")
    page.wait_for_timeout(500)
    results["sample_case_loaded"] = sample_loaded
    next_question_text = page.locator("#nextQuestion").inner_text() if page.locator("#nextQuestion").count() else ""
    results["adaptive_question_present"] = bool(next_question_text.strip())
    results["incomplete_information_detected"] = text_contains(page, ["MORE INFORMATION REQUIRED", "missing"])

    # Deterministic NO and CONFLICT controls do not invoke AI inference.
    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(500)
    safe_click(page, "#examples button[data-index='0']")
    no_clicked = safe_click(page, ".cond-controls button[data-value='no']")
    results["no_path"] = {
        "clicked": no_clicked,
        "pass": no_clicked and text_contains(page, ["NOT ELIGIBLE UNDER THIS POLICY"]),
    }
    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(500)
    safe_click(page, "#examples button[data-index='0']")
    conflict_buttons = page.locator(".cond-controls button[data-value='conflict']")
    conflict_clicked = conflict_buttons.count() > 1 and conflict_buttons.nth(1).click(timeout=5000) is None
    results["conflict_path"] = {
        "clicked": conflict_clicked,
        "pass": conflict_clicked and text_contains(page, ["CONFLICTING EVIDENCE"]),
    }

    # Export is tested without initiating an AI call.
    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(500)
    export_path = OUT / f"{host_key}_audit_export.json"
    export_result: dict[str, Any] = {"available": page.locator("#exportBtn").count() == 1}
    if export_result["available"]:
        try:
            with page.expect_download(timeout=7000) as download_info:
                page.locator("#exportBtn").click()
            download = download_info.value
            download.save_as(export_path)
            payload = json.loads(export_path.read_text(encoding="utf-8"))
            export_result.update({"pass": True, "path": str(export_path), "schema": payload.get("schema")})
        except Exception as error:
            export_result.update({"pass": False, "error": str(error)})
    results["export_audit"] = export_result

    # Settings and Firebase connection are tested, but no model request is made.
    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(500)
    settings_opened = safe_click(page, "#settingsBtn")
    page.wait_for_timeout(200)
    settings_open = page.locator("#settingsDialog").get_attribute("open") is not None if settings_opened else False
    connect_result: dict[str, Any] = {"settingsOpened": settings_open}
    if settings_open and page.locator("#connectBtn").count():
        try:
            page.locator("#connectBtn").click(timeout=5000)
            page.wait_for_timeout(5000)
            connect_result.update({
                "statusText": page.locator("#connectStatus").inner_text(),
                "envHint": page.locator("#envHint").inner_text() if page.locator("#envHint").count() else "",
                "pass": True,
            })
        except Exception as error:
            connect_result.update({"pass": False, "error": str(error)})
    results["firebase_settings_connection"] = connect_result
    body_text = page.locator("body").inner_text().lower()
    results["unavailable_nano_message_text_present"] = any(
        phrase in body_text for phrase in ["inference blocked", "unavailable", "fails closed", "only_on_device"]
    )

    # Mobile screenshot and overflow check.
    if page.locator("#settingsDialog").count() and page.locator("#settingsDialog").get_attribute("open") is not None:
        safe_click(page, "#settingsDialog button[type='submit']")
        page.wait_for_timeout(150)
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(300)
    mobile_path = OUT / f"{host_key}_mobile.png"
    page.screenshot(path=str(mobile_path), full_page=True)
    results["mobile"] = {
        "screenshot": str(mobile_path),
        "horizontalOverflow": page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2"),
    }
    return results


def audit_url(browser: Any, url: str, local: dict[str, Any]) -> dict[str, Any]:
    host_key = urlparse(url).hostname.replace(".", "_")
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[dict[str, Any]] = []
    ignored_failed_requests: list[dict[str, Any]] = []
    bad_responses: list[dict[str, Any]] = []
    responses: dict[str, dict[str, Any]] = {}
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    def on_request_failed(request: Any) -> None:
        item = {"url": request.url, "failure": request.failure}
        if request.failure == "net::ERR_ABORTED" and urlparse(request.url).path.endswith(".svg"):
            ignored_failed_requests.append({**item, "reason": "favicon lifecycle abort; direct HTTP fetch is verified separately"})
        else:
            failed_requests.append(item)

    page.on("requestfailed", on_request_failed)

    def on_response(response: Any) -> None:
        if response.request.resource_type in {"document", "script", "stylesheet", "font", "image"}:
            item = {"url": response.url, "status": response.status, "resourceType": response.request.resource_type}
            responses[response.url] = item
            if response.status >= 400:
                bad_responses.append(item)

    page.on("response", on_response)
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    title = page.title()
    html = page.content()
    desktop_path = OUT / f"{host_key}_desktop.png"
    page.screenshot(path=str(desktop_path), full_page=True)

    flows = deterministic_flows(page, host_key)
    remote_document = fetch_bytes(url)
    remote_assets: dict[str, Any] = {}
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    observed_same_origin_assets = sorted(
        {
            urlparse(response_url).path
            for response_url in responses
            if response_url.startswith(origin) and urlparse(response_url).path.startswith("/assets/")
        }
    )
    for path in sorted(set(asset_paths(html)) | set(observed_same_origin_assets) | set(local.get("assets", {}))):
        asset_url = urljoin(url, path)
        fetched = fetch_bytes(asset_url)
        remote_assets[path] = {
            "url": asset_url,
            "status": fetched.get("status"),
            "bytes": fetched.get("bytes"),
            "sha256": fetched.get("sha256"),
            "error": fetched.get("error"),
            "local": local.get("assets", {}).get(path),
            "hashMatchesLocal": fetched.get("sha256") == local.get("assets", {}).get(path, {}).get("sha256"),
        }
    result = {
        "url": url,
        "host": urlparse(url).hostname,
        "title": title,
        "http": {
            "status": remote_document.get("status"),
            "bytes": remote_document.get("bytes"),
            "sha256": remote_document.get("sha256"),
            "headers": {
                key: remote_document.get("headers", {}).get(key)
                for key in [
                    "strict-transport-security",
                    "x-content-type-options",
                    "referrer-policy",
                    "permissions-policy",
                    "x-frame-options",
                    "cache-control",
                    "content-security-policy",
                ]
            },
        },
        "tls": tls_summary(urlparse(url).hostname),
        "liveDocumentAssets": asset_paths(html),
        "loadedSameOriginAssetPaths": observed_same_origin_assets,
        "remoteAssets": remote_assets,
        "network": {
            "responses": list(responses.values()),
            "failedRequests": failed_requests,
            "ignoredFailedRequests": ignored_failed_requests,
            "badResponses": bad_responses,
            "allEssentialAssetsReturned2xx": all(
                item.get("status") in range(200, 300) for item in remote_assets.values()
            ),
        },
        "console": {"errors": console_errors, "pageErrors": page_errors},
        "desktop": {
            "screenshot": str(desktop_path),
            "workbenchPresent": page.locator("#workbench").count() == 1 or page.locator("#question").count() == 1,
            "newWorkbenchShellPresent": page.locator("#workbench").count() == 1,
        },
        "flows": flows,
        "inferencePolicy": "No Gemini/Nano inference was initiated by this read-only audit.",
    }
    context.close()
    return result


def main() -> int:
    if not (ROOT / "dist" / "index.html").is_file():
        print("dist/index.html is missing; run npm run build first", file=sys.stderr)
        return 2
    local = local_asset_manifest()
    report: dict[str, Any] = {
        "schema": "gapwise.live.site.audit.readonly.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "project": "gapwise-hybrid-2026",
        "root": str(ROOT),
        "output": str(OUT),
        "browserPolicy": "clean Playwright context, no persistent profile, no credentials, no App Check debug token",
        "localDist": local,
        "urls": [],
        "toolingLimitations": [
            "Chrome DevTools MCP was not available, so official performance traces/Core Web Vitals were not collected.",
            "No Gemini/Nano inference was initiated; unavailable-model messaging was checked only as visible UI text/code path.",
        ],
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            for url in LIVE_URLS:
                report["urls"].append(audit_url(browser, url, local))
        finally:
            browser.close()

    local_paths = set(local["assets"])
    for item in report["urls"]:
        live_paths = {
            path
            for path, entry in item["remoteAssets"].items()
            if entry.get("status") in range(200, 300)
        }
        item["comparison"] = {
            "localIndexSha256": local["index.html"]["sha256"],
            "liveIndexSha256": item["http"]["sha256"],
            "indexMatches": item["http"]["sha256"] == local["index.html"]["sha256"],
            "liveOnlyAssets": sorted(live_paths - local_paths),
            "localOnlyAssets": sorted(local_paths - live_paths),
            "commonAssetHashesAllMatch": all(
                entry["hashMatchesLocal"]
                for path, entry in item["remoteAssets"].items()
                if path in local_paths
            ),
        }
    report["summary"] = {
        "liveMatchesLocal": all(
            item["comparison"]["indexMatches"]
            and not item["comparison"]["liveOnlyAssets"]
            and not item["comparison"]["localOnlyAssets"]
            and item["comparison"]["commonAssetHashesAllMatch"]
            for item in report["urls"]
        ),
        "localBuildHealth": "PASS" if local["index.html"].get("sha256") else "FAIL",
        "liveWebsiteHealth": "PASS"
        if all(
            item["http"]["status"] == 200
            and item["network"]["allEssentialAssetsReturned2xx"]
            and not item["console"]["errors"]
            and not item["console"]["pageErrors"]
            for item in report["urls"]
        )
        else "FAIL",
        "buildOrDeploymentMismatch": not all(
            item["comparison"]["indexMatches"]
            and not item["comparison"]["liveOnlyAssets"]
            and not item["comparison"]["localOnlyAssets"]
            and item["comparison"]["commonAssetHashesAllMatch"]
            for item in report["urls"]
        ),
    }
    report_path = OUT / "live_site_audit_readonly.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"report": str(report_path), "summary": report["summary"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
