from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from app.github.fetch import ExtractionError, safe_extract_tarball


def _make_tar(path: Path, entries: list[tuple[str, bytes, int]]) -> Path:
    """entries: (name, content, tarinfo_type) where type: 0=file, 1=dir, 2=symlink."""
    with tarfile.open(path, "w:gz") as tar:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name=name)
            if kind == 1:
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            elif kind == 2:
                info.type = tarfile.SYMTYPE
                info.linkname = content.decode() if content else "/etc/passwd"
                tar.addfile(info)
            else:
                info.size = len(content)
                info.mode = 0o644
                tar.addfile(info, io.BytesIO(content))
    return path


def test_safe_extract_normal_archive(tmp_path: Path) -> None:
    tarball = _make_tar(
        tmp_path / "ok.tar.gz",
        [
            ("repo-abc123/", b"", 1),
            ("repo-abc123/package.json", b'{"name": "x"}', 0),
            ("repo-abc123/src/", b"", 1),
            ("repo-abc123/src/index.js", b"module.exports = 1;", 0),
        ],
    )
    root = safe_extract_tarball(tarball, tmp_path / "out")
    assert (root / "package.json").is_file()
    assert (root / "src" / "index.js").is_file()
    assert not tarball.exists()  # tarball cleaned up


def test_rejects_path_traversal(tmp_path: Path) -> None:
    tarball = _make_tar(
        tmp_path / "evil.tar.gz",
        [("repo/../../evil.txt", b"pwned", 0)],
    )
    with pytest.raises(ExtractionError):
        safe_extract_tarball(tarball, tmp_path / "out")
    assert not (tmp_path / "evil.txt").exists()


def test_rejects_absolute_path(tmp_path: Path) -> None:
    tarball = _make_tar(tmp_path / "abs.tar.gz", [("/etc/passwd", b"root", 0)])
    with pytest.raises(ExtractionError):
        safe_extract_tarball(tarball, tmp_path / "out")


def test_skips_symlinks(tmp_path: Path) -> None:
    tarball = _make_tar(
        tmp_path / "sym.tar.gz",
        [
            ("repo/", b"", 1),
            ("repo/link", b"/etc/passwd", 2),
            ("repo/file.txt", b"ok", 0),
        ],
    )
    root = safe_extract_tarball(tarball, tmp_path / "out")
    assert not (root / "link").exists()
    assert (root / "file.txt").read_text() == "ok"


def test_file_count_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_files", 3)
    entries = [("repo/", b"", 1)] + [(f"repo/f{i}.txt", b"x", 0) for i in range(10)]
    tarball = _make_tar(tmp_path / "many.tar.gz", entries)
    with pytest.raises(ExtractionError):
        safe_extract_tarball(tarball, tmp_path / "out")


def test_single_file_size_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_file_size_kb", 1)
    tarball = _make_tar(
        tmp_path / "big.tar.gz",
        [
            ("repo/", b"", 1),
            ("repo/big.bin", b"A" * 4096, 0),
            ("repo/small.txt", b"ok", 0),
        ],
    )
    root = safe_extract_tarball(tarball, tmp_path / "out")
    assert not (root / "big.bin").exists()
    assert (root / "small.txt").is_file()


def test_corrupt_archive(tmp_path: Path) -> None:
    tarball = tmp_path / "bad.tar.gz"
    tarball.write_bytes(b"this is not a gzip stream")
    with pytest.raises(ExtractionError):
        safe_extract_tarball(tarball, tmp_path / "out")


def test_empty_archive(tmp_path: Path) -> None:
    tarball = _make_tar(tmp_path / "empty.tar.gz", [])
    with pytest.raises(ExtractionError):
        safe_extract_tarball(tarball, tmp_path / "out")
