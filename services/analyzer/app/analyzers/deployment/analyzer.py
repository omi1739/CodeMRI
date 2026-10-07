from __future__ import annotations

from pathlib import Path

from app.analyzers.base import Evidence, Finding, ScanContext


class DeploymentAnalyzer:
    name = "deployment"
    version = "0.1.0"

    def run(self, ctx: ScanContext) -> list[Finding]:
        findings: list[Finding] = []

        has_dockerfile = any(_is_dockerfile(e.get("path") or "") for e in ctx.inventory)
        has_ci = any(_is_ci_file(e.get("path") or "") for e in ctx.inventory)

        if not has_dockerfile and not has_ci:
            findings.append(
                Finding(
                    category="deployment",
                    rule_id="DEP-LY-001",
                    title="No container or CI deployment definition",
                    severity="low",
                    confidence="high",
                    description=(
                        "No Dockerfile or CI workflow (e.g. .github/workflows, .gitlab-ci.yml, "
                        "Jenkinsfile, .circleci) was found, so deployment is not automated or "
                        "containerized in a reproducible way."
                    ),
                    recommendation=(
                        "Add a Dockerfile and a minimal CI workflow that runs tests and produces "
                        "an artifact."
                    ),
                    analyzer=self.name,
                    group_key="DEP-LY-001|none",
                    evidence=[Evidence(file_path="Dockerfile", reason="no_deployment_definition")],
                )
            )
        return findings


def _is_dockerfile(rel: str) -> bool:
    return Path(rel).name.lower() in ("dockerfile", "dockerfile.dev")


def _is_ci_file(rel: str) -> bool:
    lowered = rel.lower()
    return (
        "workflow" in lowered and lowered.endswith(".yml")
        or lowered.endswith("jenkinsfile")
        or lowered.startswith(".github/workflows/")
        or lowered.startswith(".gitlab-ci")
        or lowered.startswith(".circleci/")
        or lowered.startswith("azure-pipelines")
        or lowered.startswith("bitbucket-pipelines")
        or lowered.startswith(".travis")
        or lowered.startswith(".appveyor")
    )