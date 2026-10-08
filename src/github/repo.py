import base64
import os
import requests


GITHUB_API = "https://api.github.com"


def github_headers():
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }


def get_commit(owner: str, repo: str, sha: str):

    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}"

    response = requests.get(
        url,
        headers=github_headers(),
    )

    response.raise_for_status()

    return response.json()


def get_file_at_commit(
    owner: str,
    repo: str,
    path: str,
    sha: str,
):

    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"

    response = requests.get(
        url,
        params={"ref": sha},
        headers=github_headers(),
    )

    response.raise_for_status()

    data = response.json()

    return base64.b64decode(
        data["content"]
    ).decode("utf-8")


def get_compare(
    owner: str,
    repo: str,
    base_sha: str,
    head_sha: str,
):

    url = (
        f"{GITHUB_API}/repos/{owner}/{repo}"
        f"/compare/{base_sha}...{head_sha}"
    )

    response = requests.get(
        url,
        headers=github_headers(),
    )

    response.raise_for_status()

    return response.json()