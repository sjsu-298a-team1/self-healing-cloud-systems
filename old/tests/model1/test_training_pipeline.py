"""
Model 1 Phase 3: training-pipeline tests.

Most checks use synthetic/small tensors only -- this file never calls train.py's
main() (which would build the real 4,020-window training set and constitute a
real training run). A tiny smoke run (a handful of synthetic windows, a couple
of epochs) is used to exercise the actual training/checkpoint/save logic, per
the phase's explicit allowance for that.

A few checks (validation-region correctness) do load real BARO data via
--data-dir -- but only to build windows and inspect their timestamps, never to
run any training step against them.

Usage:
    python3 test_training_pipeline.py --data-dir <BARO_DATA_DIR>
"""
import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
from unittest import mock

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "training"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "data"))

import train  # noqa: E402
from dataset import (  # noqa: E402
    DEFAULT_CONFIGS_DIR,
    DEFAULT_MANIFESTS_DIR,
    EVAL_STRIDE,
    build_eval_windows,
    build_model_selection_validation_windows,
    build_train_windows,
    load_case_df,
    load_features,
    load_manifest,
    load_scaler,
)

TINY_CONFIG = {
    "model": {
        "input_size": 55,
        "sequence_length": 30,
        "hidden_size": 8,
        "latent_size": 4,
        "num_layers": 1,
        "dropout": 0.0,
    },
    "optimizer": {"learning_rate": 0.01},
    "batch_size": 4,
    "max_epochs": 3,
    "early_stopping": {"patience_epochs": 100},  # effectively disabled for this smoke test
    "seed": {"value": 123},
}


def check_training_step_updates_parameters():
    train.set_seeds(123)
    model, _ = train.build_model_from_config(TINY_CONFIG)
    optimizer = torch.optim.Adam(model.parameters(), lr=TINY_CONFIG["optimizer"]["learning_rate"])
    generator = torch.Generator().manual_seed(123)

    before = [p.clone().detach() for p in model.parameters()]
    windows = torch.randn(12, 30, 55)
    loss = train.train_one_epoch(model, windows, optimizer, batch_size=4, generator=generator)
    after = [p.clone().detach() for p in model.parameters()]

    failures = []
    if not (loss == loss):  # NaN check
        failures.append("training loss is NaN")
    if not torch.isfinite(torch.tensor(loss)):
        failures.append(f"training loss is not finite: {loss}")
    any_changed = any(not torch.equal(b, a) for b, a in zip(before, after))
    if not any_changed:
        failures.append("no parameter changed after one training step")
    return failures


def check_validation_step_does_not_update_parameters():
    train.set_seeds(123)
    model, _ = train.build_model_from_config(TINY_CONFIG)
    windows = torch.randn(8, 30, 55)

    before = [p.clone().detach() for p in model.parameters()]
    loss = train.evaluate_loss(model, windows)
    after = [p.clone().detach() for p in model.parameters()]

    failures = []
    if not torch.isfinite(torch.tensor(loss)):
        failures.append(f"validation loss is not finite: {loss}")
    unchanged = all(torch.equal(b, a) for b, a in zip(before, after))
    if not unchanged:
        failures.append("a parameter changed during evaluate_loss (validation must not update parameters)")
    return failures


def check_best_checkpoint_uses_validation_loss():
    tracker = train.BestCheckpointTracker()
    val_losses = [0.5, 0.3, 0.4, 0.2, 0.25]
    is_best_flags = [tracker.update(epoch=i + 1, val_loss=v) for i, v in enumerate(val_losses)]

    failures = []
    expected_best_flags = [True, True, False, True, False]
    if is_best_flags != expected_best_flags:
        failures.append(f"expected is_best sequence {expected_best_flags}, got {is_best_flags}")
    if tracker.best_val_loss != 0.2:
        failures.append(f"expected best_val_loss=0.2, got {tracker.best_val_loss}")
    if tracker.best_epoch != 4:
        failures.append(f"expected best_epoch=4, got {tracker.best_epoch}")
    return failures


