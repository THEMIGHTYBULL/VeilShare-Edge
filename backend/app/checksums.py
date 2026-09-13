"""Numeric checksum algorithms used to validate structured identifiers.

These make the deterministic detectors *precise* instead of noisy:

- a 13-19 digit string is only called a payment card when it passes **Luhn**;
- a 12-digit string is only called Aadhaar-like when it passes the
  **Verhoeff** check digit used by UIDAI.

Both algorithms run locally on plain digit strings. No network access.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Luhn (payment cards, and many other check-digit schemes)
# ---------------------------------------------------------------------------

def luhn_checksum(number: str) -> int:
    """Return the Luhn checksum (0-9) of a digit string."""
    digits = [int(c) for c in re.findall(r"\d", number)]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10


def luhn_valid(number: str) -> bool:
    """True when the digit string satisfies the Luhn check."""
    return luhn_checksum(number) == 0


def luhn_check_digit(partial: str) -> int:
    """Check digit to append to `partial` so the result passes Luhn."""
    return (10 - luhn_checksum(partial + "0")) % 10


# ---------------------------------------------------------------------------
# Verhoeff (used by Aadhaar numbers)
# ---------------------------------------------------------------------------

# Dihedral group D5 operation table: d[j][k]
_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation applied based on digit position (period 8)
_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse of the D table's first row (used to derive check digits)
_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def verhoeff_valid(number: str) -> bool:
    """True when the digit string satisfies the Verhoeff check.

    Processes digits right-to-left with permutation row ``i % 8``
    (i = 0 for the rightmost digit, the check digit itself).
    """
    digits = [int(c) for c in re.findall(r"\d", number)]
    if not digits:
        return False
    c = 0
    for i, d in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][d]]
    return c == 0


def verhoeff_check_digit(partial: str) -> int:
    """Check digit to append to `partial` so the result passes Verhoeff.

    Appends a zero placeholder at the check-digit position (i = 0), folds the
    payload, then inverts the accumulator.
    """
    digits = [int(c) for c in re.findall(r"\d", partial)] + [0]
    c = 0
    for i, d in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][d]]
    return _INV[c]
