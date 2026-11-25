import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("appcheck_debug_secret", re.compile(r"APPCHECK_DEBUG_TOKEN\s*=\s*[A-Za-z0-9-]{8,}")),
    ("service_account_json", re.compile(r'"type"\s*:\s*"service_account"')),
    ("local_user_path_leak", re.compile(r"C:(?:\\|\\\\)Users(?:\\|\\\\)(?!Public\b|Default\b|runner\b)[A-Za-z0-9._-]+\b", re.I)),
    ("device_serial_leak", re.compile(r'(?:"adb_serial"\s*:\s*"(?!redacted)[A-Za-z0-9_-]{8,}"|\bserial[:\s`"\']+(?!redacted)[0-9a-z]{12,}\b)', re.I)),
    ("personal_email_leak", re.compile(r"\b[A-Za-z0-9._%+-]+@gmail\.com\b", re.I)),
]

FORBIDDEN_TRACKED_PATHS = [
    ".env",
    ".env.local",
    "google-services.json",
    "serviceAccountKey.json",
    "firebase-adminsdk.json",
    ".keystore",
    ".jks",
]

SKIP_DIRS = {".git", "node_modules", "dist", ".gradle", "build", "scratch", "_venv", "__pycache__", ".firebase"}


def main():
    tracked = subprocess.run(["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, check=True).stdout.splitlines()
    bad_tracked_files = [
        p for p in tracked
        if any(p.endswith(s) for s in FORBIDDEN_TRACKED_PATHS) and not p.endswith(".example")
    ]

    objs = subprocess.run(["git", "rev-list", "--all", "--objects"], cwd=str(ROOT), capture_output=True, text=True, check=True).stdout.splitlines()
    history_bad_paths = []
    history_secret_hits = []
    blob_queries = []
    sha_to_path = {}
    for line in objs:
        parts = line.split(" ", 1)
        sha = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        if path and any(path.endswith(s) for s in FORBIDDEN_TRACKED_PATHS) and not path.endswith(".example"):
            history_bad_paths.append(f"{sha[:8]}:{path}")
        if not path or path.endswith((".png", ".jpg", ".mp4", ".wav", ".webm", ".jar", ".zip", ".ttf", ".woff2", ".apk")):
            continue
        if sha not in sha_to_path:
            sha_to_path[sha] = path
            blob_queries.append(sha)

    blobs_scanned = 0
    if blob_queries:
        proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out_bytes, _ = proc.communicate(("\n".join(blob_queries) + "\n").encode("utf-8"))
        pos = 0
        n_bytes = len(out_bytes)
        while pos < n_bytes:
            nl = out_bytes.find(b"\n", pos)
            if nl < 0:
                break
            header = out_bytes[pos:nl].decode("utf-8", errors="replace").split(" ")
            pos = nl + 1
            if len(header) >= 3 and header[1] == "blob":
                size = int(header[2])
                body = out_bytes[pos:pos + size]
                pos += size + 1
                blobs_scanned += 1
                sha = header[0]
                path = sha_to_path.get(sha, "")
                content = body.decode("utf-8", errors="ignore")
                for pname, rx in PATTERNS:
                    for m in rx.finditer(content):
                        history_secret_hits.append({"commit_obj": sha[:8], "path": path, "pattern": pname, "snippet": m.group(0)[:20] + "..."})
            elif len(header) >= 3 and header[1] in ("tree", "commit", "tag"):
                size = int(header[2])
                pos += size + 1

    wt_secret_hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            f = Path(dirpath) / fn
            rel = f.relative_to(ROOT).as_posix()
            if rel in (".env.local", "android/app/google-services.json", "android/keystore.properties"):
                assert rel not in tracked, f"CRITICAL: gitignored secret file is tracked in git: {rel}"
                continue
            if f.suffix.lower() in (".png", ".jpg", ".mp4", ".webm", ".wav", ".zip", ".apk", ".jar", ".jks", ".keystore", ".log"):
                continue
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for pname, rx in PATTERNS:
                for m in rx.finditer(txt):
                    wt_secret_hits.append({"path": rel, "pattern": pname, "snippet": m.group(0)[:20] + "..."})

    report = {
        "tracked_files_count": len(tracked),
        "forbidden_tracked_files": bad_tracked_files,
        "git_history_blobs_scanned": blobs_scanned,
        "git_history_forbidden_paths": history_bad_paths,
        "git_history_pattern_hits": history_secret_hits,
        "working_tree_tracked_or_unignored_hits": wt_secret_hits,
        "status": "PASS" if not (bad_tracked_files or history_bad_paths or history_secret_hits or wt_secret_hits) else "FAIL_REVIEW",
    }
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
