#!/usr/bin/env python3
"""Fail-closed validator for a supervised prize-drum physical soak journal."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable


AUDIT_PREFIX = "PRIZE_DRUM_AUDIT "
CANARY_PRIZE_IDS = frozenset(
    {
        "COCKTL",
        "DEP1K",
        "DEP2K",
        "MERCHFREE",
        "SHOT1FREE",
        "SHOTFR",
        "TIX1FREE",
        "TIX50",
    }
)


class SoakAuditError(RuntimeError):
    pass


def parse_audit_rows(lines: Iterable[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if AUDIT_PREFIX not in line:
            continue
        raw = line.split(AUDIT_PREFIX, 1)[1].strip()
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SoakAuditError(f"line {line_number}: malformed audit JSON") from exc
        if not isinstance(row, dict) or not str(row.get("event") or ""):
            raise SoakAuditError(f"line {line_number}: invalid audit row")
        row["_line"] = line_number
        rows.append(row)
    if not rows:
        raise SoakAuditError("no prize-drum audit rows found")
    return rows


def validate_soak(rows: list[dict[str, Any]], *, expected: int = 60) -> dict[str, Any]:
    if expected < 1:
        raise SoakAuditError("expected issue count must be positive")

    allowed_events = {"award_committed", "reel_landed", "print_complete", "print_error"}
    unexpected = sorted({str(row["event"]) for row in rows} - allowed_events)
    if unexpected:
        raise SoakAuditError(f"unexpected audit events: {', '.join(unexpected)}")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        issue_id = str(row.get("issue_id") or "")
        if not issue_id:
            raise SoakAuditError(f"line {row['_line']}: missing issue_id")
        grouped.setdefault(issue_id, []).append(row)

    if len(grouped) != expected:
        raise SoakAuditError(f"expected {expected} unique issues, found {len(grouped)}")

    prize_counts: Counter[str] = Counter()
    coupon_ids: set[str] = set()
    for issue_id, issue_rows in grouped.items():
        by_event: dict[str, list[dict[str, Any]]] = {}
        for row in issue_rows:
            by_event.setdefault(str(row["event"]), []).append(row)
        for required in ("award_committed", "reel_landed", "print_complete"):
            count = len(by_event.get(required, []))
            if count != 1:
                raise SoakAuditError(f"{issue_id}: expected one {required}, found {count}")
        if by_event.get("print_error"):
            raise SoakAuditError(f"{issue_id}: print_error present")

        award = by_event["award_committed"][0]
        landed = by_event["reel_landed"][0]
        printed = by_event["print_complete"][0]
        if not all(bool(row.get("test_mode")) for row in (award, landed, printed)):
            raise SoakAuditError(f"{issue_id}: production award present in canary soak")

        prize_id = str(award.get("prize_id") or "")
        landed_id = str(landed.get("landed_prize_id") or "")
        if prize_id not in CANARY_PRIZE_IDS:
            raise SoakAuditError(f"{issue_id}: unknown prize {prize_id!r}")
        if landed_id != prize_id or str(landed.get("prize_id") or "") != prize_id:
            raise SoakAuditError(
                f"{issue_id}: server prize {prize_id!r} landed as {landed_id!r}"
            )
        if str(printed.get("prize_id") or "") != prize_id:
            raise SoakAuditError(f"{issue_id}: printed prize does not match {prize_id!r}")

        coupon_audit_id = str(award.get("coupon_audit_id") or "")
        if not coupon_audit_id or coupon_audit_id in coupon_ids:
            raise SoakAuditError(f"{issue_id}: missing or duplicate coupon audit id")
        coupon_ids.add(coupon_audit_id)
        prize_counts[prize_id] += 1

        event_lines = [award["_line"], landed["_line"], printed["_line"]]
        if event_lines != sorted(event_lines):
            raise SoakAuditError(f"{issue_id}: event order is not award → landing → print")

    missing = sorted(CANARY_PRIZE_IDS - set(prize_counts))
    if missing:
        raise SoakAuditError(f"canary sectors not observed: {', '.join(missing)}")

    return {
        "status": "pass",
        "unique_issues": len(grouped),
        "unique_coupon_audit_ids": len(coupon_ids),
        "prize_counts": dict(sorted(prize_counts.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("journal", type=Path)
    parser.add_argument("--expected", type=int, default=60)
    args = parser.parse_args()
    rows = parse_audit_rows(args.journal.read_text(encoding="utf-8").splitlines())
    print(json.dumps(validate_soak(rows, expected=args.expected), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
