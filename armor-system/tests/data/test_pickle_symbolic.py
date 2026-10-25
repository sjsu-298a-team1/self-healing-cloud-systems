import io
import os
import pickle
import tempfile
import unittest

import _paths  # noqa: F401
import pickle_symbolic as ps

MARKER = os.path.join(tempfile.gettempdir(), "armor_pickle_symbolic_must_not_exist")


class Evil:
    def __reduce__(self):
        return (os.system, (f"touch {MARKER}",))


class PickleSymbolicTests(unittest.TestCase):
    def test_literals_match_real_pickle_for_all_protocols(self):
        data = {"a": [1, 2.5, "x", None, True, False, (3, 4)], "b": {"n": -7, "big": 2 ** 70},
                "s": "unicodé", "t": (), "l": [], "u": [(1,), (1, 2), (1, 2, 3, 4)]}
        for proto in (2, 3, 4, 5):
            blob = pickle.dumps(data, protocol=proto)
            expected = pickle.loads(blob)  # test-created data only
            self.assertEqual(ps.read_symbolic(io.BytesIO(blob)), expected, msg=f"protocol {proto}")

    def test_shared_references_via_memo(self):
        shared = [1, 2, 3]
        got = ps.read_symbolic(io.BytesIO(pickle.dumps({"x": shared, "y": shared}, protocol=4)))
        self.assertIs(got["x"], got["y"])

    def test_hostile_pickle_is_never_executed(self):
        if os.path.exists(MARKER):
            os.remove(MARKER)
        blob = pickle.dumps([Evil()], protocol=4)
        node = ps.read_symbolic(io.BytesIO(blob))
        self.assertFalse(os.path.exists(MARKER), "symbolic reader must not execute REDUCE")
        self.assertIsInstance(node[0], ps.Call)
        refs = ps.global_refs(node)
        self.assertTrue(any(r.endswith(".system") for r in refs), refs)

    def test_bytes_payloads_retain_only_length_by_default(self):
        blob = pickle.dumps({"k": b"abcdef"}, protocol=4)
        node = ps.read_symbolic(io.BytesIO(blob))["k"]
        self.assertEqual((node.length, node.data, node.digest), (6, None, None))
        kept = ps.read_symbolic(io.BytesIO(blob), keep_bytes=True)["k"]
        self.assertEqual(kept.data, b"abcdef")
        hashed = ps.read_symbolic(io.BytesIO(blob), hash_bytes=True)["k"]
        self.assertEqual(hashed.digest, "e80b5017098950fc58aad83c8c14978e")
        self.assertIsNone(hashed.data)

    def test_literal_only_pickles_have_no_globals(self):
        self.assertEqual(ps.global_refs(ps.read_symbolic(io.BytesIO(pickle.dumps({"a": [1, "b"]}, protocol=4)))), [])

    def test_truncated_stream_raises(self):
        blob = pickle.dumps([1, 2, 3], protocol=4)[:-3]
        with self.assertRaises(Exception):
            ps.read_symbolic(io.BytesIO(blob))


if __name__ == "__main__":
    unittest.main()
