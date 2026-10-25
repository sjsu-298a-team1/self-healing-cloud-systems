"""Stdlib-only helpers for inspecting and fetching members of a remote zip safely.

Nothing here executes or deserializes downloaded content. A remote archive is
read through HTTP range requests so that a single member can be fetched without
downloading the rest of the archive.
"""
import hashlib
import io
import os
import posixpath
import stat
import struct
import urllib.request
import zipfile
import zlib

CHUNK = 1 << 20
DEFAULT_MAX_TOTAL_BYTES = 4 << 30
DEFAULT_MAX_RATIO = 1000.0


class UnsafeArchiveError(Exception):
    pass


class RemoteFile(io.RawIOBase):
    """Read-only seekable file over HTTP range requests (counts bytes fetched)."""

    def __init__(self, url):
        self.url = url
        self.pos = 0
        self.bytes_fetched = 0
        req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
        with urllib.request.urlopen(req) as resp:
            self.size = int(resp.headers["Content-Range"].split("/")[1])
            self.bytes_fetched += 1

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        else:
            self.pos = self.size + offset
        return self.pos

    def read(self, n=-1):
        if n < 0 or self.pos + n > self.size:
            n = self.size - self.pos
        if n <= 0:
            return b""
        req = urllib.request.Request(
            self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}
        )
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        self.pos += len(data)
        self.bytes_fetched += len(data)
        return data

    def readinto(self, buf):
        data = self.read(len(buf))
        buf[: len(data)] = data
        return len(data)


def safe_member_path(dest_root, name):
    """Return the absolute destination for an archive member, or raise.

    Rejects absolute paths, drive letters, backslash tricks and any path that
    resolves outside dest_root.
    """
    if not name or name.startswith("/") or "\\" in name or (len(name) > 1 and name[1] == ":"):
        raise UnsafeArchiveError(f"unsafe member name: {name!r}")
    norm = posixpath.normpath(name)
    if norm == ".." or norm.startswith("../") or norm.startswith("/"):
        raise UnsafeArchiveError(f"path traversal in member: {name!r}")
    root = os.path.realpath(dest_root)
    target = os.path.realpath(os.path.join(root, *norm.split("/")))
    if target != root and not target.startswith(root + os.sep):
        raise UnsafeArchiveError(f"member escapes destination: {name!r}")
    return target


def is_symlink(info):
    return stat.S_ISLNK(info.external_attr >> 16)


def check_archive_limits(infos, max_total=DEFAULT_MAX_TOTAL_BYTES, max_ratio=DEFAULT_MAX_RATIO):
    total = sum(i.file_size for i in infos)
    if total > max_total:
        raise UnsafeArchiveError(f"uncompressed total {total} exceeds limit {max_total}")
    for i in infos:
        if i.compress_size and i.file_size / i.compress_size > max_ratio:
            raise UnsafeArchiveError(f"suspicious compression ratio for {i.filename}")
    return total


def hash_file(path):
    md5, sha = hashlib.md5(), hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            md5.update(block)
            sha.update(block)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest(), "size": os.path.getsize(path)}


def fetch_member(remote, info, out_path):
    """Fetch one member of a remote zip with a single range request.

    Decompresses a deflate stream on the fly, verifies the size and CRC32
    recorded in the archive's central directory, and writes out_path atomically.
    """
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise UnsafeArchiveError(f"unsupported compression {info.compress_type} for {info.filename}")
    remote.seek(info.header_offset)
    header = remote.read(30)
    if header[:4] != b"PK\x03\x04":
        raise UnsafeArchiveError(f"bad local header for {info.filename}")
    name_len, extra_len = struct.unpack("<HH", header[26:30])
    data_start = info.header_offset + 30 + name_len + extra_len
    last = data_start + info.compress_size - 1
    req = urllib.request.Request(remote.url, headers={"Range": f"bytes={data_start}-{last}"})
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".part"
    crc, written, got = 0, 0, 0
    decomp = zlib.decompressobj(-15) if info.compress_type == zipfile.ZIP_DEFLATED else None
    with urllib.request.urlopen(req) as resp, open(tmp, "wb") as out:
        for block in iter(lambda: resp.read(CHUNK), b""):
            got += len(block)
            data = decomp.decompress(block) if decomp else block
            crc = zlib.crc32(data, crc)
            written += len(data)
            out.write(data)
        if decomp:
            data = decomp.flush()
            crc = zlib.crc32(data, crc)
            written += len(data)
            out.write(data)
    remote.bytes_fetched += got
    if got != info.compress_size or written != info.file_size or (crc & 0xFFFFFFFF) != info.CRC:
        os.remove(tmp)
        raise UnsafeArchiveError(
            f"integrity failure for {info.filename}: got={got}/{info.compress_size} "
            f"size={written}/{info.file_size} crc={crc & 0xFFFFFFFF:08x}/{info.CRC:08x}"
        )
    os.replace(tmp, out_path)
    return {"compressed_bytes_fetched": got, "size": written, "crc32": f"{info.CRC:08x}"}


def safe_extract(zip_path, dest_root, skip_prefixes=("__MACOSX/",), max_total=DEFAULT_MAX_TOTAL_BYTES):
    """Extract a local zip with path-safety, symlink and size checks.

    Returns (extracted_records, skipped_names). Verifies CRC32 via zipfile.
    """
    extracted, skipped = [], []
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad is not None:
            raise UnsafeArchiveError(f"CRC failure in nested archive member: {bad}")
        infos = z.infolist()
        check_archive_limits(infos, max_total=max_total)
        for info in infos:
            if any(info.filename.startswith(p) for p in skip_prefixes):
                skipped.append(info.filename)
                continue
            if is_symlink(info):
                raise UnsafeArchiveError(f"symlink member rejected: {info.filename}")
            target = safe_member_path(dest_root, info.filename)
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                for block in iter(lambda: src.read(CHUNK), b""):
                    dst.write(block)
            if os.path.getsize(target) != info.file_size:
                raise UnsafeArchiveError(f"size mismatch after extraction: {info.filename}")
            extracted.append({"path": info.filename, "size": info.file_size, "crc32": f"{info.CRC:08x}"})
    return extracted, skipped
