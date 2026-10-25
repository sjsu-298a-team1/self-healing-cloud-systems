"""
Model 1 protocol step 7: evaluation metric formulas.

Pure functions only -- no model, no real predictions. Exercised in this file's
__main__ block with small synthetic arrays purely to prove the formulas are
implemented correctly; this is NOT model evaluation and does not touch the
dataset, val, or test splits.
"""
from typing import Sequence


def precision(tp: int, fp: int) -> float:
    return tp / (tp + fp) if (tp + fp) > 0 else float("nan")


def recall(tp: int, fn: int) -> float:
    return tp / (tp + fn) if (tp + fn) > 0 else float("nan")


def f1_score(tp: int, fp: int, fn: int) -> float:
    p = precision(tp, fp)
    r = recall(tp, fn)
    if p != p or r != r:  # NaN check without importing math/numpy
        return float("nan")
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def confusion_counts(labels: Sequence[bool], predictions: Sequence[bool]):
    assert len(labels) == len(predictions), "labels and predictions must be same length"
    tp = fp = fn = tn = 0
    for y, yhat in zip(labels, predictions):
        if y and yhat:
            tp += 1
        elif (not y) and yhat:
            fp += 1
        elif y and (not yhat):
            fn += 1
        else:
            tn += 1
    return dict(tp=tp, fp=fp, fn=fn, tn=tn)


def detection_delay(inject_time: float, detection_time: float) -> float:
    """Seconds between fault injection and first true-positive detection.
    Caller must only invoke this for cases that had at least one detection --
    a case with no detection is a miss and must be reported separately, not
    passed here."""
    return detection_time - inject_time


def first_detection_time(window_times: Sequence[float], window_labels: Sequence[bool], window_predictions: Sequence[bool]):
    """Implements protocol_config.json's detection_event_rule: the timestamp of the
    first window that is both in the post-injection evaluation region (label=True)
    and predicted anomalous. Inputs must already be sorted by time ascending.
    Returns None if no such window exists (a miss) -- callers must check for None
    and exclude misses from detection_delay/median, not silently coerce to 0 or skip
    the case's contribution to recall/precision."""
    assert len(window_times) == len(window_labels) == len(window_predictions)
    for t, label, pred in zip(window_times, window_labels, window_predictions):
        if label and pred:
            return t
    return None


def median(values: Sequence[float]) -> float:
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        return float("nan")
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def pre_fault_false_positive_rate(pre_fault_predictions: Sequence[bool]) -> float:
    """pre_fault_predictions: one bool per window in the known-normal region
    (time < inject_time) only -- see protocol_config.json limitations.fault_duration.
    True = predicted anomalous. Must never include any post-injection-region window."""
    n = len(pre_fault_predictions)
    if n == 0:
        return float("nan")
    return sum(1 for p in pre_fault_predictions if p) / n


FAULT_TYPES = ("cpu", "mem", "delay", "loss")


def fault_type_of_case(case_id: str) -> str:
    """case_id format '<service>_<fault_type>/<run_id>', e.g. 'cartservice_cpu/3' -> 'cpu'.
    Used to stratify evaluation by fault type (protocol_config.json
    metrics.stratified_evaluation) so CPU/MEM (stress-ng, possible early
    self-termination) and DELAY/LOSS (tc, plausibly persistent) can be compared
    instead of pooled -- see limitations.fault_duration."""
    combo = case_id.split("/")[0]
    for ft in FAULT_TYPES:
        if combo.endswith("_" + ft):
            return ft
    raise ValueError(f"could not parse a known fault_type from case_id {case_id!r}")


def group_case_ids_by_fault_type(case_ids: Sequence[str]):
    groups = {ft: [] for ft in FAULT_TYPES}
    for cid in case_ids:
        groups[fault_type_of_case(cid)].append(cid)
    return groups


if __name__ == "__main__":
    # Synthetic sanity checks only -- no real model output.
    labels =      [False, False, True, True, True, False, True]
    predictions = [False, True,  True, True, False, False, True]
    cm = confusion_counts(labels, predictions)
    assert cm == dict(tp=3, fp=1, fn=1, tn=2), cm
    p = precision(cm["tp"], cm["fp"])
    r = recall(cm["tp"], cm["fn"])
    f1 = f1_score(cm["tp"], cm["fp"], cm["fn"])
    assert abs(p - 0.75) < 1e-9, p
    assert abs(r - 0.75) < 1e-9, r
    assert abs(f1 - 0.75) < 1e-9, f1

    assert detection_delay(inject_time=100.0, detection_time=107.0) == 7.0
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 2, 3]) == 2.5
    assert abs(pre_fault_false_positive_rate([False, False, True, False]) - 0.25) < 1e-9
    assert first_detection_time([10, 11, 12], [True, True, True], [False, False, True]) == 12
    assert first_detection_time([10, 11, 12], [True, True, True], [False, False, False]) is None

    assert fault_type_of_case("cartservice_cpu/3") == "cpu"
    assert fault_type_of_case("productcatalogservice_delay/1") == "delay"
    grouped = group_case_ids_by_fault_type(["cartservice_cpu/1", "cartservice_mem/1", "cartservice_loss/1"])
    assert grouped["cpu"] == ["cartservice_cpu/1"]
    assert grouped["mem"] == ["cartservice_mem/1"]
    assert grouped["loss"] == ["cartservice_loss/1"]
    assert grouped["delay"] == []

    print("metrics.py: all synthetic formula sanity checks passed")
    print(f"  example: precision={p}, recall={r}, f1={f1}")