def check_early_stopper_uses_validation_loss_only():
    stopper = train.EarlyStopper(patience_epochs=3)
    # 3 consecutive non-improvements should trigger stop; an improvement resets the counter.
    is_best_sequence = [True, False, True, False, False, False]
    stopped_at = None
    for i, is_best in enumerate(is_best_sequence):
        if stopper.step(is_best):
            stopped_at = i
            break
    return [] if stopped_at == 5 else [f"expected early stop at index 5, got {stopped_at}"]


def check_deterministic_seed_setup():
    train.set_seeds(999)
    model_a, _ = train.build_model_from_config(TINY_CONFIG)
    train.set_seeds(999)
    model_b, _ = train.build_model_from_config(TINY_CONFIG)

    failures = []
    for (name_a, p_a), (name_b, p_b) in zip(model_a.named_parameters(), model_b.named_parameters()):
        if not torch.equal(p_a, p_b):
            failures.append(f"parameter {name_a} differs between two set_seeds(999)-then-init runs")
    return failures


def check_training_code_never_loads_test_manifest():
    """AST-based (not string-search) check: inspects every actual call to
    load_manifest(...) in train.py's source and confirms 'test' is never one
    of its literal arguments. Deliberately ignores comments/docstrings (which
    may legitimately mention 'test_cases.json' to document its absence) --
    only real Call nodes count."""
    import ast

    train_py_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "training", "train.py"
    )
    with open(train_py_path) as f:
        source = f.read()
    tree = ast.parse(source)

    load_manifest_call_args = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_manifest":
            if node.args and isinstance(node.args[0], ast.Constant):
                load_manifest_call_args.append(node.args[0].value)

    failures = []
    if "test" in load_manifest_call_args:
        failures.append(f"train.py calls load_manifest(\"test\", ...); all calls found: {load_manifest_call_args}")
    # Sanity: the check above isn't vacuous -- train.py DOES call load_manifest
    # for train/val, so the absence of 'test' is a meaningful, checked fact.
    if "train" not in load_manifest_call_args or "val" not in load_manifest_call_args:
        failures.append(f"expected load_manifest('train'/'val', ...) calls not found (check may be vacuous); found: {load_manifest_call_args}")
    return failures


def check_saved_metadata_sufficient_to_reproduce():
    run_dir = tempfile.mkdtemp(prefix="model1_test_run_")
    try:
        train.set_seeds(TINY_CONFIG["seed"]["value"])
        train_windows = torch.randn(12, 30, 55)
        val_windows = torch.randn(8, 30, 55)
        model, history, tracker = train.run_training_loop(
            train_windows, val_windows, TINY_CONFIG, run_dir, run_id="test_run",
        )

        failures = []
        for fname in ("config_snapshot.json", "training_history.json", "run_metadata.json"):
            if not os.path.exists(os.path.join(run_dir, fname)):
                failures.append(f"missing output file: {fname}")
        if not os.path.exists(os.path.join(run_dir, "checkpoints", "best.pt")):
            failures.append("missing checkpoints/best.pt")

        with open(os.path.join(run_dir, "config_snapshot.json")) as f:
            config_snapshot = json.load(f)
        with open(os.path.join(run_dir, "run_metadata.json")) as f:
            run_metadata = json.load(f)
        with open(os.path.join(run_dir, "training_history.json")) as f:
            history_json = json.load(f)

        required_config_fields = ["model", "optimizer", "batch_size", "max_epochs", "seed"]
        for field in required_config_fields:
            if field not in config_snapshot.get("training_config", {}):
                failures.append(f"config_snapshot.json missing training_config.{field}")
        if "n_trainable_parameters" not in config_snapshot:
            failures.append("config_snapshot.json missing n_trainable_parameters")

        required_metadata_fields = [
            "best_epoch", "best_val_loss", "epochs_run", "runtime_sec", "device",
            "python_version", "torch_version",
        ]
        for field in required_metadata_fields:
            if field not in run_metadata:
                failures.append(f"run_metadata.json missing {field}")

        if len(history_json) != len(history):
            failures.append("training_history.json length does not match in-memory history")
        for entry in history_json:
            for field in ("epoch", "train_loss", "val_loss", "is_best"):
                if field not in entry:
                    failures.append(f"training_history.json entry missing '{field}'")
                    break

        return failures
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def check_train_windows_strictly_pre_fault_real_data(data_dir, configs_dir, manifests_dir):
    """Every training window used for optimization is strictly pre-injection,
    using train.py's actual code path (build_train_windows on the real train
    manifest against real BARO data)."""
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    train_cases = load_manifest("train", manifests_dir)

    windows, metadata = build_train_windows(data_dir, train_cases, features, scaler)

    inject_times = {}
    for cid in train_cases:
        combo, run_id = cid.split("/")
        with open(os.path.join(data_dir, combo, run_id, "inject_time.txt")) as f:
            inject_times[cid] = int(f.read().strip())

    violations = [m for m in metadata if m["end_time"] >= inject_times[m["case_id"]]]
    failures = []
    if violations:
        failures.append(f"{len(violations)} training window(s) include a post-injection row: {violations[:3]}")
    print(f"  (train windows checked: {windows.shape[0]})")
    return failures


