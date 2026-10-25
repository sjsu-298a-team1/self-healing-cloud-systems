"""Read the numeric payload of a torch storage blob WITHOUT torch and without executing it.

`torch.storage._load_from_bytes(blob)` blobs are zip archives holding an inner
pickle (data.pkl, read here symbolically) and raw little-endian element data.
Only the dtype name and raw bytes are extracted; nothing is imported or called.
"""
import io
import struct
import zipfile

import pickle_symbolic as ps

# Storage class / dtype symbol names -> (numpy dtype string, itemsize)
_STORAGE_DTYPES = {
    "FloatStorage": ("<f4", 4), "DoubleStorage": ("<f8", 8), "HalfStorage": ("<f2", 2),
    "LongStorage": ("<i8", 8), "IntStorage": ("<i4", 4), "ShortStorage": ("<i2", 2),
    "CharStorage": ("i1", 1), "ByteStorage": ("u1", 1), "BoolStorage": ("?", 1),
    "float32": ("<f4", 4), "float64": ("<f8", 8), "float16": ("<f2", 2),
    "int64": ("<i8", 8), "int32": ("<i4", 4), "int16": ("<i2", 2),
    "int8": ("i1", 1), "uint8": ("u1", 1), "bool": ("?", 1),
}


_ITEMSIZE = {"<f4": 4, "<f8": 8, "<f2": 2, "<i8": 8, "<i4": 4, "<i2": 2, "i1": 1, "u1": 1, "?": 1}


class BlobFormatError(Exception):
    pass


_LEGACY_MAGIC = 0x1950A86A20F9469CFC6C


def _split_pickles(blob, count):
    """Split `count` consecutive pickle streams off the front of blob; return (pickles, offset)."""
    import pickletools
    f = io.BytesIO(blob)
    out, pos = [], 0
    for _ in range(count):
        f.seek(pos)
        for _op in pickletools.genops(f):
            pass
        end = f.tell()
        out.append(ps.read_symbolic(io.BytesIO(blob[pos:end])))
        pos = end
    return out, pos


def _parse_legacy_blob(blob):
    """Legacy (pre-1.6) torch.save layout: magic, protocol, sys_info, main pickle, keys, raw data."""
    try:
        (magic, proto, _sysinfo, main, keys), pos = _split_pickles(blob, 5)
    except Exception as exc:
        raise BlobFormatError(f"unrecognized storage blob format: {exc}") from exc
    if magic != _LEGACY_MAGIC:
        raise BlobFormatError("legacy magic number mismatch")
    if not isinstance(main, ps.PersId) or not isinstance(main.pid, tuple) or len(main.pid) < 5:
        raise BlobFormatError(f"unexpected main pickle: {main!r}")
    storage_cls, key, numel = main.pid[1], str(main.pid[2]), int(main.pid[4])
    dtype = _STORAGE_DTYPES.get(storage_cls.name, (None, None))[0] if isinstance(storage_cls, ps.Sym) else None
    if dtype is None or keys != [key]:
        raise BlobFormatError(f"cannot resolve dtype/key: cls={storage_cls!r} keys={keys!r}")
    itemsize = _ITEMSIZE[dtype]
    (stored_numel,) = struct.unpack("<q", blob[pos:pos + 8])
    data = blob[pos + 8:]
    if stored_numel != numel or len(data) != numel * itemsize:
        raise BlobFormatError(f"legacy storage length mismatch: numel={numel} stored={stored_numel} bytes={len(data)}")
    return {"dtype": dtype, "numel": numel, "data": data}


def parse_storage_blob(blob):
    """Return {'dtype': numpy-dtype-str, 'numel': int, 'data': bytes} for a storage blob.

    Supports the zip format (torch >= 1.6) and the legacy sequential-pickle format.
    """
    if not zipfile.is_zipfile(io.BytesIO(blob)):
        return _parse_legacy_blob(blob)
    z = zipfile.ZipFile(io.BytesIO(blob))
    names = z.namelist()
    pkl_names = [n for n in names if n.endswith("data.pkl")]
    if len(pkl_names) != 1:
        raise BlobFormatError(f"expected one data.pkl, found {pkl_names}")
    inner = ps.read_symbolic(io.BytesIO(z.read(pkl_names[0])))
    prefix = pkl_names[0][: -len("data.pkl")]
    dtype = key = numel = None
    refs = ps.global_refs(inner)
    for r in refs:
        short = r.rsplit(".", 1)[-1]
        if short in _STORAGE_DTYPES:
            dtype = _STORAGE_DTYPES[short][0]
    pid = _find_persid(inner)
    if pid is not None and isinstance(pid, tuple) and len(pid) >= 5:
        key, numel = str(pid[2]), int(pid[4])
    if dtype is None or key is None:
        raise BlobFormatError(f"cannot determine dtype/key from inner pickle: refs={refs} pid={pid}")
    entry = f"{prefix}data/{key}"
    if entry not in names:
        raise BlobFormatError(f"missing storage entry {entry}")
    data = z.read(entry)
    if len(data) != numel * _ITEMSIZE[dtype]:
        raise BlobFormatError(f"storage length {len(data)} != numel*itemsize {numel * _ITEMSIZE[dtype]}")
    return {"dtype": dtype, "numel": numel, "data": data}


def _find_persid(node, depth=0):
    if depth > 8:
        return None
    if isinstance(node, ps.PersId):
        return node.pid
    if isinstance(node, (list, tuple)):
        for x in node:
            r = _find_persid(x, depth + 1)
            if r is not None:
                return r
    if isinstance(node, ps.Call):
        for part in (node.args, node.state):
            r = _find_persid(part, depth + 1)
            if r is not None:
                return r
    return None


def tensor_to_array(tensor_node, np):
    """Materialize a symbolic torch._utils._rebuild_tensor_v2 node as a numpy array copy.

    tensor_node.args = (storage_call, storage_offset, size, stride, requires_grad, hooks).
    Only dense contiguous tensors with a stride matching C-order are supported.
    """
    if not (isinstance(tensor_node, ps.Call) and isinstance(tensor_node.func, ps.Sym)
            and tensor_node.func.name == "_rebuild_tensor_v2"):
        raise BlobFormatError("not a _rebuild_tensor_v2 node")
    storage, offset, size, stride = tensor_node.args[:4]
    blob = storage.args[0]
    if not isinstance(blob, ps.RawBytes) or blob.data is None:
        raise BlobFormatError("storage bytes not retained (use keep_bytes=True)")
    parsed = parse_storage_blob(blob.data)
    arr = np.frombuffer(parsed["data"], dtype=parsed["dtype"])
    shape = tuple(size)
    expect = []
    acc = 1
    for dim in reversed(shape):
        expect.append(acc)
        acc *= max(dim, 1)
    if tuple(reversed(expect)) != tuple(stride) and 0 not in shape:
        raise BlobFormatError(f"non-contiguous stride {stride} for shape {shape}")
    n = 1
    for d in shape:
        n *= d
    return arr[offset: offset + n].reshape(shape).copy()
