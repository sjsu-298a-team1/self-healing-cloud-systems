"""Run ARMOR's unmodified `main.py` on a CPU-only machine.

    cd <isolated ARMOR copy> && <armor env python> run_armor_cpu.py --dataset D1 --run-id <run>

ARMOR's released D1 `model.pkl` is a plain pickle of the whole model saved on a CUDA device, and ARMOR loads it with
`pickle.Unpickler`, which calls torch's `_load_from_bytes` without a `map_location`; on a machine without CUDA that raises
"Attempting to deserialize object on a CUDA device". The only change made here is that tensor storages are mapped to the CPU when
the pickle is loaded, and xgboost is imported before torch (library load order only). No ARMOR file is edited and nothing else is patched; `main.py` then runs exactly as released (training, if the
run directory has no `model.pkl`, falls back to CPU in ARMOR's own code).

Run it from inside the ARMOR copy (ARMOR's imports and data paths are relative to its root). Must be copied there or invoked by path.
"""
import io
import os
import runpy
import sys

import xgboost  # noqa: F401  load before torch: xgboost >= 2.1 with conda's libomp segfaults on macOS x86_64 when torch's OpenMP loads first
import torch
import torch.storage

torch.storage._load_from_bytes = lambda b: torch.load(io.BytesIO(b), map_location="cpu")

if __name__ == "__main__":
    root = os.getcwd()
    if not os.path.isfile(os.path.join(root, "main.py")):
        raise SystemExit("run from the root of an ARMOR copy (main.py not found in the current directory)")
    sys.path.insert(0, root)
    sys.argv = [os.path.join(root, "main.py")] + sys.argv[1:]
    runpy.run_path(sys.argv[0], run_name="__main__")
