import io
import pickle
import struct
import sys
import types
import unittest
import zipfile

import _paths  # noqa: F401
import pickle_symbolic as ps
import torch_blob as tb

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


class _FakeTorch:
    """Pickle fake `torch.FloatStorage` by reference without importing real torch."""

    def __enter__(self):
        mod = types.ModuleType("torch")

        class FloatStorage:
            pass

        FloatStorage.__module__, FloatStorage.__qualname__ = "torch", "FloatStorage"
        mod.FloatStorage = FloatStorage
        self.prev = sys.modules.get("torch")
        sys.modules["torch"] = mod
        self.cls = FloatStorage
        return self

    def __exit__(self, *a):
        if self.prev is None:
            del sys.modules["torch"]
        else:
            sys.modules["torch"] = self.prev


class _P(pickle.Pickler):
    def __init__(self, f, obj_to_pid, protocol):
        super().__init__(f, protocol=protocol)
        self._map = obj_to_pid

    def persistent_id(self, obj):
        return self._map.get(id(obj))


def legacy_blob(cls, values):
    raw = struct.pack(f"<{len(values)}f", *values)
    marker = object()
    out = io.BytesIO()
    pickle.dump(0x1950A86A20F9469CFC6C, out, protocol=2)
    pickle.dump(1001, out, protocol=2)
    pickle.dump({"protocol_version": 1001, "little_endian": True}, out, protocol=2)
    _P(out, {id(marker): ("storage", cls, "42", "cpu", len(values), None)}, 2).dump(marker)
    pickle.dump(["42"], out, protocol=2)
    out.write(struct.pack("<q", len(values)) + raw)
    return out.getvalue()


def zip_blob(cls, values):
    raw = struct.pack(f"<{len(values)}f", *values)
    marker = object()
    pkl = io.BytesIO()
    _P(pkl, {id(marker): ("storage", cls, "0", "cpu", len(values))}, 2).dump(marker)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("archive/data.pkl", pkl.getvalue())
        z.writestr("archive/data/0", raw)
    return buf.getvalue()


def tensor_node(blob, size, stride):
    storage = ps.Call(ps.Sym("torch.storage", "_load_from_bytes"), (ps.RawBytes(len(blob), blob),))
    return ps.Call(ps.Sym("torch._utils", "_rebuild_tensor_v2"), (storage, 0, size, stride, False, None))


class TorchBlobTests(unittest.TestCase):
    def test_legacy_and_zip_blobs_parse_identically(self):
        vals = [1.5, -2.0, 0.0, 3.25, 7.0, 8.5]
        with _FakeTorch() as ft:
            for make in (legacy_blob, zip_blob):
                parsed = tb.parse_storage_blob(make(ft.cls, vals))
                self.assertEqual((parsed["dtype"], parsed["numel"]), ("<f4", 6))
                self.assertEqual(struct.unpack("<6f", parsed["data"]), tuple(vals))

    def test_length_mismatch_is_rejected(self):
        with _FakeTorch() as ft:
            blob = legacy_blob(ft.cls, [1.0, 2.0, 3.0])
            with self.assertRaises(tb.BlobFormatError):
                tb.parse_storage_blob(blob[:-4])

    def test_garbage_is_rejected(self):
        with self.assertRaises(tb.BlobFormatError):
            tb.parse_storage_blob(b"not a torch blob at all")

    @unittest.skipIf(np is None, "numpy not installed")
    def test_tensor_to_array_roundtrip_and_stride_check(self):
        vals = [float(i) for i in range(6)]
        with _FakeTorch() as ft:
            blob = legacy_blob(ft.cls, vals)
        arr = tb.tensor_to_array(tensor_node(blob, (2, 3), (3, 1)), np)
        self.assertEqual(arr.tolist(), [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]])
        with self.assertRaises(tb.BlobFormatError):
            tb.tensor_to_array(tensor_node(blob, (2, 3), (1, 2)), np)

    @unittest.skipIf(np is None, "numpy not installed")
    def test_requires_retained_bytes(self):
        node = tensor_node(b"x", (1,), (1,))
        node.args[0].args[0].data = None
        with self.assertRaises(tb.BlobFormatError):
            tb.tensor_to_array(node, np)


if __name__ == "__main__":
    unittest.main()
