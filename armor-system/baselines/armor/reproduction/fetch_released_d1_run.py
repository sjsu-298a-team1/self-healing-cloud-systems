"""Fetch ARMOR's released D1 run (checkpoint and the authors' prediction files) from the official Zenodo release.

    .venv/bin/python -I armor-system/baselines/armor/reproduction/fetch_released_d1_run.py

Fetches exactly the five files of ARMOR/res/D1/20260113_101332/ with HTTP range requests (one request per member), each checked
against the size and CRC32 in the committed outer-archive listing (`data/manifests/armor_d1/outer_archive_listing.csv`) and the
archive's own central directory. Nothing under ARMOR/data/D2* or ARMOR/res/D2/ is requested. Files land in the Git-ignored
`data/raw/armor_zenodo_21744694/`; only their hashes are written to `evidence/released_d1_run_fetch.json`.

Nothing fetched is executed or deserialized here (model.pkl is a pickle and is only loaded later by ARMOR's own code).
"""
import csv
import datetime
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ARMOR_SYSTEM = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ARMOR_SYSTEM, "data", "tools"))
import zip_safe as zs  # noqa: E402

FILE_API = "https://zenodo.org/api/records/21744694/files/ARMOR.zip/content"
ARCHIVE_SIZE = 174195955
DEST = os.path.join(ARMOR_SYSTEM, "data", "raw", "armor_zenodo_21744694")
LISTING = os.path.join(ARMOR_SYSTEM, "data", "manifests", "armor_d1", "outer_archive_listing.csv")
RUN = "ARMOR/res/D1/20260113_101332/"
MEMBERS = [RUN + "model.pkl", RUN + "scenarios/full/res.json", RUN + "scenarios/full/tmp/pre_interval.json",
           RUN + "scenarios/full/tmp/pre_types.json", RUN + "scenarios/full/tmp/rank_df.csv"]
OUT = os.path.join(HERE, "evidence", "released_d1_run_fetch.json")


def main():
    with open(LISTING, newline="") as fh:
        listed = {r["name"]: r for r in csv.DictReader(fh)}
    remote = zs.RemoteFile(FILE_API)
    if remote.size != ARCHIVE_SIZE:
        raise SystemExit(f"remote size {remote.size} != {ARCHIVE_SIZE}")
    with zipfile.ZipFile(remote) as z:
        infos = {i.filename: i for i in z.infolist()}
    records = []
    for name in MEMBERS:
        assert name.startswith("ARMOR/res/D1/") and "D2" not in name
        info, row = infos[name], listed[name]
        if (info.file_size, f"{info.CRC:08x}") != (int(row["size"]), row["crc32"]):
            raise SystemExit(f"{name}: central directory differs from the committed listing")
        out = zs.safe_member_path(DEST, name)
        if os.path.exists(out) and zs.hash_file(out)["size"] == info.file_size:
            res = {"compressed_bytes_fetched": 0, "size": info.file_size, "crc32": f"{info.CRC:08x}", "note": "already present"}
        else:
            res = zs.fetch_member(remote, info, out)
        h = zs.hash_file(out)
        records.append({"member": name, **res, "sha256": h["sha256"]})
        print(f"{name}: {h['size']} B sha256 {h['sha256'][:16]}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        json.dump({"source": FILE_API, "fetched_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "listing": os.path.relpath(LISTING, ARMOR_SYSTEM), "total_compressed_bytes_requested": remote.bytes_fetched,
                   "members": records, "not_fetched": "ARMOR/data/D2.zip and ARMOR/res/D2/ (D2 excluded by project decision)"}, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
