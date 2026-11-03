"""Verbatim evidence matching must not false-reject real page text.

Eight cases against agent.evidence_is_real: smart quotes, NBSP, hyphen vs
en-dash, a newline inside the quote, case folding, a real mismatch (must NOT
match), the empty quote (must NOT match) and a partial quote (must NOT match).

Run from the repo root:  python scripts/test_evidence.py
Exit is non-zero when any case fails.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import evidence_is_real

CASES = [
    # (name, quote, source, expected)
    ("curly double quotes", 'The heading reads "Example Domain".', '<h1>The heading reads \u201cExample Domain\u201d.</h1>', True),
    ("NBSP in the source text", "Price: 100 USD per night", "Price:\u00a0100\u202fUSD\u00a0per\u00a0night", True),
    ("hyphen quote, en-dash source", "years 1990-1999", "Coverage spans the years 1990\u20131999 and beyond.", True),
    ("newline inside the quote", "Status: active Expires: never", "Record:\n  Status: active\n  Expires: never", True),
    ("case difference", "Example Domain", "EXAMPLE DOMAIN", True),
    ("real mismatch", "The tower is exactly 330 meters", "The Eiffel Tower is 330 metres tall.", False),
    ("empty quote", "", "Some perfectly good page text.", False),
    ("partial quote", "Example Domain plus words that are nowhere in this source", "Example Domain with different words after it", False),
]


def main() -> None:
    failures = 0
    for name, quote, source, expected in CASES:
        got = evidence_is_real(quote, source)
        ok = got == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name}: expected {expected}, got {got}")
        if not ok:
            failures += 1
    if failures:
        print(f"\n{failures} of {len(CASES)} case(s) failed")
        sys.exit(1)
    print(f"\nAll {len(CASES)} evidence-matching cases pass")


if __name__ == "__main__":
    main()
