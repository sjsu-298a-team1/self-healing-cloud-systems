"""
Independent validation of scripts/metrics.py before closing the Model 1
preprocessing/split/evaluation protocol issue.

Three small, hand-computable evaluation cases are defined below. For each case,
TP/FP/TN/FN, Precision, Recall, F1, pre-fault FPR, and (where applicable)
detection delay are worked out BY HAND in the comments and hard-coded as
EXPECTED_* constants -- none of those constants are produced by calling
metrics.py. Only after the expected values are fixed does the test call the
real metrics.py functions and assert exact/near-exact agreement.

This file does not train the LSTM and does not touch any real val/test model
output -- all labels/predictions below are synthetic, hand-picked integers.

Usage:
    python3 test_metrics.py

(no --data-dir needed -- this file only exercises metrics.py's pure functions
against synthetic, hand-picked data, never real telemetry)
"""
import os
import sys

# metrics.py lives in scripts/model1/protocol/, a sibling directory tree to this
# test file's tests/model1/ -- add it to sys.path via a repo-relative path so this
# works regardless of the machine/checkout location.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "protocol"))

from metrics import (
    confusion_counts,
    detection_delay,
    f1_score,
    first_detection_time,
    median,
    precision,
    recall,
    pre_fault_false_positive_rate,
)

TOL = 1e-9


def close(a, b, tol=TOL):
    return abs(a - b) < tol


# =====================================================================
# CASE 1: perfect detection
# ---------------------------------------------------------------------
# inject_time = 10
# pre-fault windows  (label=False): t=5,6,7,8,9   predictions: all False
# post-inj  windows  (label=True):  t=10,11,12    predictions: all True
#
# By hand:
#   TP = 3 (t=10,11,12: label True, pred True)
#   FP = 0 (no pre-fault window predicted True)
#   FN = 0 (no post-injection window predicted False)
#   TN = 5 (t=5..9: label False, pred False)
#   Precision = TP/(TP+FP) = 3/3 = 1.0
#   Recall    = TP/(TP+FN) = 3/3 = 1.0
#   F1        = 2*1.0*1.0/(1.0+1.0) = 1.0
#   pre-fault FPR = FP_pre / n_pre = 0/5 = 0.0
#   first detection = first (label=True, pred=True) window by time = t=10
#   detection delay = 10 - 10 = 0
# =====================================================================
CASE1_TIMES = [5, 6, 7, 8, 9, 10, 11, 12]
CASE1_LABELS = [False, False, False, False, False, True, True, True]
CASE1_PREDS = [False, False, False, False, False, True, True, True]
CASE1_INJECT_TIME = 10
CASE1_PRE_PREDS = [False, False, False, False, False]

CASE1_EXPECTED = dict(
    tp=3, fp=0, fn=0, tn=5,
    precision=1.0, recall=1.0, f1=1.0,
    pre_fault_fpr=0.0,
    detection_time=10, detection_delay=0,
)


# =====================================================================
# CASE 2: false positives + missed anomalies
# ---------------------------------------------------------------------
# inject_time = 10
# pre-fault windows (label=False): t=5,6,7,8,9
#   predictions:                        F,   F,   T,   F,   T   -> 2 false positives (t=7,9)
# post-inj  windows (label=True):  t=10,11,12,13
#   predictions:                        F,   F,   T,   F        -> 1 true positive (t=12), 3 false negatives (t=10,11,13)
#
# By hand:
#   TP = 1, FP = 2, FN = 3, TN = 3
#   Precision = TP/(TP+FP) = 1/3           = 0.333333333333333...
#   Recall    = TP/(TP+FN) = 1/4           = 0.25
#   F1        = 2*(1/3)*(1/4) / (1/3+1/4)
#             = 2*(1/12) / (7/12) = (2/12)*(12/7) = 2/7 = 0.285714285714286...
#   pre-fault FPR = 2/5 = 0.4
#   first detection = first post-inj window with pred=True, scanning t=10(F),11(F),12(T) -> t=12
#   detection delay = 12 - 10 = 2
# =====================================================================
CASE2_TIMES = [5, 6, 7, 8, 9, 10, 11, 12, 13]
CASE2_LABELS = [False, False, False, False, False, True, True, True, True]
CASE2_PREDS = [False, False, True, False, True, False, False, True, False]
CASE2_INJECT_TIME = 10
CASE2_PRE_PREDS = [False, False, True, False, True]

CASE2_EXPECTED = dict(
    tp=1, fp=2, fn=3, tn=3,
    precision=1.0 / 3.0, recall=0.25, f1=2.0 / 7.0,
    pre_fault_fpr=0.4,
    detection_time=12, detection_delay=2,
)


