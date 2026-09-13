"""Checksum algorithm tests (Luhn + Verhoeff)."""

from backend.app.checksums import (
    luhn_check_digit,
    luhn_valid,
    verhoeff_check_digit,
    verhoeff_valid,
)


def test_luhn_known_vectors():
    assert luhn_valid("4111111111111111") is True   # classic Visa test number
    assert luhn_valid("4111111111111112") is False
    assert luhn_valid("5500005555555559") is True
    assert luhn_valid("79927398713") is True        # textbook example
    assert luhn_valid("79927398710") is False


def test_luhn_ignores_separators():
    assert luhn_valid("4111 1111 1111 1111") is True
    assert luhn_valid("4111-1111-1111-1111") is True


def test_luhn_check_digit_roundtrip():
    assert luhn_check_digit("411111111111111") == 1
    for partial in ("123456789", "000000000", "987654321"):
        assert luhn_valid(partial + str(luhn_check_digit(partial))) is True


def test_verhoeff_worked_example():
    # The classic Verhoeff worked example: check digit for 236 is 3.
    assert verhoeff_check_digit("236") == 3
    assert verhoeff_valid("2363") is True
    assert verhoeff_valid("2364") is False


def test_verhoeff_roundtrip_and_single_digit_errors():
    import random

    rng = random.Random(1234)
    for _ in range(500):
        n = rng.randint(10**5, 10**12)
        partial = str(n)
        full = partial + str(verhoeff_check_digit(partial))
        assert verhoeff_valid(full) is True
        # corrupting any single digit must invalidate (Verhoeff property)
        pos = rng.randrange(len(full))
        bad = full[:pos] + str((int(full[pos]) + 1 + rng.randint(0, 8)) % 10) + full[pos + 1:]
        if bad != full:
            assert verhoeff_valid(bad) is False


def test_verhoeff_rejects_garbage():
    assert verhoeff_valid("") is False
    assert verhoeff_valid("abc") is False
