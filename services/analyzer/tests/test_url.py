from __future__ import annotations

import pytest

from app.github.url import InvalidRepoUrl, parse_github_url


@pytest.mark.parametrize(
    "url, owner, name, ref",
    [
        ("https://github.com/owner/repo", "owner", "repo", None),
        ("https://github.com/owner/repo/", "owner", "repo", None),
        ("https://github.com/owner/repo.git", "owner", "repo", None),
        ("https://github.com/owner/repo.git/", "owner", "repo", None),
        ("http://github.com/owner/repo", "owner", "repo", None),
        ("https://www.github.com/owner/repo", "owner", "repo", None),
        ("https://github.com/owner/repo/tree/main", "owner", "repo", "main"),
        ("https://github.com/owner/repo/tree/feature/x/y", "owner", "repo", "feature/x/y"),
        ("https://github.com/owner-name/repo.name.js", "owner-name", "repo.name.js", None),
        ("  https://github.com/owner/repo  ", "owner", "repo", None),
    ],
)
def test_valid_urls(url: str, owner: str, name: str, ref: str | None) -> None:
    parsed = parse_github_url(url)
    assert parsed.owner == owner
    assert parsed.name == name
    assert parsed.ref == ref


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "https://example.com/owner/repo",
        "https://github.com/owner",
        "https://github.com/",
        "git@github.com:owner/repo.git",
        "https://github.com/owner/repo/issues/1",
        "https://evil.com/https://github.com/owner/repo",
        "https://github.com/owner/repo\nhttps://evil.com",
        "https://github.com/owner/repo#readme",
        "ftp://github.com/owner/repo",
        "https://github.com/-bad/repo",
        "x" * 600,
    ],
)
def test_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidRepoUrl):
        parse_github_url(url)


def test_full_name() -> None:
    assert parse_github_url("https://github.com/a/b").full_name == "a/b"