def check_model_selection_validation_windows_strictly_pre_fault(data_dir, configs_dir, manifests_dir):
    """Every validation window used for early stopping/checkpoint selection is
    strictly pre-injection (t < 360 relative to that case). Reports the exact
    count and proves every single one has end_time < inject_time."""
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    val_cases = load_manifest("val", manifests_dir)

    windows, metadata = build_model_selection_validation_windows(data_dir, val_cases, features, scaler)

    inject_times = {}
    for cid in val_cases:
        combo, run_id = cid.split("/")
        with open(os.path.join(data_dir, combo, run_id, "inject_time.txt")) as f:
            inject_times[cid] = int(f.read().strip())

    violations = [m for m in metadata if m["end_time"] >= inject_times[m["case_id"]]]
    failures = []
    if violations:
        failures.append(f"{len(violations)} model-selection validation window(s) include a post-injection row: {violations[:3]}")
    if windows.shape[0] == 0:
        failures.append("zero model-selection validation windows built -- test would be vacuous")

    print(f"  Model-selection validation windows: {windows.shape[0]} (all from {len(val_cases)} val cases)")
    print(f"  All end_times < inject_time: {len(violations) == 0} (0 violations out of {len(metadata)})")
    return failures, windows.shape[0]


def check_full_validation_timeline_not_used_in_training(data_dir, configs_dir, manifests_dir):
    """The full (pre+post) validation timeline must NOT be what feeds
    val_reconstruction_loss during training -- confirmed by showing the
    model-selection window count is strictly smaller than the full eval-window
    count for the same cases (the full timeline includes ~2x as many rows per
    case: pre-fault AND post-fault, at the same stride)."""
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    val_cases = load_manifest("val", manifests_dir)

    model_selection_windows, _ = build_model_selection_validation_windows(data_dir, val_cases, features, scaler)
    full_eval_windows, full_eval_metadata = build_eval_windows(data_dir, val_cases, features, scaler, stride=EVAL_STRIDE)

    failures = []
    if model_selection_windows.shape[0] >= full_eval_windows.shape[0]:
        failures.append(
            f"model-selection windows ({model_selection_windows.shape[0]}) should be strictly fewer than "
            f"full eval windows ({full_eval_windows.shape[0]}) for the same cases/stride"
        )
    post_injection_present_in_full = any(m["region"] == "post_injection_evaluation_region" for m in full_eval_metadata)
    if not post_injection_present_in_full:
        failures.append("full eval windows unexpectedly contain no post-injection-region windows -- check may be vacuous")

    print(f"  Model-selection (pre-fault only) windows: {model_selection_windows.shape[0]}")
    print(f"  Full pre+post eval windows (NOT used in training): {full_eval_windows.shape[0]}")
    return failures


