from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Trigger content is materialized at test time (these modules are plain .py, so
# the committed repository never contains secret-shaped strings or circular
# imports on disk — the analyzer sees them only inside pytest's tmp dir).
# ---------------------------------------------------------------------------

SECRETS_CONFIG_JS = '''\
"use strict";

// FAKE credentials for testing only. Do not use.
const config = {
  awsAccessKeyId: "AKIAIOSFODNN7FAKEKEY",
  githubToken: "ghp_FAKEFAKEFAKEFAKEFAKEFAKE12",
  apiKey: "super-secret-demo-key-000111222333",
};

module.exports = { config };
'''

CIRCULAR_A_JS = '''\
"use strict";

const { b } = require("./b.js");

function a() {
  return b();
}

module.exports = { a };
'''

CIRCULAR_B_JS = '''\
"use strict";

const { a } = require("./a.js");

function b() {
  return a();
}

module.exports = { b };
'''

# Materialized at test time only; the committed fixture directory never
# contains a .env file (it is gitignored and would be absent from clean
# checkouts, which is exactly why SEC-002 must be tested against tmp_path).
SECRETS_ENV = """\
# Runtime fixture environment (see conftest.py)
NODE_ENV=test
FAKE_API_KEY=placeholder
"""


def _materialize(name: str, tmp_path: Path, overwrite: dict[str, str]) -> Path:
    dest = tmp_path / name
    shutil.copytree(FIXTURES / name, dest)
    for rel, content in overwrite.items():
        (dest / rel).write_text(content, encoding="utf-8")
    return dest


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def clean_js(fixtures_dir: Path) -> Path:
    return fixtures_dir / "clean-js"


@pytest.fixture
def circular_deps(tmp_path: Path) -> Path:
    return _materialize(
        "circular-deps",
        tmp_path,
        {"a.js": CIRCULAR_A_JS, "b.js": CIRCULAR_B_JS},
    )


@pytest.fixture
def almost_no_tests(fixtures_dir: Path) -> Path:
    return fixtures_dir / "almost-no-tests"


@pytest.fixture
def vulnerable_deps(fixtures_dir: Path) -> Path:
    return fixtures_dir / "vulnerable-deps"


@pytest.fixture
def secrets(tmp_path: Path) -> Path:
    return _materialize(
        "secrets",
        tmp_path,
        {"src/config.js": SECRETS_CONFIG_JS, ".env": SECRETS_ENV},
    )