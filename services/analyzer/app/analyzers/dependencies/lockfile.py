from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

LOCKFILES = {
    "package-lock.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
    "npm-shrinkwrap.json": "npm",
}


@dataclass
class DeclaredDependency:
    name: str
    version_range: str
    dev: bool


@dataclass
class DependencyInfo:
    declared: list[DeclaredDependency] = field(default_factory=list)
    resolved: dict[str, str] = field(default_factory=dict)  # name -> exact version
    lockfiles: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    scripts: dict[str, str] = field(default_factory=dict)
    engines: dict[str, str] = field(default_factory=dict)


def read_package_json(root: Path) -> dict:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return {}


def detect_lockfiles(root: Path) -> list[str]:
    return [name for name in LOCKFILES if (root / name).is_file()]


def _parse_package_lock(root: Path, info: DependencyInfo) -> None:
    path = root / "package-lock.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return

    packages = data.get("packages")
    if isinstance(packages, dict):
        for key, value in packages.items():
            if key == "" or not isinstance(value, dict):
                continue
            name = key.split("node_modules/")[-1]
            version = value.get("version")
            if name and isinstance(version, str):
                info.resolved.setdefault(name, version)
        return

    dependencies = data.get("dependencies", {})
    if isinstance(dependencies, dict):
        for name, value in dependencies.items():
            if isinstance(value, dict) and isinstance(value.get("version"), str):
                info.resolved.setdefault(name, value["version"])


_YARN_BLOCK_RE = re.compile(r'^"?([^"\n]+?)@[^:\n]+"?:\s*$', re.MULTILINE)
_YARN_VERSION_RE = re.compile(r'^\s+version\s+"([^"]+)"', re.MULTILINE)


def _parse_yarn_lock(root: Path, info: DependencyInfo) -> None:
    path = root / "yarn.lock"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return

    blocks = _YARN_BLOCK_RE.split(text)
    # split gives [pre, name/spec, body, name/spec, body, ...]
    for index in range(1, len(blocks) - 1, 2):
        specs = blocks[index]
        body = blocks[index + 1]
        version_match = _YARN_VERSION_RE.search(body)
        if not version_match:
            continue
        version = version_match.group(1)
        for spec in specs.split(", "):
            spec = spec.strip().strip('"')
            if "@" not in spec:
                continue
            name = spec[1:] if spec.startswith("@") else spec.split("@")[0]
            if spec.startswith("@"):
                name = spec.rsplit("@", 1)[0]
            if name:
                info.resolved.setdefault(name, version)


def _parse_pnpm_lock(root: Path, info: DependencyInfo) -> None:
    path = root / "pnpm-lock.yaml"
    if not path.is_file():
        return
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except (yaml.YAMLError, OSError):
        return
    if not isinstance(data, dict):
        return
    packages = data.get("packages")
    if isinstance(packages, dict):
        for key in packages:
            if not isinstance(key, str) or not key.startswith("/"):
                continue
            bare = key[1:].split("(")[0]
            if "@" not in bare:
                continue
            name, _, version = bare.rpartition("@")
            if name and version:
                info.resolved.setdefault(name, version)


def collect_dependencies(root: Path) -> DependencyInfo:
    info = DependencyInfo()
    package_json = read_package_json(root)
    if not package_json:
        return info

    for name, version in (package_json.get("dependencies") or {}).items():
        if isinstance(version, str):
            info.declared.append(DeclaredDependency(name=name, version_range=version, dev=False))
    for name, version in (package_json.get("devDependencies") or {}).items():
        if isinstance(version, str):
            info.declared.append(DeclaredDependency(name=name, version_range=version, dev=True))

    info.scripts = {
        k: v for k, v in (package_json.get("scripts") or {}).items() if isinstance(v, str)
    }
    info.engines = {
        k: v for k, v in (package_json.get("engines") or {}).items() if isinstance(v, str)
    }

    info.lockfiles = detect_lockfiles(root)
    info.package_managers = sorted({LOCKFILES[name] for name in info.lockfiles})

    _parse_package_lock(root, info)
    _parse_yarn_lock(root, info)
    _parse_pnpm_lock(root, info)
    return info


_EXACT_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+(?:[-+][0-9A-Za-z.-]+)?)$")


def exact_version_from_range(version_range: str) -> str | None:
    match = _EXACT_RE.match(version_range.strip())
    return match.group(0).lstrip("v") if match else None


def base_major(version: str | None) -> int | None:
    if not version:
        return None
    match = re.match(r"^v?(\d+)", version.strip())
    return int(match.group(1)) if match else None


def base_version(version_range: str) -> str | None:
    """Best-effort numeric base from a range like ^1.2.3 -> 1.2.3."""
    cleaned = re.sub(r"^[\^~>=<\s*v]+", "", version_range.strip())
    match = re.match(r"(\d+(?:\.\d+){0,2})", cleaned)
    return match.group(1) if match else None
