"""Acquire ARMOR D1 from the official Zenodo release (record 21744694).

Only D1 is fetched. The outer ARMOR.zip also embeds D2, which is deliberately
NOT downloaded (licensing conflict), so the whole-archive md5 published by
Zenodo cannot be recomputed here. Integrity is instead established with the
CRC32 and sizes recorded in the official archive's central directory, plus a
local CRC test of the nested D1 archive.

Nothing downloaded is executed or deserialized.

Usage:  python3 -I fetch_d1.py [--dest DIR] [--manifest-dir DIR]
"""
import argparse
import csv
import datetime
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zip_safe as zs  # noqa: E402
import zipfile  # noqa: E402

RECORD_ID = "21744694"
RECORD_API = f"https://zenodo.org/api/records/{RECORD_ID}"
FILE_API = f"https://zenodo.org/api/records/{RECORD_ID}/files/ARMOR.zip/content"
EXPECTED = {
    "record_id": RECORD_ID,
    "doi": "10.5281/zenodo.21744694",
    "concept_doi": "10.5281/zenodo.19157588",
    "publication_date": "2026-08-01",
    "license": "cc-by-4.0",
    "file_name": "ARMOR.zip",
    "file_size": 174195955,
    "file_md5": "b0f1068c2a32d76f30630c6217cbaab0",
}
D1_MEMBER = "ARMOR/data/D1.zip"
# Members that must never be fetched: D2 data, and result/checkpoint folders.
EXCLUDED_PREFIXES = ("__MACOSX/", "ARMOR/data/D2", "ARMOR/res/")
SMALL_MEMBER_LIMIT = 200_000


def select_members(infos):
    """Choose members to fetch: D1 archive plus small code/config/README files."""
    chosen = []
    for info in infos:
        n = info.filename
        if info.is_dir() or n.endswith(".DS_Store"):
            continue
        if any(n.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if n == D1_MEMBER or info.file_size <= SMALL_MEMBER_LIMIT:
            chosen.append(info)
    return chosen


def verify_record_metadata(meta):
    f = meta["files"][0]
    got = {
        "record_id": str(meta["id"]),
        "doi": meta["doi"],
        "concept_doi": meta["conceptdoi"],
        "publication_date": meta["metadata"]["publication_date"],
        "license": meta["metadata"]["license"]["id"],
        "file_name": f["key"],
        "file_size": f["size"],
        "file_md5": f["checksum"].split(":", 1)[1],
    }
    mismatches = {k: (EXPECTED[k], got[k]) for k in EXPECTED if EXPECTED[k] != got[k]}
    if len(meta["files"]) != 1 or mismatches:
        raise SystemExit(f"Zenodo metadata mismatch: files={len(meta['files'])} {mismatches}")
    return got


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_data = os.path.abspath(os.path.join(here, ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=os.path.join(repo_data, "raw", f"armor_zenodo_{RECORD_ID}"))
    ap.add_argument("--manifest-dir", default=os.path.join(repo_data, "manifests", "armor_d1"))
    args = ap.parse_args()
    os.makedirs(args.dest, exist_ok=True)
    os.makedirs(args.manifest_dir, exist_ok=True)

    with urllib.request.urlopen(RECORD_API) as r:
        meta = json.load(r)
    verified = verify_record_metadata(meta)
    print("record metadata verified:", verified["record_id"], verified["file_md5"])

    remote = zs.RemoteFile(FILE_API)
    if remote.size != EXPECTED["file_size"]:
        raise SystemExit(f"remote size {remote.size} != expected {EXPECTED['file_size']}")
    with zipfile.ZipFile(remote) as z:
        infos = z.infolist()
    for i in infos:
        zs.safe_member_path(args.dest, i.filename)  # reject unsafe names up front

    listing = os.path.join(args.manifest_dir, "outer_archive_listing.csv")
    with open(listing, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "size", "compressed_size", "crc32", "compress_type", "fetched"])
        chosen = {i.filename for i in select_members(infos)}
        for i in infos:
            w.writerow([i.filename, i.file_size, i.compress_size, f"{i.CRC:08x}", i.compress_type,
                        "yes" if i.filename in chosen else "no"])

    fetched = []
    for info in select_members(infos):
        out = zs.safe_member_path(args.dest, info.filename)
        if os.path.exists(out) and os.path.getsize(out) == info.file_size:
            res = {"size": info.file_size, "crc32": f"{info.CRC:08x}", "compressed_bytes_fetched": 0,
                   "note": "already present, not re-downloaded"}
        else:
            res = zs.fetch_member(remote, info, out)
        rec = {"member": info.filename, "local_path": os.path.relpath(out, args.dest), **res,
               **{k: v for k, v in zs.hash_file(out).items() if k != "size"}}
        fetched.append(rec)
        print(f"fetched {info.filename} ({res['size']} B)")

    d1_zip = zs.safe_member_path(args.dest, D1_MEMBER)
    extract_root = os.path.join(args.dest, "extracted")
    extracted, skipped = zs.safe_extract(d1_zip, extract_root)
    print(f"extracted {len(extracted)} D1 files; skipped {len(skipped)}")

    checksums = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "official_archive": {**verified,
                             "whole_archive_md5_recomputed": False,
                             "reason_not_recomputed": "requires downloading D2 bytes, which are excluded by project decision"},
        "bytes_fetched_from_archive": remote.bytes_fetched,
        "bytes_not_fetched": remote.size - remote.bytes_fetched,
        "fetched_members": fetched,
        "nested_d1_extraction": {"count": len(extracted), "skipped": skipped,
                                  "crc_test": "zipfile.testzip() passed", "files": extracted},
    }
    with open(os.path.join(args.manifest_dir, "checksums.json"), "w") as fh:
        json.dump(checksums, fh, indent=2)
    prov = {"zenodo_record_url": f"https://zenodo.org/records/{RECORD_ID}", "api_url": RECORD_API,
            "download_url": FILE_API, "expected": EXPECTED, "verified_against_live_metadata": True,
            "d1_member": D1_MEMBER, "excluded_prefixes": list(EXCLUDED_PREFIXES),
            "data_lineage_claim": "ARMOR README: datasets derived from https://github.com/bbyldebb/ART",
            "local_dataset_dir_gitignored": os.path.relpath(args.dest, repo_data)}
    with open(os.path.join(args.manifest_dir, "provenance.json"), "w") as fh:
        json.dump(prov, fh, indent=2)
    print(f"done. fetched {remote.bytes_fetched} of {remote.size} archive bytes")


if __name__ == "__main__":
    main()
