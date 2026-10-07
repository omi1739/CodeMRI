from __future__ import annotations

import logging
import shutil
import tarfile
from pathlib import Path, PurePosixPath

import httpx

from app.core.config import settings
from app.github.client import GitHubError, NetworkError, RateLimitedError, _headers

log = logging.getLogger(__name__)

MAX_TARBALL_BYTES = settings.max_repo_size_mb * 1024 * 1024 * 2  # compressed upper bound


class ExtractionError(GitHubError):
    pass


def download_tarball(owner: str, name: str, sha: str, dest: Path) -> Path:
    """Download the repo tarball at an exact commit. Raises GitHubError on failure."""
    url = f"{settings.github_api_base}/repos/{owner}/{name}/tarball/{sha}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        with httpx.stream(
            "GET", url, headers=_headers(), timeout=60.0, follow_redirects=True
        ) as response:
            if response.status_code == 403 and "rate limit" in response.text.lower():
                raise RateLimitedError()
            if response.status_code == 404:
                raise GitHubError("Repository or commit not found on GitHub.")
            if response.status_code >= 400:
                raise NetworkError()

            written = 0
            with dest.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=65536):
                    written += len(chunk)
                    if written > MAX_TARBALL_BYTES:
                        handle.close()
                        dest.unlink(missing_ok=True)
                        raise ExtractionError("Downloaded archive exceeded the size limit.")
                    handle.write(chunk)
    except httpx.HTTPError as exc:
        dest.unlink(missing_ok=True)
        log.warning("tarball_download_failed sha=%s error=%s", sha, exc)
        raise NetworkError() from exc

    if written == 0:
        dest.unlink(missing_ok=True)
        raise ExtractionError("Downloaded archive was empty.")
    return dest


def safe_extract_tarball(tarball: Path, dest_dir: Path) -> Path:
    """Extract a GitHub tarball defensively.

    Rejects: absolute paths, '..' traversal, symlinks/hardlinks, non-regular files.
    Caps: total files, per-file size, total extracted bytes.
    Returns the single top-level directory GitHub wraps the archive in.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    top_level: set[str] = set()

    try:
        with tarfile.open(tarball, "r:gz") as tar:
            for member in tar:
                if file_count >= settings.max_files:
                    raise ExtractionError(f"Archive has more than {settings.max_files} files.")

                posix = PurePosixPath(member.name)
                parts = [p for p in posix.parts if p not in (".",)]
                if posix.is_absolute() or not parts:
                    raise ExtractionError(f"Unsafe path in archive: {member.name}")
                if any(part == ".." for part in parts):
                    raise ExtractionError(f"Path traversal in archive: {member.name}")
                if member.issym() or member.islnk():
                    continue  # skip links entirely
                if not (member.isfile() or member.isdir()):
                    continue  # skip devices, fifos, etc.

                top_level.add(parts[0])

                relative = Path(*parts[1:]) if len(parts) > 1 else None
                if member.isdir():
                    if relative is not None:
                        (dest_dir / relative).mkdir(parents=True, exist_ok=True)
                    continue
                if relative is None:
                    continue

                if member.size > settings.max_file_size_kb * 1024:
                    continue  # skip oversized files, keep scanning
                total_bytes += member.size
                if total_bytes > settings.max_extracted_bytes:
                    raise ExtractionError("Archive would extract to more than the size limit.")

                target = dest_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                source = tar.extractfile(member)
                if source is None:
                    continue
                with source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle, length=65536)
                file_count += 1
    except tarfile.TarError as exc:
        raise ExtractionError("Archive is corrupt or not a gzip tarball.") from exc
    finally:
        tarball.unlink(missing_ok=True)

    if file_count == 0:
        raise ExtractionError("Archive contained no files.")
    if len(top_level) == 1:
        # GitHub tarballs nest everything in <owner>-<repo>-<sha>/
        root = dest_dir / next(iter(top_level))
        if root.is_dir():
            return root

    return dest_dir
