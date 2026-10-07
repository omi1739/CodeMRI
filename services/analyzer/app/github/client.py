from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


class GitHubError(Exception):
    """Base class for GitHub intake errors; message is safe to show to the user."""


class RepoNotFoundError(GitHubError):
    def __init__(self) -> None:
        super().__init__("Repository not found (it may be private or misspelled).")


class RepoPrivateError(GitHubError):
    def __init__(self) -> None:
        super().__init__("Only public repositories can be scanned.")


class RepoTooLargeError(GitHubError):
    def __init__(self, size_kb: int) -> None:
        super().__init__(
            f"Repository is too large to scan ({size_kb} KB > {settings.max_repo_size_mb} MB limit)."
        )


class RateLimitedError(GitHubError):
    def __init__(self) -> None:
        super().__init__("GitHub API rate limit reached. Try again later.")


class NetworkError(GitHubError):
    def __init__(self) -> None:
        super().__init__("Could not reach GitHub. Check your network and try again.")


@dataclass(frozen=True)
class RepoMetadata:
    owner: str
    name: str
    full_name: str
    html_url: str
    default_branch: str
    visibility: str
    primary_language: str | None
    stars: int
    size_kb: int
    archived: bool
    pushed_at: str | None


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CodeMRI-scanner",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise RepoNotFoundError()
    if response.status_code == 403 and "rate limit" in response.text.lower():
        raise RateLimitedError()
    if response.status_code in (401, 403):
        raise RepoPrivateError()
    if response.status_code >= 500:
        raise NetworkError()
    response.raise_for_status()


def get_repo_metadata(owner: str, name: str) -> RepoMetadata:
    url = f"{settings.github_api_base}/repos/{owner}/{name}"
    try:
        response = httpx.get(url, headers=_headers(), timeout=30.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        log.warning("github_metadata_failed owner=%s name=%s error=%s", owner, name, exc)
        raise NetworkError() from exc

    _raise_for_status(response)
    data = response.json()

    if data.get("private"):
        raise RepoPrivateError()
    size_kb = int(data.get("size") or 0)
    if size_kb > settings.max_repo_size_mb * 1024:
        raise RepoTooLargeError(size_kb)

    return RepoMetadata(
        owner=data.get("owner", {}).get("login", owner),
        name=data.get("name", name),
        full_name=data.get("full_name", f"{owner}/{name}"),
        html_url=data.get("html_url", f"https://github.com/{owner}/{name}"),
        default_branch=data.get("default_branch") or "main",
        visibility="private" if data.get("private") else "public",
        primary_language=data.get("language"),
        stars=int(data.get("stargazers_count") or 0),
        size_kb=size_kb,
        archived=bool(data.get("archived")),
        pushed_at=data.get("pushed_at"),
    )


def get_branch_sha(owner: str, name: str, branch: str) -> str:
    url = f"{settings.github_api_base}/repos/{owner}/{name}/commits/{branch}"
    try:
        response = httpx.get(url, headers=_headers(), timeout=30.0, follow_redirects=True)
    except httpx.HTTPError as exc:
        log.warning("github_commit_failed ref=%s error=%s", branch, exc)
        raise NetworkError() from exc

    _raise_for_status(response)
    sha = response.json().get("sha")
    if not sha:
        raise GitHubError("Could not resolve the commit SHA for the requested branch.")
    return sha


def get_recent_commits(owner: str, name: str, branch: str, limit: int = 30) -> list[dict]:
    """Return up to `limit` recent commits: [{sha, message, author, date}]."""
    url = f"{settings.github_api_base}/repos/{owner}/{name}/commits"
    params = {"sha": branch, "per_page": min(max(limit, 1), 100)}
    try:
        response = httpx.get(url, headers=_headers(), params=params, timeout=30.0)
    except httpx.HTTPError:
        return []
    if response.status_code != 200:
        return []
    commits = []
    for item in response.json()[:limit]:
        commit = item.get("commit", {})
        commits.append(
            {
                "sha": item.get("sha"),
                "message": (commit.get("message") or "").split("\n")[0][:200],
                "author": (commit.get("author") or {}).get("name"),
                "date": (commit.get("author") or {}).get("date"),
            }
        )
    return commits
