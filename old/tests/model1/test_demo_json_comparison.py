"""
Regression test for the Stage 4 scaler-comparison bug in
scripts/model1/demo/run_data_demo.py.

Stage 4 regenerates configs/model1/scaler.json from scratch and compares it
against the committed file. On a real run, the regenerated std for
large-magnitude features (e.g. *_mem stats ~1e7) differed from the committed
value by ~4.8e-7 absolute -- float64 summation-order noise from a different
numpy/pandas version, ~2e-14 relative to the value itself -- which exceeded
the old abs_tol=1e-9-only comparison and made Stage 4 FAIL despite the scaler
being correct to ~14 significant figures. The fix made that comparison
math.isclose(rel_tol=1e-12, abs_tol=1e-9) instead of a bare absolute diff.

This test is entirely synthetic: no Torch, no BARO dataset, no real
scaler.json is read. The large-magnitude numbers in case 2 are the exact
pair observed during that investigation (committed vs. regenerated std for
one *_mem feature on this machine), reused here only as representative
floats, not loaded from any file.

Usage:
    python3 test_demo_json_comparison.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "scripts", "model1", "demo",
))

from run_data_demo import (
    SCALER_COMPARISON_ABS_TOL,
    SCALER_COMPARISON_REL_TOL,
    _approx_equal,
    compare_json,
)

assert SCALER_COMPARISON_ABS_TOL == 1e-9
assert SCALER_COMPARISON_REL_TOL == 1e-12


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {name}" + (f" -- {detail}" if detail else ""))
    return condition


def write_json(tmpdir, filename, obj):
    path = os.path.join(tmpdir, filename)
    with open(path, "w") as f:
        json.dump(obj, f)
    return path


def main():
    failures = []

    # ------------------------------------------------------------------
    # 1. Exact numeric match -> PASS
    # ------------------------------------------------------------------
    a = {"mean": {"adservice_cpu": 1.135115763}, "std": {"adservice_cpu": 0.4415521638}}
    b = {"mean": {"adservice_cpu": 1.135115763}, "std": {"adservice_cpu": 0.4415521638}}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("1. exact numeric match", ok is True):
        failures.append("1")

    # ------------------------------------------------------------------
    # 2. Large-magnitude value, ~2e-14 relative float64 noise -> PASS
    #    (the exact pair observed on this machine for a *_mem feature's std;
    #    reused here as representative floats only)
    # ------------------------------------------------------------------
    committed_std = 24138511.4370775670
    regenerated_std = 24138511.4370780438
    rel_diff = abs(committed_std - regenerated_std) / committed_std
    a = {"std": {"main_mem": committed_std}}
    b = {"std": {"main_mem": regenerated_std}}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("2. large-magnitude value, ~2e-14 relative noise", ok is True,
                 f"rel_diff={rel_diff:.3e}"):
        failures.append("2")
    # Confirm this case genuinely needs the relative tolerance -- abs_tol
    # alone (the old behavior) must NOT be enough to pass it, or this test
    # would not actually be exercising the fix.
    abs_tol_only = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, 0.0)
    if not check("2b. same pair fails under abs_tol-only (proves rel_tol is doing the work)",
                 abs_tol_only is False):
        failures.append("2b")

    # ------------------------------------------------------------------
    # 3. Tiny absolute floating-point noise on a small-magnitude value -> PASS
    # ------------------------------------------------------------------
    a = {"mean": {"adservice_latency-50": 0.0008233324289}}
    b = {"mean": {"adservice_latency-50": 0.0008233324289 + 1e-10}}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("3. tiny absolute noise on a small-magnitude value", ok is True):
        failures.append("3")

    # ------------------------------------------------------------------
    # 4. Deliberately meaningful scaler-value change -> FAIL
    # ------------------------------------------------------------------
    a = {"mean": {"adservice_cpu": 1.135115763}}
    b = {"mean": {"adservice_cpu": 1.135115763 + 0.01}}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("4. deliberately meaningful value change", ok is False):
        failures.append("4")

    # ------------------------------------------------------------------
    # 5. Missing dictionary key -> FAIL
    # ------------------------------------------------------------------
    a = {"mean": {"adservice_cpu": 1.0}, "std": {"adservice_cpu": 0.5}}
    b = {"mean": {"adservice_cpu": 1.0}}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("5. missing dictionary key", ok is False):
        failures.append("5")

    # ------------------------------------------------------------------
    # 6. List-length mismatch -> FAIL
    # ------------------------------------------------------------------
    a = {"features": ["adservice_cpu", "adservice_mem", "cartservice_cpu"]}
    b = {"features": ["adservice_cpu", "adservice_mem"]}
    ok = _approx_equal(a, b, SCALER_COMPARISON_ABS_TOL, SCALER_COMPARISON_REL_TOL)
    if not check("6. list-length mismatch", ok is False):
        failures.append("6")

    # ------------------------------------------------------------------
    # 7. Exact comparison path (tolerance=None) still rejects a changed
    #    manifest-like value -- this is Stage 3's exact call pattern, and
    #    must remain completely unaffected by the Stage 4 fix above.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        committed = write_json(tmpdir, "train_cases_committed.json",
                                {"case_ids": ["cartservice_cpu/1", "cartservice_cpu/2"]})
        changed = write_json(tmpdir, "train_cases_regenerated.json",
                              {"case_ids": ["cartservice_cpu/1", "cartservice_cpu/3"]})
        ok = compare_json(changed, committed, "train_cases.json")  # tolerance=None (default)
        if not check("7. tolerance=None path rejects a changed manifest-like value",
                      ok is False):
            failures.append("7")

        # Same-content exact match must still pass under tolerance=None, to
        # confirm this isn't just "always fails" once case_ids differ in
        # some other way.
        identical = write_json(tmpdir, "train_cases_identical.json",
                                {"case_ids": ["cartservice_cpu/1", "cartservice_cpu/2"]})
        ok2 = compare_json(identical, committed, "train_cases.json")
        if not check("7b. tolerance=None path still passes on an identical manifest",
                      ok2 is True):
            failures.append("7b")

    # ------------------------------------------------------------------
    # 8. End-to-end compare_json, exactly as Stage 4 calls it (file I/O
    #    included), on a synthetic scaler.json-shaped pair with the same
    #    large-magnitude noise as case 2.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as tmpdir:
        scaler_shape = lambda std_mem: {
            "method": "zscore",
            "features": ["adservice_cpu", "main_mem"],
            "mean": {"adservice_cpu": 1.135115763, "main_mem": 1234.0},
            "std": {"adservice_cpu": 0.4415521638, "main_mem": std_mem},
        }
        committed = write_json(tmpdir, "scaler_committed.json", scaler_shape(committed_std))
        regenerated = write_json(tmpdir, "scaler_regenerated.json", scaler_shape(regenerated_std))
        ok = compare_json(regenerated, committed, "scaler.json",
                           tolerance=SCALER_COMPARISON_ABS_TOL,
                           rel_tolerance=SCALER_COMPARISON_REL_TOL)
        if not check("8. end-to-end compare_json on a scaler.json-shaped pair "
                     "(Stage 4's exact call pattern)", ok is True):
            failures.append("8")

    all_passed = len(failures) == 0
    print(f"\nALL TESTS PASSED: {all_passed}")
    if failures:
        print(f"Failed cases: {failures}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
