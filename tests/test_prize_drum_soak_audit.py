from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_prize_drum_soak_log.py"
SPEC = importlib.util.spec_from_file_location("prize_drum_soak_audit", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def _rows(*, count: int = 8):
    lines = []
    prizes = sorted(audit.CANARY_PRIZE_IDS)
    for index in range(count):
        issue_id = f"canary-issue-{index:06d}"
        prize_id = prizes[index % len(prizes)]
        payloads = (
            {
                "event": "award_committed",
                "issue_id": issue_id,
                "prize_id": prize_id,
                "coupon_audit_id": f"TEST-VNVNC-{index:06d}",
                "test_mode": True,
            },
            {
                "event": "reel_landed",
                "issue_id": issue_id,
                "prize_id": prize_id,
                "landed_prize_id": prize_id,
                "test_mode": True,
            },
            {
                "event": "print_complete",
                "issue_id": issue_id,
                "prize_id": prize_id,
                "test_mode": True,
            },
        )
        lines.extend(f"journal prefix {audit.AUDIT_PREFIX}{json.dumps(row)}" for row in payloads)
    return audit.parse_audit_rows(lines)


def test_soak_auditor_accepts_complete_eight_sector_canary() -> None:
    result = audit.validate_soak(_rows(), expected=8)
    assert result["status"] == "pass"
    assert result["unique_issues"] == 8
    assert set(result["prize_counts"]) == audit.CANARY_PRIZE_IDS


@pytest.mark.parametrize(
    "mutate, error",
    [
        (lambda rows: rows.pop(), "print_complete"),
        (
            lambda rows: rows[1].__setitem__("landed_prize_id", "WRONG"),
            "landed as",
        ),
        (
            lambda rows: rows.append(
                {
                    "_line": 999,
                    "event": "print_error",
                    "issue_id": rows[0]["issue_id"],
                    "prize_id": rows[0]["prize_id"],
                    "test_mode": True,
                }
            ),
            "print_error",
        ),
        (lambda rows: rows[0].__setitem__("test_mode", False), "production award"),
        (
            lambda rows: rows[3].__setitem__(
                "coupon_audit_id", rows[0]["coupon_audit_id"]
            ),
            "duplicate coupon",
        ),
    ],
)
def test_soak_auditor_fails_closed_on_bad_evidence(mutate, error) -> None:
    rows = _rows()
    mutate(rows)
    with pytest.raises(audit.SoakAuditError, match=error):
        audit.validate_soak(rows, expected=8)
