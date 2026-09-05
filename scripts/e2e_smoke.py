#!/usr/bin/env python3
"""End-to-end smoke test for the Financial Clarity demo.

Owned by Person 5 (integration/demo). Run this against a live backend before
every demo checkpoint (hours 14, 24, 32 per the team schedule) to catch any
regression that would break the pitch mid-demo.

Usage:
    uvicorn app.main:app --reload    # in backend/, in another terminal
    python scripts/e2e_smoke.py [base_url]   # defaults to http://127.0.0.1:8000

Exits non-zero on any failure so it can be wired into a pre-demo checklist.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # older Python without reconfigure(); output falls back to the platform default

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
SAMPLE_OFFERS_PATH = Path(__file__).resolve().parent.parent / "backend" / "data" / "sample_offers.json"

failures: list[str] = []


def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                  headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def check(label: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(f"{label}: {detail}")


def main() -> int:
    print(f"Financial Clarity E2E smoke test — target {BASE_URL}\n")

    print("Global endpoints")
    status, scope = request("GET", "/completeness-scope")
    check("GET /completeness-scope reachable", status == 200, f"status {status}")
    check("completeness-scope has covered/not_covered", "covered" in scope and "not_covered" in scope)

    status, rule = request("GET", "/rule/PF_EMPLOYEE_RATE")
    check("GET /rule/PF_EMPLOYEE_RATE reachable", status == 200, f"status {status}")
    check("rule has description", bool(rule.get("description")))
    print()

    offers = json.loads(SAMPLE_OFFERS_PATH.read_text(encoding="utf-8"))["offers"]
    for offer in offers:
        print(f"Sample offer: {offer['id']} — {offer['title']}")
        status, payload = request("POST", "/breakdown", {
            "ctc_breakup": offer["ctc_breakup"],
            "regime": offer["regime"],
        })
        check(f"[{offer['id']}] POST /breakdown returns 200", status == 200, f"status {status}, body {payload}")
        if status != 200:
            print()
            continue

        b = payload["breakdown"]
        flags = payload["red_flags"]
        expect = offer["expect"]

        check(f"[{offer['id']}] red_flag_count == {expect['red_flag_count']}",
              len(flags) == expect["red_flag_count"],
              f"got {len(flags)}: {[f['flag_id'] for f in flags]}")
        check(f"[{offer['id']}] in_hand_monthly == {expect['in_hand_monthly']}",
              abs(b["in_hand_monthly"] - expect["in_hand_monthly"]) < 0.01,
              f"got {b['in_hand_monthly']}")
        if "hra_exemption_amount" in expect:
            check(f"[{offer['id']}] hra_exemption_amount == {expect['hra_exemption_amount']}",
                  abs(b["hra_exemption_amount"] - expect["hra_exemption_amount"]) < 0.01,
                  f"got {b['hra_exemption_amount']}")
        check(f"[{offer['id']}] every deduction/flag with a rule_id resolves",
              all(request("GET", f"/rule/{d['rule_id']}")[0] == 200
                  for d in b["deductions"] if d.get("rule_id")))
        print()

    print(f"{'='*60}")
    if failures:
        print(f"{len(failures)} check(s) FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
