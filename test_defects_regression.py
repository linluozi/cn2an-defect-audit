"""Regression tests for four confirmed defects in cn2an 0.5.24.

Every assertion below was checked against the upstream commit 7c9ba07 first:
the ones that fail there are the reproduced bugs, the ones that pass there are
guard rails that must not regress.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cn2an.an2cn import An2Cn  # noqa: E402
from cn2an.cn2an import Cn2An  # noqa: E402
from cn2an.transform import Transform  # noqa: E402

ac = An2Cn()
ca = Cn2An()
tr = Transform()


# --------------------------------------------------------------------------
# D1  an2cn(..., "rmb") loses the 分 as soon as the fraction reaches 17+
#     characters: the 16-character cut happens before the cent is decided.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value, expected",
    [
        # --- guard rails: digit mapping verified against upstream output
        ("5.559", "伍元伍角伍分"),
        ("5.999", "伍元玖角玖分"),
        ("1.01", "壹元零壹分"),
        ("1.10", "壹元壹角"),
        ("7.5678", "柒元伍角陆分"),
        ("12.123456789012345", "壹拾贰元壹角贰分"),
        # --- reproduced defect: a 17+ digit run of 9s lost the carry into 元
        #     (upstream: 玖角玖分 -> value 0.99 instead of 1.00)
        ("0.999999999999999999", "壹元整"),
        ("10.999999999999999999", "壹拾壹元整"),
        ("100.999999999999999999", "壹佰零壹元整"),
    ],
)
def test_rmb_long_fraction_keeps_cents(value, expected):
    assert ac.an2cn(value, "rmb") == expected


def test_rmb_short_fraction_unchanged():
    """Fractions of at most 16 digits must stay byte-identical to upstream."""
    assert ac.an2cn("1.045", "rmb") == "壹元零肆分"
    assert ac.an2cn("0.4321", "rmb") == "肆角叁分"
    assert ac.an2cn("1000054.4321", "rmb") == "壹佰万零伍拾肆元肆角叁分"
    assert ac.an2cn("5.559", "rmb") == "伍元伍角伍分"
    assert ac.an2cn("5.999", "rmb") == "伍元玖角玖分"
    assert ac.an2cn("12.123456789012345", "rmb") == "壹拾贰元壹角贰分"


def test_rmb_long_run_of_nines_carries():
    """A 玖角玖分 pair followed by 9s past the 16-char cut must carry into 元."""
    for total in range(17, 25):
        value = "0." + "9" * total
        assert ac.an2cn(value, "rmb") == "壹元整", value
    for yuan in (1, 9, 99, 1000, 1000054):
        value = f"{yuan}." + "9" * 18
        text = ac.an2cn(value, "rmb")
        assert text.endswith("元整"), (value, text)
        assert ca.cn2an(text, "strict") == yuan + 1


# --------------------------------------------------------------------------
# D2  cn2an(..., "smart") returns a *float* for a plain integer string while
#     every other path returns an int; JSON output flips 123 -> 123.0.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value, expected", [
    ("123", 123), ("0", 0), ("100", 100), ("１２３", 123), ("00012", 12),
    ("10.1", 10.1), ("-10.1", -10.1), ("10.1万", 101000), ("16.4亿", 1640000000),
])
def test_smart_plain_digits_value(value, expected):
    assert ca.cn2an(value, "smart") == expected


@pytest.mark.parametrize("value", ["123", "0", "100", "１２３", "00012", "007"])
def test_smart_plain_integer_returns_int(value):
    """A plain integer string must not come back as float (JSON would print 123.0)."""
    result = ca.cn2an(value, "smart")
    assert isinstance(result, int) and not isinstance(result, bool), result


@pytest.mark.parametrize("value, expected", [("1.0", 1), ("0.0", 0)])
def test_smart_decimal_that_is_integral(value, expected):
    """A decimal spelling that lands on a whole number is an int, like 1.0 -> 1."""
    result = ca.cn2an(value, "smart")
    assert result == expected
    assert isinstance(result, int) and not isinstance(result, bool)


def test_smart_and_strict_agree_on_type_for_the_same_number():
    smart = ca.cn2an("1720", "smart")
    strict = ca.cn2an("一千七百二十", "strict")
    assert isinstance(smart, int) and isinstance(strict, int)
    assert smart == strict == 1720


# --------------------------------------------------------------------------
# D3  transform() lets AttributeError / TypeError escape for non-str input,
#     while cn2an()/an2cn() raise ValueError with a message.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value", [None, 123, 1.5, True, b"123", ["1"], {"a": 1}])
@pytest.mark.parametrize("method", ["cn2an", "an2cn"])
def test_transform_rejects_non_str_with_value_error(value, method):
    with pytest.raises(ValueError):
        tr.transform(value, method)


@pytest.mark.parametrize("method", ["cn2an", "an2cn"])
def test_transform_still_accepts_str(method):
    assert isinstance(tr.transform("小王捡了100块钱", method), str)


def test_transform_bad_method_still_raises_value_error():
    with pytest.raises(ValueError):
        tr.transform("123", "nope")


# --------------------------------------------------------------------------
# D4  documented boundary 10**16 (README 3.2).  an2cn rejected it and cn2an
#     stopped at 9999万亿, so neither direction could reach the stated maximum.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("value, low", [
    (10 ** 16, "一亿亿"),
    (10 ** 12, "一万亿"),
    (10 ** 16 - 1, "九千九百九十九万九千九百九十九亿九千九百九十九万九千九百九十九"),
])
def test_an2cn_accepts_documented_maximum(value, low):
    assert ac.an2cn(value, "low") == low


def test_an2cn_maximum_other_modes():
    assert ac.an2cn(10 ** 16, "up") == "壹亿亿"
    assert ac.an2cn(10 ** 16, "rmb") == "壹亿亿元整"


@pytest.mark.parametrize("value", [10 ** 16, -10 ** 16])
def test_an2cn_boundary_round_trip(value):
    """The documented maximum must survive an2cn -> cn2an."""
    assert ca.cn2an(ac.an2cn(value, "low"), "strict") == value


@pytest.mark.parametrize("value", [0, 1, 9, 99, 1000, 10 ** 8, 10 ** 12,
                                   10 ** 16 - 2, 10 ** 16 - 1, 9876543298765432])
def test_an2cn_round_trip_below_the_boundary(value):
    assert ca.cn2an(ac.an2cn(value, "low"), "strict") == value


def test_cn2an_rejects_beyond_the_documented_boundary():
    """亿亿 is only allowed with a 一 multiplier, so 10**17 and above stay out."""
    for text in ("九亿亿", "十亿亿", "二亿亿"):
        with pytest.raises(ValueError):
            ca.cn2an(text, "strict")


@pytest.mark.parametrize("value", [10 ** 17, 10 ** 18])
def test_an2cn_still_rejects_above_the_boundary(value):
    with pytest.raises(ValueError):
        ac.an2cn(value, "low")


@pytest.mark.parametrize("text, expected", [
    ("一亿亿", 10 ** 16),
    ("壹亿亿", 10 ** 16),
    ("一万亿", 10 ** 12),
    ("九千九百九十九万九千九百九十九亿九千九百九十九万九千九百九十九", 10 ** 16 - 1),
])
def test_cn2an_parses_yi_yi(text, expected):
    assert ca.cn2an(text, "strict") == expected


def test_cn2an_yi_yi_in_all_modes():
    assert ca.cn2an("一亿亿", "normal") == 10 ** 16
    assert ca.cn2an("一亿亿", "smart") == 10 ** 16
    assert ca.cn2an("负一亿亿", "strict") == -(10 ** 16)