# =====================================================================
# CASE 3: no post-injection detection at all (a total miss)
# ---------------------------------------------------------------------
# inject_time = 10
# pre-fault windows (label=False): t=5,6,7,8,9
#   predictions:                        F,   F,   F,   T,   F   -> 1 false positive (t=8)
# post-inj  windows (label=True):  t=10,11,12,13,14
#   predictions:                        F,   F,   F,   F,   F   -> 0 true positives, 5 false negatives
#
# By hand:
#   TP = 0, FP = 1, FN = 5, TN = 4
#   Precision = TP/(TP+FP) = 0/1 = 0.0
#   Recall    = TP/(TP+FN) = 0/5 = 0.0
#   F1: both precision and recall are 0 (not undefined -- there IS a positive
#       denominator in both), so by the standard F1 convention F1 = 0.0
#   pre-fault FPR = 1/5 = 0.2
#   first detection = scan all 5 post-inj windows, all pred=False -> NO detection (None)
#   => this case must be EXCLUDED from any detection-delay average/median,
#      not treated as delay=0 and not silently dropped from recall/precision.
# =====================================================================
CASE3_TIMES = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
CASE3_LABELS = [False, False, False, False, False, True, True, True, True, True]
CASE3_PREDS = [False, False, False, True, False, False, False, False, False, False]
CASE3_INJECT_TIME = 10
CASE3_PRE_PREDS = [False, False, False, True, False]

CASE3_EXPECTED = dict(
    tp=0, fp=1, fn=5, tn=4,
    precision=0.0, recall=0.0, f1=0.0,
    pre_fault_fpr=0.2,
    detection_time=None,  # miss -- no detection_delay computable
)


def run_case(name, times, labels, preds, inject_time, pre_preds, expected):
    print(f"\n--- {name} ---")
    failures = []

    cm = confusion_counts(labels, preds)
    for key in ("tp", "fp", "fn", "tn"):
        if cm[key] != expected[key]:
            failures.append(f"{key}: got {cm[key]}, expected {expected[key]}")

    p = precision(cm["tp"], cm["fp"])
    if not close(p, expected["precision"]):
        failures.append(f"precision: got {p}, expected {expected['precision']}")

    r = recall(cm["tp"], cm["fn"])
    if not close(r, expected["recall"]):
        failures.append(f"recall: got {r}, expected {expected['recall']}")

    f1 = f1_score(cm["tp"], cm["fp"], cm["fn"])
    if not close(f1, expected["f1"]):
        failures.append(f"f1: got {f1}, expected {expected['f1']}")

    fpr = pre_fault_false_positive_rate(pre_preds)
    if not close(fpr, expected["pre_fault_fpr"]):
        failures.append(f"pre_fault_fpr: got {fpr}, expected {expected['pre_fault_fpr']}")

    det_time = first_detection_time(times, labels, preds)
    if det_time != expected["detection_time"]:
        failures.append(f"detection_time: got {det_time}, expected {expected['detection_time']}")

    if expected["detection_time"] is None:
        if det_time is not None:
            failures.append("expected a miss (no detection) but first_detection_time returned a value")
    else:
        delay = detection_delay(inject_time, det_time)
        if delay != expected["detection_delay"]:
            failures.append(f"detection_delay: got {delay}, expected {expected['detection_delay']}")

    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
    else:
        print(
            f"PASS: TP={cm['tp']} FP={cm['fp']} FN={cm['fn']} TN={cm['tn']} "
            f"P={p:.6f} R={r:.6f} F1={f1:.6f} pre_fault_FPR={fpr:.6f} "
            f"detection_time={det_time}"
        )
    return len(failures) == 0, det_time


def main():
    all_passed = True

    ok1, det1 = run_case("Case 1: perfect detection", CASE1_TIMES, CASE1_LABELS, CASE1_PREDS,
                          CASE1_INJECT_TIME, CASE1_PRE_PREDS, CASE1_EXPECTED)
    all_passed &= ok1

    ok2, det2 = run_case("Case 2: false positives + missed anomalies", CASE2_TIMES, CASE2_LABELS,
                          CASE2_PREDS, CASE2_INJECT_TIME, CASE2_PRE_PREDS, CASE2_EXPECTED)
    all_passed &= ok2

    ok3, det3 = run_case("Case 3: no post-injection detection (miss)", CASE3_TIMES, CASE3_LABELS,
                          CASE3_PREDS, CASE3_INJECT_TIME, CASE3_PRE_PREDS, CASE3_EXPECTED)
    all_passed &= ok3

    # Rollup: median detection delay across cases, correctly excluding the miss.
    # By hand: case1 delay=0, case2 delay=2, case3=miss (excluded) -> median([0,2]) = 1.0
    print("\n--- Rollup: median detection delay across the 3 cases (miss excluded) ---")
    delays = []
    for det_time, inject_time, case_name in [
        (det1, CASE1_INJECT_TIME, "case1"),
        (det2, CASE2_INJECT_TIME, "case2"),
        (det3, CASE3_INJECT_TIME, "case3"),
    ]:
        if det_time is not None:
            delays.append(detection_delay(inject_time, det_time))
        else:
            print(f"  {case_name}: miss, excluded from delay rollup (as required)")
    expected_median_delay = 1.0  # hand-computed: median([0, 2]) = 1.0
    got_median_delay = median(delays)
    if len(delays) == 2 and close(got_median_delay, expected_median_delay):
        print(f"PASS: delays={delays}, median={got_median_delay}")
    else:
        print(f"FAIL: delays={delays}, median={got_median_delay}, expected median={expected_median_delay}")
        all_passed = False

    print(f"\nALL TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
