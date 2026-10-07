from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path

SOURCE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte")
ENTRY_NAMES = {
    "index",
    "main",
    "app",
    "server",
    "cli",
    "entry",
    "bootstrap",
    # framework entry conventions (Next.js, Remix, SvelteKit, etc.)
    "page",
    "layout",
    "route",
    "loading",
    "error",
    "not-found",
    "not_found",
    "template",
    "default",
    "middleware",
    "proxy",
    "global-error",
    "$",
    "@",
}

_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|export\s+[\w*{}\s,]+\s+from\s+|require\()\s*['"]([^'"]+)['"]"""
)
_MAX_FILES = 2000
_MAX_BYTES = 512 * 1024


def is_source_path(path: str) -> bool:
    return path.lower().endswith(SOURCE_EXTS)


def is_entry_path(path: str) -> bool:
    name = posixpath.basename(path).lower()
    stem = name.split(".")[0] if "." in name else name
    if stem in ENTRY_NAMES:
        return True
    if name == "next.config" or name.startswith(("next.config.", "next-env.")):
        return True
    if ".config." in name or name.endswith(".config") or name.endswith(".d.ts"):
        return True
    return False


_SKIP_PACKAGE_DIRS = {"node_modules", ".next", "dist", "build", "coverage", ".git", "vendor"}


def locate_package_json(root: Path) -> tuple[Path, dict]:
    """Find the package.json this repo is built on.

    Prefers the repository root (single-project repos), otherwise falls back to the
    shallowest package.json under a workspace subdirectory (monorepos e.g. apps/,
    packages/). Returns (directory, parsed json); empty dict when none is found.
    """
    root_json = root / "package.json"
    if root_json.is_file():
        try:
            return root, json.loads(root_json.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError):
            return root, {}

    candidates: list[tuple[int, Path]] = []
    if root.is_dir():
        for path in root.rglob("package.json"):
            parts = set(p.lower() for p in path.parts)
            if parts & _SKIP_PACKAGE_DIRS:
                continue
            depth = len(path.relative_to(root).parts)
            candidates.append((depth, path))
    if not candidates:
        return root, {}
    candidates.sort(key=lambda item: (item[0], item[1].as_posix()))
    chosen = candidates[0][1]
    try:
        data = json.loads(chosen.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        data = {}
    return chosen.parent, data


def import_specifiers(text: str) -> list[str]:
    return _IMPORT_RE.findall(text)


def is_local_specifier(spec: str) -> bool:
    return spec.startswith((".", "/"))


def package_of_specifier(spec: str) -> str | None:
    if is_local_specifier(spec) or spec.startswith("#"):
        return None
    if spec.startswith("@"):
        parts = spec.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else None
    return spec.split("/")[0]


def iter_source_files(root: Path, inventory: list[dict]):
    """Yield (path, rel_path, text) for scannable source files, bounded by caps."""
    scanned = 0
    for entry in inventory:
        if scanned >= _MAX_FILES:
            return
        rel = entry.get("path") or ""
        if not is_source_path(rel):
            continue
        if entry.get("is_ignored") or entry.get("is_generated"):
            continue
        if entry.get("size_bytes", 0) > _MAX_BYTES:
            continue
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        yield path, rel, text


def resolve_relative_import(from_file: str, spec: str, file_set: set[str]) -> str | None:
    if not (spec.startswith(".") or spec.startswith("/")):
        return None
    base = posixpath.dirname(from_file) or "."
    if spec.startswith("/"):
        target = posixpath.normpath(spec.lstrip("/"))
    else:
        target = posixpath.normpath(posixpath.join(base, spec))

    candidates = [target]
    for ext in SOURCE_EXTS:
        if spec.endswith(("/index", "/index.js", "/index.ts")):
            break
        candidates.extend([target + ext, posixpath.join(target, "index" + ext)])
    candidates.append(posixpath.join(target, "index.js"))
    candidates.append(posixpath.join(target, "index.ts"))

    for candidate in dict.fromkeys(candidates):
        if candidate in file_set:
            return candidate
    return None


# --- function / complexity estimation (heuristic; never executed code) ----------

_FUNC_OPEN_RE = re.compile(r"\b(?:function\b[^{]*|\b(?:const|let|var|async)\s+[\w$]+\s*=\s*(?:async\s*)?(?:\([^)]*\)|[^={\n]+)\s*=>\s*|\b(?:async\s+)?[\w$]+\s*\([^)]*\))\s*\{")


def function_blocks(text: str) -> list[tuple[str, int, int]]:
    """Return (name, complexity_estimate, loc) for function-looking blocks."""
    results: list[tuple[str, int, int]] = []
    for match in _FUNC_OPEN_RE.finditer(text):
        start = match.start()
        open_brace = text.find("{", match.start() + 1)
        if open_brace < 0:
            continue
        depth = 0
        i = open_brace
        in_str: str | None = None
        escaped = False
        while i < len(text):
            char = text[i]
            if in_str:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == in_str:
                    in_str = None
            else:
                if char in "\"'`":
                    in_str = char
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
        body = text[open_brace : i + 1]
        complexity = _estimate_complexity(body)
        loc = body.count("\n") + 1
        name = _function_name(text[match.start() : open_brace])
        results.append((name, complexity, loc))
    return results


_BRANCH_RE = re.compile(r"(\bif\b|\bfor\b|\bwhile\b|\bswitch\b|\bcase\b|\bcatch\b|\belse\b|&&|\|\||\?\?|\?\.)")


def _estimate_complexity(body: str) -> int:
    return 1 + len(_BRANCH_RE.findall(body))


def _function_name(prefix: str) -> str:
    clean = re.sub(r"async|function|=>|\{|\([^)]*\)", "", prefix).strip()
    clean = clean.replace("=", "")
    clean = clean.strip()
    return clean or "anonymous"


def file_complexity_estimate(text: str) -> int:
    return max((c for _, c, _ in function_blocks(text)), default=0)


# --- unused-import / variable detection (lexical only) --------------------------

_IMPORT_LINE_RE = re.compile(
    r"""^\s*import\s+(?:type\s+)?(?:(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\})?|(\*\s*as\s+([\w$]+)))\s+from\s+['"][^'"]+['"]\s*;?\s*$|^\s*import\s+['"][^'"]+['"]\s*;?\s*$"""
)
_REQUIRE_RE = re.compile(
    r"""^\s*(?:const|let|var)\s+([\w$]+)\s*=\s*require\s*\(\s*['"][^'"]+['"]\s*\)\s*;?\s*$"""
)


def unused_import_names(text: str) -> list[str]:
    """Names imported once and never referenced again in the file."""
    unused: list[str] = []

    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        match = _IMPORT_LINE_RE.match(stripped)
        if not match:
            match = _REQUIRE_RE.match(stripped)
            if not match:
                continue
            names = [match.group(1)]
            rest = "\n".join(lines[:index] + lines[index + 1 :])
        else:
            if match.group(1):  # import Default [, {named}] from
                names = [match.group(1)]
                if match.group(2):
                    names.extend(_named_imports(match.group(2)))
            elif match.group(2):  # import { a, b }
                names = _named_imports(match.group(2))
            elif match.group(4):  # import * as ns
                names = [match.group(4)]
            else:  # side-effect only
                continue
            rest = "\n".join(lines[:index] + lines[index + 1 :])

        for name in names:
            if not name:
                continue
            pattern = re.compile(rf"(?<![\w$]){re.escape(name)}(?![\w$])")
            if not pattern.search(rest):
                unused.append(name)

    return unused


def _named_imports(clause: str) -> list[str]:
    names: list[str] = []
    for part in clause.split(","):
        part = part.strip()
        if not part:
            continue
        # TypeScript inline type specifiers: `{ type Foo }`, `{ type Foo as Bar }`
        if part.startswith("type "):
            part = part[5:].lstrip()
        elif part in ("type", "typeof"):
            continue
        alias = part.split(" as ")[-1].strip()
        if alias:
            names.append(alias)
    return names


def duplicated_line_count(text: str) -> int:
    """Estimate how many non-trivial lines are duplicated in ≥5-line blocks."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    n = len(lines)
    if n < 10:
        return 0
    window = 5
    seen: dict[tuple[str, ...], list[int]] = {}
    for i in range(0, n - window + 1):
        key = tuple(lines[i : i + window])
        seen.setdefault(key, []).append(i)
    duplicated = 0
    for starts in seen.values():
        if len(starts) >= 2:
            duplicated += window * len(starts)
    return duplicated


def count_importers(inventory: list[dict], relatives: dict[str, set[str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for importers in relatives.values():
        for target in importers:
            counts[target] = counts.get(target, 0) + 1
    return counts