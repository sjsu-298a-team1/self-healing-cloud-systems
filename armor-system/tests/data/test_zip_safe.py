import http.server
import os
import stat
import tempfile
import threading
import unittest
import zipfile

import _paths  # noqa: F401
import zip_safe as zs


class RangeHandler(http.server.BaseHTTPRequestHandler):
    payload = b""

    def log_message(self, *a):
        pass

    def do_GET(self):
        total = len(self.payload)
        rng = self.headers.get("Range")
        if rng:
            a, b = rng.split("=")[1].split("-")
            a, b = int(a), min(int(b), total - 1)
            body = self.payload[a:b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{total}")
        else:
            body = self.payload
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(payload):
    handler = type("H", (RangeHandler,), {"payload": payload})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/a.zip"


def build_zip(path, members):
    with zipfile.ZipFile(path, "w") as z:
        for name, data, ctype in members:
            z.writestr(zipfile.ZipInfo(name), data, compress_type=ctype)


class SafePathTests(unittest.TestCase):
    def test_rejects_traversal_and_absolute(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ["../x", "a/../../x", "/etc/passwd", "a\\b", "C:evil", ""]:
                with self.assertRaises(zs.UnsafeArchiveError, msg=bad):
                    zs.safe_member_path(d, bad)

    def test_accepts_nested_relative(self):
        with tempfile.TemporaryDirectory() as d:
            p = zs.safe_member_path(d, "a/b/c.txt")
            self.assertTrue(p.startswith(os.path.realpath(d)))

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            os.symlink(outside, os.path.join(d, "link"))
            with self.assertRaises(zs.UnsafeArchiveError):
                zs.safe_member_path(d, "link/x.txt")

    def test_limits(self):
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "z.zip")
            build_zip(zp, [("a.txt", b"x" * 5000, zipfile.ZIP_DEFLATED)])
            with zipfile.ZipFile(zp) as z:
                with self.assertRaises(zs.UnsafeArchiveError):
                    zs.check_archive_limits(z.infolist(), max_total=100)
                with self.assertRaises(zs.UnsafeArchiveError):
                    zs.check_archive_limits(z.infolist(), max_ratio=2.0)
                self.assertEqual(zs.check_archive_limits(z.infolist()), 5000)


class ExtractTests(unittest.TestCase):
    def test_extracts_and_skips_macosx(self):
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "z.zip")
            build_zip(zp, [("D1/cases/c.csv", b"a,b\n1,2\n", zipfile.ZIP_DEFLATED),
                           ("__MACOSX/D1/._c.csv", b"junk", zipfile.ZIP_STORED)])
            dest = os.path.join(d, "out")
            extracted, skipped = zs.safe_extract(zp, dest)
            self.assertEqual([e["path"] for e in extracted], ["D1/cases/c.csv"])
            self.assertEqual(skipped, ["__MACOSX/D1/._c.csv"])
            self.assertTrue(os.path.exists(os.path.join(dest, "D1", "cases", "c.csv")))

    def test_rejects_traversal_member(self):
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "z.zip")
            build_zip(zp, [("../evil.txt", b"x", zipfile.ZIP_STORED)])
            with self.assertRaises(zs.UnsafeArchiveError):
                zs.safe_extract(zp, os.path.join(d, "out"))
            self.assertFalse(os.path.exists(os.path.join(d, "evil.txt")))

    def test_rejects_symlink_member(self):
        with tempfile.TemporaryDirectory() as d:
            zp = os.path.join(d, "z.zip")
            info = zipfile.ZipInfo("link")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(zp, "w") as z:
                z.writestr(info, "/etc/passwd")
            with self.assertRaises(zs.UnsafeArchiveError):
                zs.safe_extract(zp, os.path.join(d, "out"))


class RemoteFetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.zip_path = os.path.join(self.tmp.name, "a.zip")
        self.big = bytes(range(256)) * 4000
        build_zip(self.zip_path, [("keep/big.bin", self.big, zipfile.ZIP_DEFLATED),
                                  ("keep/small.txt", b"hello", zipfile.ZIP_STORED),
                                  ("skip/other.bin", os.urandom(50000), zipfile.ZIP_STORED)])

    def _zip_bytes(self):
        with open(self.zip_path, "rb") as fh:
            return fh.read()

    def _remote(self, payload):
        srv, url = serve(payload)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return zs.RemoteFile(url)

    def test_fetch_single_member_without_downloading_the_rest(self):
        remote = self._remote(self._zip_bytes())
        with zipfile.ZipFile(remote) as z:
            info = z.getinfo("keep/big.bin")
        out = os.path.join(self.tmp.name, "out", "big.bin")
        res = zs.fetch_member(remote, info, out)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(), self.big)
        self.assertEqual(res["crc32"], f"{info.CRC:08x}")
        self.assertLess(remote.bytes_fetched, remote.size)  # other.bin was never fetched

    def test_detects_corrupted_payload(self):
        payload = bytearray(self._zip_bytes())
        with zipfile.ZipFile(self.zip_path) as z:
            info = z.getinfo("keep/small.txt")
        payload[info.header_offset + 30 + len(info.filename)] ^= 0xFF  # flip first data byte
        remote = self._remote(bytes(payload))
        with self.assertRaises(zs.UnsafeArchiveError):
            zs.fetch_member(remote, info, os.path.join(self.tmp.name, "out", "small.txt"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "out", "small.txt")))


if __name__ == "__main__":
    unittest.main()
