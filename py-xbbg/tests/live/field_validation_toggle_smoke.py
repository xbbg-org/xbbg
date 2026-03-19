"""Live smoke test for field-validation toggle behavior.

Run with Bloomberg Terminal connected:

    uv run python py-xbbg/tests/live/field_validation_toggle_smoke.py
"""

from __future__ import annotations

from dataclasses import dataclass

import xbbg
from xbbg.exceptions import BlpValidationError

TICKER = "IBM US Equity"
BAD_FIELD = "INVALID_FIELD_12345"


@dataclass
class Case:
    name: str
    validation_mode: str
    validate_fields: bool | None
    should_raise: bool


CASES = [
    Case(
        name="engine_disabled_default",
        validation_mode="disabled",
        validate_fields=None,
        should_raise=False,
    ),
    Case(
        name="engine_strict_default",
        validation_mode="strict",
        validate_fields=None,
        should_raise=True,
    ),
    Case(
        name="engine_strict_request_override_off",
        validation_mode="strict",
        validate_fields=False,
        should_raise=False,
    ),
    Case(
        name="engine_disabled_request_override_on",
        validation_mode="disabled",
        validate_fields=True,
        should_raise=True,
    ),
]


def run_case(case: Case) -> tuple[bool, str]:
    xbbg.reset()
    xbbg.configure(validation_mode=case.validation_mode)

    try:
        df = xbbg.bdp(TICKER, BAD_FIELD, validate_fields=case.validate_fields)
    except BlpValidationError as exc:
        if case.should_raise:
            return True, f"raised BlpValidationError as expected: {exc}"
        return False, f"unexpected BlpValidationError: {exc}"
    except Exception as exc:  # pragma: no cover - live diagnostic path
        return False, f"unexpected {type(exc).__name__}: {exc}"

    if case.should_raise:
        return False, "expected BlpValidationError but request succeeded"

    return True, f"succeeded with rows={len(df)}"


def main() -> int:
    print("Running field validation toggle smoke cases...")
    failures = 0

    for case in CASES:
        ok, detail = run_case(case)
        status = "PASS" if ok else "FAIL"
        print(f"{status:4} {case.name:38} {detail}")
        if not ok:
            failures += 1

    xbbg.reset()

    if failures:
        print(f"\n{failures} case(s) failed")
        return 1

    print("\nAll cases passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
