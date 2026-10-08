import base64
import os
from urllib.parse import quote

import requests


GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 30


def github_headers():
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(path, **kwargs):
    response = requests.get(
        f"{GITHUB_API}{path}", headers=github_headers(),
        timeout=REQUEST_TIMEOUT, **kwargs,
    )
    response.raise_for_status()
    return response.json()


def get_commit(owner: str, repo: str, sha: str):
    return _get(f"/repos/{owner}/{repo}/commits/{quote(sha, safe='')}")


def get_file_at_commit(owner: str, repo: str, path: str, sha: str):
    data = _get(
        f"/repos/{owner}/{repo}/contents/{quote(path, safe='/')}",
        params={"ref": sha},
    )
    if not isinstance(data, dict) or data.get("encoding") != "base64":
        raise ValueError(f"GitHub did not return supported file content for {path}")
    content = base64.b64decode(data["content"])
    if b"\x00" in content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def get_compare(owner: str, repo: str, base_sha: str, head_sha: str):
    comparison = _get(
        f"/repos/{owner}/{repo}/compare/{quote(base_sha, safe='')}...{quote(head_sha, safe='')}"
    )
    if len(comparison.get("files", [])) >= 300:
        raise ValueError("Use a PR number to retrieve a complete large PR file list")
    return comparison


def get_pull_request(owner: str, repo: str, number: int):
    return _get(f"/repos/{owner}/{repo}/pulls/{number}")


def get_pull_request_files(owner: str, repo: str, number: int):
    files = []
    for page in range(1, 31):
        batch = _get(
            f"/repos/{owner}/{repo}/pulls/{number}/files",
            params={"per_page": 100, "page": page},
        )
        files.extend(batch)
        if len(batch) < 100:
            return files
    raise ValueError("PR file list reached GitHub's 3000-file limit; refusing a partial analysis")
