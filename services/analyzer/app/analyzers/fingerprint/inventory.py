from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "bower_components",
    "vendor",
    "dist",
    "build",
    "out",
    "coverage",
    ".next",
    ".nuxt",
    ".output",
    ".turbo",
    ".cache",
    ".parcel-cache",
    "target",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "tmp",
    "temp",
}

IGNORED_FOR_LOC = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "npm-shrinkwrap.json",
    "Cargo.lock",
    "poetry.lock",
    "composer.lock",
}

GENERATED_HINTS = (".min.js", ".min.css", ".bundle.js", ".generated.", ".pb.go", "_pb2.py")

LANGUAGES = {
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".py": "Python",
    ".rb": "Ruby",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".php": "PHP",
    ".swift": "Swift",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "Less",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".md": "Markdown",
    ".toml": "TOML",
    ".xml": "XML",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".graphql": "GraphQL",
    ".prisma": "Prisma",
    ".dockerfile": "Dockerfile",
}

TEST_PATTERNS = (".test.", ".spec.", "_test.", "_spec.", "/tests/", "/test/", "__tests__", "/e2e/", "/cypress/")


@dataclass
class FileEntry:
    path: str
    language: str | None
    loc: int
    size_bytes: int
    is_test: bool
    is_generated: bool
    is_ignored: bool


def _is_test_path(rel: str) -> bool:
    lowered = rel.replace("\\", "/").lower()
    prefixed = f"/{lowered}"
    if any(pattern in prefixed or pattern in lowered for pattern in TEST_PATTERNS):
        return True
    return lowered.startswith(("tests/", "test/", "__tests__/", "e2e/", "cypress/"))


def _looks_generated(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in GENERATED_HINTS)


def _is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def _count_loc(path: Path, *, count_loc: bool) -> int:
    if not count_loc:
        return 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.strip())


def build_inventory(source_dir: Path, max_files: int, max_file_size_kb: int) -> list[FileEntry]:
    entries: list[FileEntry] = []
    root = source_dir.resolve()

    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(
            d
            for d in dirs
            if d not in IGNORE_DIRS and not (d.startswith(".git") and d not in {".github"})
        )
        for filename in sorted(files):
            if len(entries) >= max_files:
                return entries

            path = Path(current) / filename
            try:
                rel = path.relative_to(root).as_posix()
                size = path.stat().st_size
            except (OSError, ValueError):
                continue

            language = LANGUAGES.get(path.suffix.lower()) or (
                "Dockerfile" if filename.lower() == "dockerfile" else None
            )
            generated = _looks_generated(filename) or "generated" in rel.lower()
            ignored = filename in IGNORED_FOR_LOC or path.suffix.lower() in {".min.js", ".min.css"}
            binary = _is_binary(path)
            oversized = size > max_file_size_kb * 1024

            loc = 0 if (binary or ignored or oversized) else _count_loc(path, count_loc=True)

            entries.append(
                FileEntry(
                    path=rel,
                    language=language,
                    loc=loc,
                    size_bytes=size,
                    is_test=_is_test_path(rel),
                    is_generated=generated,
                    is_ignored=ignored or binary,
                )
            )
    return entries


def inventory_as_dicts(entries: list[FileEntry]) -> list[dict]:
    return [asdict(entry) for entry in entries]
