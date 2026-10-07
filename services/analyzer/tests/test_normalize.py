from __future__ import annotations

from app.analyzers.base import Evidence, Finding
from app.evidence.normalize import fingerprint_hash, normalize_findings, redact


def _finding(**overrides) -> Finding:
    payload = dict(
        category="security",
        rule_id="SEC-001",
        title="Probable secret",
        severity="critical",
        confidence="high",
        description="d",
        recommendation="r",
        analyzer="test",
        evidence=[
            Evidence(
                file_path="src/config.js",
                line_start=3,
                line_end=3,
                snippet='apiKey = "AKIA1234567890ABCDEF"',
                reason="aws_key_pattern",
            )
        ],
    )
    payload.update(overrides)
    return Finding(**payload)


def test_redacts_aws_key() -> None:
    text = "const k = 'AKIA1234567890ABCDEF';"
    redacted = redact(text)
    assert "AKIA1234567890ABCDEF" not in redacted
    assert "AKIA" in redacted
    assert "*" in redacted


def test_redacts_assignment_secret() -> None:
    text = 'password: "hunter2supersecret",'
    redacted = redact(text)
    assert "hunter2supersecret" not in redacted
    assert "REDACTED" in redacted


def test_redacts_ghp_token() -> None:
    text = "token=ghp_abcdefghij1234567890ABCD"
    redacted = redact(text)
    assert "ghp_abcdefghij1234567890ABCD" not in redacted


def test_redact_keeps_normal_text() -> None:
    assert redact("const answer = 42;") == "const answer = 42;"
    assert redact(None) is None


def test_fingerprint_hash_stable_and_distinct() -> None:
    a = fingerprint_hash("SEC-001", "src/a.js", None, "reason")
    b = fingerprint_hash("SEC-001", "src/a.js", None, "reason")
    c = fingerprint_hash("SEC-001", "src/b.js", None, "reason")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_normalize_dedupes_same_rule_and_group(tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Base, Finding as FindingRow

    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    f1 = _finding()
    f2 = _finding()  # same rule + same file anchor -> same group_key
    stored = normalize_findings(session, 1, [f1, f2])
    session.commit()

    rows = session.query(FindingRow).all()
    assert len(rows) == 1
    assert rows[0].occurrence_count == 2
    assert 1 <= len(rows[0].evidence) <= 5  # evidence appended, capped at 5
    assert stored[0].id is not None
    session.close()


def test_normalize_caps_evidence_and_redacts(tmp_path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Base, Finding as FindingRow

    engine = create_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    many = [
        _finding(
            group_key=f"SEC-001|file{i}.js",
            evidence=[
                Evidence(
                    file_path=f"file{i}.js",
                    line_start=i,
                    snippet=f"AKIA{'X' * 16}",
                    reason="aws_key_pattern",
                )
            ],
        )
        for i in range(10)
    ]
    normalize_findings(session, 1, many)
    session.commit()

    rows = session.query(FindingRow).all()
    assert len(rows) == 10  # different group keys -> separate rows
    for row in rows:
        assert len(row.evidence) <= 5
        for item in row.evidence:
            assert item.snippet is None or "REDACTED" in item.snippet or "XXXX" not in item.snippet
    session.close()
