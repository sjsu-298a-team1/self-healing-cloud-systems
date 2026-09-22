"""
Model 1 Phase 2: LSTM encoder-decoder autoencoder architecture tests.

Synthetic tensors only -- no real telemetry, no BARO data, no training. Proves
the architecture is correct and trainable (forward + backward pass), not that
it has learned anything. No optimizer step is ever taken.

Usage:
    python3 test_lstm_autoencoder_architecture.py
"""
import os
import sys

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models", "model1"))

from lstm_autoencoder import LSTMAutoencoder, LSTMAutoencoderConfig, count_trainable_parameters

torch.manual_seed(0)


def check_output_shape_matches_input(model, config):
    x = torch.randn(4, config.sequence_length, config.input_size)
    out = model(x)
    return [] if tuple(out.shape) == tuple(x.shape) else [f"expected {tuple(x.shape)}, got {tuple(out.shape)}"]


def check_batch_size_one(model, config):
    x = torch.randn(1, config.sequence_length, config.input_size)
    out = model(x)
    return [] if tuple(out.shape) == (1, config.sequence_length, config.input_size) else [f"batch=1 failed: got {tuple(out.shape)}"]


def check_multiple_batch_sizes(model, config):
    failures = []
    for b in (1, 2, 4, 8, 16, 32):
        x = torch.randn(b, config.sequence_length, config.input_size)
        out = model(x)
        if tuple(out.shape) != (b, config.sequence_length, config.input_size):
            failures.append(f"batch={b}: got {tuple(out.shape)}")
    return failures


def check_no_fixed_batch_size_assumption(model, config):
    """Same model instance, different batch sizes, run back-to-back -- proves
    no batch dimension is baked into any buffer/shape at construction time."""
    failures = []
    for b in (3, 7, 1, 16):
        x = torch.randn(b, config.sequence_length, config.input_size)
        try:
            out = model(x)
        except Exception as e:
            failures.append(f"batch={b} raised {type(e).__name__}: {e}")
            continue
        if out.shape[0] != b:
            failures.append(f"batch={b}: output batch dim is {out.shape[0]}")
    return failures


def check_output_finite(model, config):
    x = torch.randn(8, config.sequence_length, config.input_size)
    out = model(x)
    if not torch.isfinite(out).all():
        return ["output contains NaN or Inf values"]
    return []


def check_backward_pass_and_gradients(model, config):
    failures = []
    model.zero_grad()
    x = torch.randn(6, config.sequence_length, config.input_size)
    out = model(x)
    loss = torch.mean((out - x) ** 2)  # reconstruction-style loss, synthetic target only
    try:
        loss.backward()
    except Exception as e:
        return [f"backward() raised {type(e).__name__}: {e}"]

    no_grad_params = []
    zero_grad_params = []
    any_nonzero = False
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if p.grad is None:
            no_grad_params.append(name)
            continue
        if torch.count_nonzero(p.grad) == 0:
            zero_grad_params.append(name)
        else:
            any_nonzero = True

    if no_grad_params:
        failures.append(f"{len(no_grad_params)} trainable param(s) received no gradient at all: {no_grad_params}")
    if not any_nonzero:
        failures.append("no trainable parameter received a nonzero gradient")
    return failures


def check_exactly_55_features(model, config):
    failures = []
    if config.input_size != 55:
        failures.append(f"config.input_size = {config.input_size}, expected 55")
    if model.encoder.input_size != 55:
        failures.append(f"encoder input_size = {model.encoder.input_size}, expected 55")
    if model.output_layer.out_features != 55:
        failures.append(f"output_layer.out_features = {model.output_layer.out_features}, expected 55")
    # Wrong feature dim must fail loudly, not silently reshape/truncate.
    bad_x = torch.randn(2, config.sequence_length, 40)
    try:
        model(bad_x)
        failures.append("model accepted a 40-feature input without error (expected a shape error)")
    except RuntimeError:
        pass  # expected: nn.LSTM rejects mismatched input_size
    return failures


def check_deep_config_variant():
    """Proves the advertised num_layers/dropout configurability actually works --
    a second, deeper configuration (num_layers=2, dropout=0.1), not the default.
    This does not change or replace the default configuration (num_layers=1,
    dropout=0.0); it only demonstrates the config knob is real."""
    failures = []
    config = LSTMAutoencoderConfig(
        input_size=55, hidden_size=64, latent_size=32, num_layers=2, dropout=0.1
    )
    model = LSTMAutoencoder(config)

    x = torch.randn(4, 30, 55)
    try:
        latent = model.encode(x)
        recon = model.decode(latent, sequence_length=30)
    except Exception as e:
        return [f"forward pass raised {type(e).__name__}: {e}"]

    if tuple(recon.shape) != (4, 30, 55):
        failures.append(f"reconstruction shape: expected (4, 30, 55), got {tuple(recon.shape)}")
    if tuple(latent.shape) != (4, 32):
        failures.append(f"latent shape: expected (4, 32), got {tuple(latent.shape)}")

    model.zero_grad()
    loss = torch.mean((recon - x) ** 2)
    try:
        loss.backward()
    except Exception as e:
        return failures + [f"backward() raised {type(e).__name__}: {e}"]

    no_grad_params = [name for name, p in model.named_parameters() if p.requires_grad and p.grad is None]
    if no_grad_params:
        failures.append(f"{len(no_grad_params)} trainable param(s) received no gradient: {no_grad_params}")

    return failures


def main():
    config = LSTMAutoencoderConfig()
    model = LSTMAutoencoder(config)
    n_params = count_trainable_parameters(model)

    # Architecture summary (synthetic tensor only)
    x = torch.randn(4, config.sequence_length, config.input_size)
    encoder_raw_out, (h_n, c_n) = model.encoder(x)
    latent = model.encode(x)
    recon = model.decode(latent, config.sequence_length)

    print("=== Architecture summary ===")
    print(f"Config: {config}")
    print(f"Total trainable parameters: {n_params:,}")
    print(f"Input shape:                {tuple(x.shape)}")
    print(f"Encoder raw output shape:   {tuple(encoder_raw_out.shape)}  (batch, seq_len, hidden_size)")
    print(f"Encoder final hidden shape: {tuple(h_n[-1].shape)}  (batch, hidden_size)")
    print(f"Latent representation shape:{tuple(latent.shape)}  (batch, latent_size)")
    print(f"Decoder output shape:       {tuple(recon.shape)}  (batch, seq_len, input_size)")
    print()

    checks = {
        "output_shape_matches_input": check_output_shape_matches_input(model, config),
        "batch_size_one": check_batch_size_one(model, config),
        "multiple_batch_sizes": check_multiple_batch_sizes(model, config),
        "no_fixed_batch_size_assumption": check_no_fixed_batch_size_assumption(model, config),
        "output_finite": check_output_finite(model, config),
        "backward_pass_and_gradients": check_backward_pass_and_gradients(model, config),
        "exactly_55_features": check_exactly_55_features(model, config),
        "deep_config_variant_num_layers_2_dropout_0.1": check_deep_config_variant(),
    }

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL ARCHITECTURE TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
