"""Symbolic (non-executing) pickle reader.

Interprets a pickle opcode stream with pickletools.genops and builds inert
data nodes. GLOBAL / STACK_GLOBAL / REDUCE / NEWOBJ / BUILD are recorded as
opaque nodes: no module is imported, no callable is invoked, so a hostile
pickle cannot execute code through this reader. Large byte payloads are not
retained, only their length.

This is static inspection, NOT deserialization: results are descriptions of
the stream (types, lengths, shapes), never live objects from the pickle.
"""
import hashlib
import pickletools


class Sym:
    """Opaque reference to module.name (from GLOBAL / STACK_GLOBAL). Never imported."""
    __slots__ = ("module", "name")

    def __init__(self, module, name):
        self.module, self.name = module, name

    def __repr__(self):
        return f"Sym({self.module}.{self.name})"


class Call:
    """Opaque call node: func(*args) recorded, never executed."""
    __slots__ = ("func", "args", "kind", "state")

    def __init__(self, func, args, kind="reduce"):
        self.func, self.args, self.kind, self.state = func, args, kind, None

    def __repr__(self):
        return f"Call({self.func!r})"


class RawBytes:
    """Placeholder for a bytes payload. `data` is kept only when keep_bytes=True."""
    __slots__ = ("length", "data", "digest")

    def __init__(self, length, data=None, digest=None):
        self.length, self.data, self.digest = length, data, digest

    def __repr__(self):
        return f"RawBytes({self.length})"


class PersId:
    """Opaque persistent-id reference (never resolved)."""
    __slots__ = ("pid",)

    def __init__(self, pid):
        self.pid = pid

    def __repr__(self):
        return f"PersId({self.pid!r})"


class _Mark:
    pass


