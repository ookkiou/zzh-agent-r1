"""Fetch an immutable official MBPP snapshot; never execute downloaded code."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "data/sources/mbpp"
REPOSITORY = "google-research/google-research"
FILES = ("mbpp/mbpp.jsonl", "mbpp/sanitized-mbpp.json", "mbpp/README.md", "LICENSE")


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "zzh-code-repair-data/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def verify_snapshot(directory=DESTINATION):
    lock = json.loads((directory / "SOURCE_LOCK.json").read_text())
    if not re.fullmatch(r"[0-9a-f]{40}", lock["commit"]):
        raise ValueError("Source commit must be immutable")
    if set(lock["files"]) != {Path(path).name for path in FILES}:
        raise ValueError("Incomplete source lock")
    for name, item in lock["files"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Source checksum mismatch: {name}")
        expected_url = f"https://raw.githubusercontent.com/{REPOSITORY}/{lock['commit']}/{item['path']}"
        if item["url"] != expected_url or item["path"] not in FILES:
            raise ValueError("Source URL differs from pinned official repository")
    return lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify cached files without network")
    parser.add_argument("--commit", help="Optional explicit 40-character upstream commit")
    args = parser.parse_args()
    if args.check or (DESTINATION / "SOURCE_LOCK.json").exists():
        lock = verify_snapshot()
        if args.commit and args.commit != lock["commit"]:
            raise ValueError("Existing source snapshot is frozen; use a new dataset version")
        print(f"PASS official MBPP snapshot {lock['commit']}; 4 file checksums verified")
        return
    commit = args.commit
    if commit is None:
        response = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/commits?path=mbpp&per_page=1"))
        commit = response[0]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid upstream commit")
    assets, files = {}, {}
    for path in FILES:
        url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{path}"
        content = fetch(url)
        name = Path(path).name
        assets[name] = content
        files[name] = {"path": path, "url": url, "sha256": hashlib.sha256(content).hexdigest(),
                       "bytes": len(content)}
    # Validate the response format before saving; code is only treated as text.
    raw = [json.loads(line) for line in assets["mbpp.jsonl"].decode().splitlines() if line.strip()]
    sanitized = json.loads(assets["sanitized-mbpp.json"])
    if len(raw) != 974 or not isinstance(sanitized, list):
        raise ValueError("Unexpected upstream dataset shape")
    lock = {"schema_version": 1, "repository": f"https://github.com/{REPOSITORY}",
            "commit": commit, "files": files, "raw_records": len(raw),
            "sanitized_records": len(sanitized),
            "upstream_repository_license": "Apache-2.0; exact upstream LICENSE included",
            "downloaded_code_executed": False}
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        (DESTINATION / name).write_bytes(content)
    (DESTINATION / "SOURCE_LOCK.json").write_text(json.dumps(lock, indent=2) + "\n")
    verify_snapshot()
    print(f"Saved official MBPP snapshot {commit}; {len(raw)} raw / {len(sanitized)} sanitized records")


if __name__ == "__main__":
    main()
