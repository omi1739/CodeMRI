from __future__ import annotations

import re
from dataclasses import dataclass

# Strict: only https://github.com/{owner}/{repo}, tolerating .git, trailing slash
# and an optional /tree/<branch> (or /tree/<branch>/<path>) suffix.
_GITHUB_URL_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9._-]{1,100})"
    r"(?:\.git)?/*"
    r"(?:tree/(?P<ref>[^#\s?]+(?:/[^#\s?]+)*))?"
    r"/?$"
)

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class InvalidRepoUrl(ValueError):
    pass


@dataclass(frozen=True)
class ParsedRepoUrl:
    owner: str
    name: str
    ref: str | None = None  # branch or tag from /tree/<ref>, if present

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_github_url(url: str) -> ParsedRepoUrl:
    if not isinstance(url, str):
        raise InvalidRepoUrl("URL must be a string")
    cleaned = url.strip()
    if len(cleaned) > 500:
        raise InvalidRepoUrl("URL is too long")
    if any(ch in cleaned for ch in ("\n", "\r", "\t", " ", '"', "'")):
        raise InvalidRepoUrl("URL contains invalid characters")

    match = _GITHUB_URL_RE.match(cleaned)
    if not match:
        raise InvalidRepoUrl(
            "Not a valid public GitHub repository URL. "
            "Expected form: https://github.com/{owner}/{repo}"
        )

    owner = match.group("owner")
    name = match.group("repo").removesuffix(".git")
    if not _OWNER_RE.match(owner) or not _REPO_RE.match(name):
        raise InvalidRepoUrl("Invalid owner or repository name")
    if name in {".", ".."}:
        raise InvalidRepoUrl("Invalid repository name")

    ref = match.group("ref")
    return ParsedRepoUrl(owner=owner, name=name, ref=ref)