MARK = _Mark()
_BYTES_OPS = {"SHORT_BINBYTES", "BINBYTES", "BINBYTES8", "BYTEARRAY8"}
_STR_OPS = {"UNICODE", "SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "STRING", "BINSTRING", "SHORT_BINSTRING"}
_INT_OPS = {"INT", "BININT", "BININT1", "BININT2", "LONG", "LONG1", "LONG4"}


class UnsupportedOpcode(Exception):
    pass


def read_symbolic(path_or_file, keep_bytes=False, hash_bytes=False):
    """Return the symbolic top-level object of a pickle stream.

    keep_bytes=True retains raw payload bytes on RawBytes.data (needed to parse
    embedded tensor storages as data); hash_bytes=True records an md5 digest on
    RawBytes.digest without retaining the payload. Default keeps only lengths.
    """
    opened = isinstance(path_or_file, (str, bytes)) or hasattr(path_or_file, "__fspath__")
    f = open(path_or_file, "rb") if opened else path_or_file
    try:
        return _run(f, keep_bytes, hash_bytes)
    finally:
        if opened:
            f.close()


def _pop_mark(stack):
    items = []
    while stack:
        top = stack.pop()
        if top is MARK:
            items.reverse()
            return items
        items.append(top)
    raise ValueError("pickle: MARK not found")


def _run(f, keep_bytes=False, hash_bytes=False):
    stack, memo = [], {}
    for op, arg, _pos in pickletools.genops(f):
        n = op.name
        if n in ("PROTO", "FRAME", "NOP"):
            continue
        if n == "STOP":
            return stack.pop()
        if n == "MARK":
            stack.append(MARK)
        elif n in _INT_OPS:
            stack.append(int(arg))
        elif n in ("FLOAT", "BINFLOAT"):
            stack.append(float(arg))
        elif n in _STR_OPS:
            stack.append(arg)
        elif n in _BYTES_OPS:
            stack.append(RawBytes(len(arg), bytes(arg) if keep_bytes else None,
                                  hashlib.md5(arg).hexdigest() if hash_bytes else None))
        elif n == "NONE":
            stack.append(None)
        elif n == "NEWTRUE":
            stack.append(True)
        elif n == "NEWFALSE":
            stack.append(False)
        elif n == "EMPTY_LIST":
            stack.append([])
        elif n == "EMPTY_TUPLE":
            stack.append(())
        elif n == "EMPTY_DICT":
            stack.append({})
        elif n == "EMPTY_SET":
            stack.append(set())
        elif n == "APPEND":
            v = stack.pop()
            stack[-1].append(v)
        elif n == "APPENDS":
            items = _pop_mark(stack)
            stack[-1].extend(items)
        elif n == "LIST":
            stack.append(_pop_mark(stack))
        elif n == "TUPLE":
            stack.append(tuple(_pop_mark(stack)))
        elif n == "TUPLE1":
            stack.append((stack.pop(),))
        elif n == "TUPLE2":
            b, a = stack.pop(), stack.pop()
            stack.append((a, b))
        elif n == "TUPLE3":
            c, b, a = stack.pop(), stack.pop(), stack.pop()
            stack.append((a, b, c))
        elif n == "DICT":
            items = _pop_mark(stack)
            stack.append({_key(items[i]): items[i + 1] for i in range(0, len(items), 2)})
        elif n == "SETITEM":
            v, k = stack.pop(), stack.pop()
            stack[-1][_key(k)] = v
        elif n == "SETITEMS":
            items = _pop_mark(stack)
            d = stack[-1]
            for i in range(0, len(items), 2):
                d[_key(items[i])] = items[i + 1]
        elif n == "ADDITEMS":
            items = _pop_mark(stack)
            for it in items:
                stack[-1].add(_key(it))
        elif n == "FROZENSET":
            stack.append(frozenset(_key(i) for i in _pop_mark(stack)))
        elif n == "GLOBAL":
            module, name = arg.split(" ", 1)
            stack.append(Sym(module, name))
        elif n == "STACK_GLOBAL":
            name, module = stack.pop(), stack.pop()
            stack.append(Sym(module, name))
        elif n == "REDUCE":
            args, func = stack.pop(), stack.pop()
            stack.append(Call(func, args))
        elif n == "NEWOBJ":
            args, cls = stack.pop(), stack.pop()
            stack.append(Call(cls, args, kind="newobj"))
        elif n == "NEWOBJ_EX":
            kwargs, args, cls = stack.pop(), stack.pop(), stack.pop()
            stack.append(Call(cls, (args, kwargs), kind="newobj_ex"))
        elif n in ("INST", "OBJ"):
            args = _pop_mark(stack)
            stack.append(Call(Sym(*arg.split(" ", 1)) if n == "INST" else args[0], tuple(args), kind=n.lower()))
        elif n == "BUILD":
            state = stack.pop()
            target = stack[-1]
            if isinstance(target, Call):
                target.state = state
        elif n == "PERSID":
            stack.append(PersId(arg))
        elif n == "BINPERSID":
            stack.append(PersId(stack.pop()))
        elif n == "POP":
            stack.pop()
        elif n == "POP_MARK":
            _pop_mark(stack)
        elif n == "DUP":
            stack.append(stack[-1])
        elif n in ("PUT", "BINPUT", "LONG_BINPUT"):
            memo[int(arg)] = stack[-1]
        elif n == "MEMOIZE":
            memo[len(memo)] = stack[-1]
        elif n in ("GET", "BINGET", "LONG_BINGET"):
            stack.append(memo[int(arg)])
        else:
            raise UnsupportedOpcode(n)
    raise ValueError("pickle stream ended without STOP")


def _key(k):
    """Dict/set keys must be hashable; opaque nodes are keyed by identity."""
    try:
        hash(k)
        return k
    except TypeError:
        return id(k)


def global_refs(obj, _seen=None, limit=10_000):
    """Collect every distinct module.name referenced anywhere in a symbolic tree."""
    refs, stack, seen = set(), [obj], set()
    while stack and len(seen) < limit * 1000:
        o = stack.pop()
        if id(o) in seen:
            continue
        if isinstance(o, (list, tuple, set, frozenset)):
            seen.add(id(o))
            stack.extend(o)
        elif isinstance(o, dict):
            seen.add(id(o))
            stack.extend(o.keys())
            stack.extend(o.values())
        elif isinstance(o, Sym):
            refs.add(f"{o.module}.{o.name}")
        elif isinstance(o, PersId):
            stack.append(o.pid)
        elif isinstance(o, Call):
            seen.add(id(o))
            stack.append(o.func)
            stack.append(o.args)
            stack.append(o.state)
    return sorted(refs)


def describe_array(node):
    """If node looks like a pickled numpy array, return {'shape','dtype','nbytes'} else None.

    Handles both numpy.core.multiarray._reconstruct + BUILD(state) and
    numpy._core.numeric._frombuffer forms. Uses only inert recorded values.
    """
    if not isinstance(node, Call) or not isinstance(node.func, Sym):
        return None
    fn = f"{node.func.module}.{node.func.name}"
    if fn.endswith("multiarray._reconstruct") and isinstance(node.state, tuple) and len(node.state) >= 5:
        shape, dt, raw = node.state[1], node.state[2], node.state[4]
        return {"shape": list(shape), "dtype": _dtype_str(dt),
                "nbytes": raw.length if isinstance(raw, RawBytes) else None}
    if fn.endswith("numeric._frombuffer") and isinstance(node.args, tuple) and len(node.args) >= 3:
        raw, dt, shape = node.args[0], node.args[1], node.args[2]
        return {"shape": list(shape) if isinstance(shape, tuple) else shape, "dtype": _dtype_str(dt),
                "nbytes": raw.length if isinstance(raw, RawBytes) else None}
    return None


def _dtype_str(dt):
    if isinstance(dt, Call) and isinstance(dt.args, tuple) and dt.args and isinstance(dt.args[0], str):
        return dt.args[0]
    return None
