from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def clean_js(fixtures_dir: Path) -> Path:
    return fixtures_dir / "clean-js"


@pytest.fixture
def circular_deps(fixtures_dir: Path) -> Path:
    return fixtures_dir / "circular-deps"


@pytest.fixture
def almost_no_tests(fixtures_dir: Path) -> Path:
    return fixtures_dir / "almost-no-tests"


@pytest.fixture
def vulnerable_deps(fixtures_dir: Path) -> Path:
    return fixtures_dir / "vulnerable-deps"


@pytest.fixture
def secrets(fixtures_dir: Path) -> Path:
    return fixtures_dir / "secrets"
