from __future__ import annotations

import json
from pathlib import Path

from app.analyzers.base import Evidence, Finding, ScanContext
from app.analyzers.fingerprint.inventory import build_inventory, inventory_as_dicts

FRAMEWORKS = {
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "angular": "Angular",
    "express": "Express",
    "fastify": "Fastify",
    "koa": "Koa",
    "nestjs": "NestJS",
    "@nestjs/core": "NestJS",
    "hono": "Hono",
    "gatsby": "Gatsby",
    "remix": "Remix",
    "nuxt": "Nuxt",
    "vite": "Vite",
    "webpack": "Webpack",
    "parcel": "Parcel",
    "electron": "Electron",
}

DATABASE_LIBS = {
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql2": "MySQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "mongoose": "MongoDB",
    "redis": "Redis",
    "ioredis": "Redis",
    "sqlite3": "SQLite",
    "better-sqlite3": "SQLite",
    "prisma": "Prisma",
    "@prisma/client": "Prisma",
    "drizzle-orm": "Drizzle",
    "typeorm": "TypeORM",
    "sequelize": "Sequelize",
    "@supabase/supabase-js": "Supabase",
    "knex": "Knex",
}

TEST_FRAMEWORKS = {
    "jest": "Jest",
    "vitest": "Vitest",
    "mocha": "Mocha",
    "jasmine": "Jasmine",
    "ava": "AVA",
    "tape": "tape",
    "@playwright/test": "Playwright",
    "cypress": "Cypress",
    "@testing-library/react": "Testing Library",
}

PACKAGE_MANAGER_FILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
]


def _read_package_json(root: Path) -> dict:
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}


def _present(dependencies: dict, mapping: dict[str, str]) -> list[str]:
    found = []
    for dep in dependencies:
        base = dep.split("/")[0] if dep.startswith("@") and dep.count("/") == 1 else dep
        for key, label in mapping.items():
            if (dep == key or base == key) and label not in found:
                found.append(label)
    return sorted(found)


def _detect(root: Path, inventory: list[dict], package_json: dict) -> dict:
    deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
    paths = {entry["path"] for entry in inventory}
    languages = sorted({e["language"] for e in inventory if e.get("language") and e.get("loc", 0) > 0})

    package_manager = next(
        (name for file, name in PACKAGE_MANAGER_FILES if (root / file).is_file()), None
    )

    flags = {
        "typescript": (root / "tsconfig.json").is_file()
        or any(lang == "TypeScript" for lang in languages),
        "docker": any(p.lower() == "dockerfile" for p in paths)
        or any(p.endswith(("docker-compose.yml", "docker-compose.yaml")) for p in paths),
        "ci": any(
            p.startswith(".github/workflows/") or p in {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile"}
            for p in paths
        ),
        "env_example": any(p in {".env.example", ".env.sample", ".env.template"} for p in paths),
        "license": any(Path(p).name.upper().startswith("LICENSE") for p in paths),
        "readme": any(Path(p).name.upper().startswith("README") for p in paths),
    }

    test_files = [e for e in inventory if e.get("is_test")]
    total_loc = sum(int(e.get("loc") or 0) for e in inventory)

    return {
        "package_json_found": bool(package_json),
        "package_manager": package_manager,
        "languages": languages,
        "frameworks": _present(deps, FRAMEWORKS),
        "databases": _present(deps, DATABASE_LIBS),
        "test_frameworks": _present(deps, TEST_FRAMEWORKS),
        "total_loc": total_loc,
        "file_count": len(inventory),
        "test_file_count": len(test_files),
        "scripts": sorted(package_json.get("scripts", {}).keys()),
        **flags,
    }


class FingerprintAnalyzer:
    name = "fingerprint"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        root = Path(ctx.source_dir)
        inventory = ctx.inventory or build_inventory(
            root, max_files=20000, max_file_size_kb=1024
        )
        ctx.inventory = inventory_as_dicts(inventory)
        package_json = _read_package_json(root)
        fingerprint = _detect(root, ctx.inventory, package_json)
        ctx.fingerprint = fingerprint

        stack_bits: list[str] = []
        if fingerprint["frameworks"]:
            stack_bits.extend(fingerprint["frameworks"])
        elif fingerprint["typescript"]:
            stack_bits.append("TypeScript")
        if fingerprint["typescript"] and fingerprint["frameworks"]:
            stack_bits.append("TypeScript")
        if fingerprint["databases"]:
            stack_bits.append("+".join(fingerprint["databases"]))
        if fingerprint["test_frameworks"]:
            stack_bits.extend(fingerprint["test_frameworks"])
        if fingerprint["docker"]:
            stack_bits.append("Docker")
        if fingerprint["ci"]:
            stack_bits.append("CI")

        findings: list[Finding] = []

        if not fingerprint["package_json_found"]:
            findings.append(
                Finding(
                    category="fingerprint",
                    rule_id="FP-002",
                    title="No Node.js project detected",
                    severity="info",
                    confidence="high",
                    description=(
                        "No package.json was found at the repository root. CodeMRI V1 only "
                        "analyzes JavaScript/TypeScript projects, so dependency, quality and "
                        "test analysis will be limited or skipped."
                    ),
                    recommendation="This repository falls outside V1 scope; results will be partial.",
                    analyzer=self.name,
                    evidence=[
                        Evidence(file_path="package.json", reason="package_json_missing"),
                    ],
                )
            )
        else:
            summary = " + ".join(stack_bits) if stack_bits else "Node.js project"
            findings.append(
                Finding(
                    category="fingerprint",
                    rule_id="FP-001",
                    title="Detected project stack",
                    severity="info",
                    confidence="high",
                    description=(
                        f"{summary}. {fingerprint['file_count']} files, "
                        f"{fingerprint['total_loc']} source lines, "
                        f"{fingerprint['test_file_count']} test files."
                    ),
                    recommendation="No action needed; informational.",
                    analyzer=self.name,
                    evidence=[
                        Evidence(
                            file_path="package.json",
                            metric_name="file_count",
                            metric_value=float(fingerprint["file_count"]),
                            reason="stack_summary",
                            snippet=json.dumps(
                                {
                                    "stack": summary,
                                    "languages": fingerprint["languages"],
                                    "package_manager": fingerprint["package_manager"],
                                }
                            )[:480],
                        )
                    ],
                )
            )

        return findings