def check_train_loader_shuffles_val_loader_does_not():
    """train_one_epoch shuffles (via torch.randperm); evaluate_loss does not
    (strict sequential range()). Verified by spying on torch.randperm."""
    train.set_seeds(7)
    model, _ = train.build_model_from_config(TINY_CONFIG)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    generator = torch.Generator().manual_seed(7)
    train_windows = torch.randn(12, 30, 55)
    val_windows = torch.randn(8, 30, 55)

    failures = []
    with mock.patch("torch.randperm", wraps=torch.randperm) as spy_randperm:
        train.train_one_epoch(model, train_windows, optimizer, batch_size=4, generator=generator)
        if spy_randperm.call_count == 0:
            failures.append("train_one_epoch never called torch.randperm -- shuffling not confirmed")

    with mock.patch("torch.randperm", wraps=torch.randperm) as spy_randperm:
        train.evaluate_loss(model, val_windows)
        if spy_randperm.call_count != 0:
            failures.append(f"evaluate_loss called torch.randperm {spy_randperm.call_count} time(s) -- validation must not shuffle")

    return failures


def check_validation_runs_under_eval_mode_and_no_grad():
    """Registers a forward hook to directly observe model.training and
    torch.is_grad_enabled() at the moment evaluate_loss actually invokes the
    model -- direct proof of model.eval() + torch.no_grad(), not an inference
    from side effects."""
    train.set_seeds(11)
    model, _ = train.build_model_from_config(TINY_CONFIG)
    windows = torch.randn(8, 30, 55)

    observed = []

    def hook(module, inputs):
        observed.append((module.training, torch.is_grad_enabled()))

    handle = model.register_forward_pre_hook(hook)
    try:
        model.train()  # deliberately start in train mode
        train.evaluate_loss(model, windows)
    finally:
        handle.remove()

    failures = []
    if not observed:
        failures.append("forward hook never fired -- check is vacuous")
    if any(training for training, _ in observed):
        failures.append(f"model.training was True during evaluate_loss's forward call(s): {observed}")
    if any(grad_enabled for _, grad_enabled in observed):
        failures.append(f"torch.is_grad_enabled() was True during evaluate_loss's forward call(s): {observed}")
    return failures


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    args = parser.parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))

    model_selection_failures, n_model_selection_windows = check_model_selection_validation_windows_strictly_pre_fault(
        data_dir, args.configs_dir, args.manifests_dir
    )

    checks = {
        "training_step_updates_parameters": check_training_step_updates_parameters(),
        "validation_step_does_not_update_parameters": check_validation_step_does_not_update_parameters(),
        "best_checkpoint_uses_validation_loss": check_best_checkpoint_uses_validation_loss(),
        "early_stopper_uses_validation_loss_only": check_early_stopper_uses_validation_loss_only(),
        "deterministic_seed_setup": check_deterministic_seed_setup(),
        "training_code_never_loads_test_manifest": check_training_code_never_loads_test_manifest(),
        "saved_metadata_sufficient_to_reproduce": check_saved_metadata_sufficient_to_reproduce(),
        "train_windows_strictly_pre_fault_real_data": check_train_windows_strictly_pre_fault_real_data(
            data_dir, args.configs_dir, args.manifests_dir
        ),
        "model_selection_validation_windows_strictly_pre_fault": model_selection_failures,
        "full_validation_timeline_not_used_in_training": check_full_validation_timeline_not_used_in_training(
            data_dir, args.configs_dir, args.manifests_dir
        ),
        "train_loader_shuffles_val_loader_does_not": check_train_loader_shuffles_val_loader_does_not(),
        "validation_runs_under_eval_mode_and_no_grad": check_validation_runs_under_eval_mode_and_no_grad(),
    }
    print(f"\n(model-selection validation windows built: {n_model_selection_windows})\n")

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL TRAINING PIPELINE TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
