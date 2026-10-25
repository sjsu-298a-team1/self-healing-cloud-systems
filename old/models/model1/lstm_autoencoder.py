"""
Model 1: multivariate LSTM encoder-decoder autoencoder -- architecture only.

Phase 2 of the locked protocol (see docs/model1/protocol/protocol.md). This file
defines the network architecture and nothing else: no optimizer, no training
loop, no threshold selection, no anomaly scoring, no checkpointing. It is
exercised only by tests/model1/test_lstm_autoencoder_architecture.py against
synthetic tensors -- never against real telemetry, and never trained.

Locked input contract (from configs/model1/protocol_config.json /
scripts/model1/data/dataset.py): input is (batch_size, 30, 55) -- 30 timesteps
(the locked window length) of the 55 locked telemetry features. Output is a
reconstruction of the same shape.
"""
from dataclasses import dataclass
from typing import Optional

import torch
from torch import nn


@dataclass
class LSTMAutoencoderConfig:
    """Architecture hyperparameters. Nothing here has been tuned -- these are a
    reasonable, deliberately small starting configuration (see rationale in
    docs/model1/protocol/protocol.md and the commit/PR description for this
    phase), not experimentally chosen values. Any future tuning must happen on
    the validation split only, per the locked protocol.
    """

    input_size: int = 55        # locked: the 55 committed telemetry features
    sequence_length: int = 30   # locked: the 30-step window length
    hidden_size: int = 64       # LSTM hidden/cell state width
    latent_size: int = 32       # bottleneck width; None/== hidden_size disables
                                 # the extra projection (encoder hidden state used
                                 # directly as the latent vector)
    num_layers: int = 1         # stacked LSTM layers, encoder and decoder alike
    dropout: float = 0.0        # inter-layer dropout; only has any effect when
                                 # num_layers > 1 (PyTorch applies it between
                                 # stacked LSTM layers, not within a single layer)

    def __post_init__(self):
        if self.latent_size is None:
            self.latent_size = self.hidden_size


class LSTMAutoencoder(nn.Module):
    """Encoder LSTM -> latent vector -> decoder LSTM -> per-timestep linear
    projection back to input_size. Batch-size agnostic (nn.LSTM with
    batch_first=True imposes no fixed batch dimension); sequence length is
    passed explicitly to decode() so it isn't hardcoded into the module either,
    though the locked protocol always uses sequence_length=30 windows.
    """

    def __init__(self, config: Optional[LSTMAutoencoderConfig] = None):
        super().__init__()
        self.config = config or LSTMAutoencoderConfig()
        c = self.config

        self.encoder = nn.LSTM(
            input_size=c.input_size,
            hidden_size=c.hidden_size,
            num_layers=c.num_layers,
            batch_first=True,
            dropout=c.dropout if c.num_layers > 1 else 0.0,
        )

        self._has_latent_projection = c.latent_size != c.hidden_size
        if self._has_latent_projection:
            self.to_latent = nn.Linear(c.hidden_size, c.latent_size)
            self.from_latent = nn.Linear(c.latent_size, c.hidden_size)
        else:
            self.to_latent = nn.Identity()
            self.from_latent = nn.Identity()

        # Decoder consumes the (projected-back-to-hidden_size) latent context,
        # repeated at every timestep, as its input -- a standard, simple
        # reconstruction-decoder input scheme for sequence autoencoders.
        self.decoder = nn.LSTM(
            input_size=c.hidden_size,
            hidden_size=c.hidden_size,
            num_layers=c.num_layers,
            batch_first=True,
            dropout=c.dropout if c.num_layers > 1 else 0.0,
        )

        self.output_layer = nn.Linear(c.hidden_size, c.input_size)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, input_size) -> latent: (batch, latent_size)."""
        _, (h_n, _) = self.encoder(x)
        h_last = h_n[-1]  # final layer's final hidden state: (batch, hidden_size)
        return self.to_latent(h_last)

    def decode(self, latent: torch.Tensor, sequence_length: int) -> torch.Tensor:
        """latent: (batch, latent_size) -> reconstruction: (batch, sequence_length, input_size)."""
        batch_size = latent.shape[0]
        context = self.from_latent(latent)  # (batch, hidden_size)

        decoder_input = context.unsqueeze(1).expand(batch_size, sequence_length, -1)
        h0 = context.unsqueeze(0).expand(self.config.num_layers, batch_size, -1).contiguous()
        c0 = torch.zeros_like(h0)

        decoder_out, _ = self.decoder(decoder_input, (h0, c0))  # (batch, seq_len, hidden_size)
        return self.output_layer(decoder_out)  # (batch, seq_len, input_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (batch, seq_len, input_size) -> reconstruction of the same shape."""
        latent = self.encode(x)
        return self.decode(latent, sequence_length=x.shape[1])


def count_trainable_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    # Architecture summary only -- synthetic tensor, no training, no real data.
    config = LSTMAutoencoderConfig()
    model = LSTMAutoencoder(config)
    print(f"Config: {config}")
    print(f"Total trainable parameters: {count_trainable_parameters(model):,}")

    x = torch.randn(4, config.sequence_length, config.input_size)
    latent = model.encode(x)
    recon = model.decode(latent, config.sequence_length)
    print(f"Input shape:  {tuple(x.shape)}")
    print(f"Latent shape: {tuple(latent.shape)}")
    print(f"Output shape: {tuple(recon.shape)}")
