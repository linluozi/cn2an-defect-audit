# NOTICE — modifications to cn2an

This tree is **cn2an 0.5.24** (upstream commit `7c9ba0770b129960d9b6e6c6b2b46c00ec580778`,
https://github.com/Ailln/cn2an, MIT License) with four defect fixes applied.

Original work: Copyright (c) Ailln. License unchanged: MIT (see `LICENSE`).

## Changed files

| File | Change |
| --- | --- |
| `cn2an/an2cn.py` | D1: 角/分 are read before the fraction is truncated, so a 17+ digit run of 9s can carry into 元 |
| `cn2an/cn2an.py` | D2: `smart` returns `int` for integral values; D4: `亿亿` (10**16) regex branch |
| `cn2an/transform.py` | D3: non-`str` input raises `ValueError` instead of leaking `AttributeError`/`TypeError` |
| `cn2an/conf.py` | D4: 17th unit order entry + `MAX_UNIT_PATTERN_CN` |
| `cn2an/an2cn_test.py` | negative case `1.23e16` → `1.23e17`, because `10**16` is now in range |
| `test_defects_regression.py` | new, 70 regression tests |

Everything else is byte-identical to upstream. `defect-fixes.patch` reproduces the whole
change against a `git archive HEAD` export of the upstream commit.

## Verification performed

- clean upstream export (`git archive HEAD`): `pytest test_defects_regression.py` → **35 failed / 36 passed**
- patched tree: `pytest` → **73 passed**
- differential over 408 probes across `cn2an` / `an2cn` / `transform`: **408 identical to upstream**
- mutation check: removing each fix in turn makes 4 / 9 / 14 / 5 tests fail (none missed)
- `flake8 cn2an example setup.py --select=E9,F63,F7,F82` → 0 (same as upstream)

See `REPORT.md` for the full analysis and `repro.json` for the raw before/after values.
