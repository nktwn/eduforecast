import argparse
import hashlib
import io
import re
import time
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

from src.finance.config import CPI_PATH, CPI_URL, IPEDS_DATA_URL, MANIFEST_PATH, RAW_DIR, YEARS, files_for_year

MAX_RETRIES = 4


def _fetch(name: str) -> bytes | None:
    url = IPEDS_DATA_URL.format(name=name)
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=180)
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(2 ** attempt)
            continue
        if resp.status_code == 404:
            return None
        if resp.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        return resp.content
    raise RuntimeError(f"failed to download {url}")


def _pick_csv(archive: zipfile.ZipFile) -> str:
    csvs = [n for n in archive.namelist() if n.lower().endswith(".csv")]
    revised = [n for n in csvs if n.lower().endswith("_rv.csv")]
    return (revised or csvs)[0]


def download(name: str) -> dict:
    target = RAW_DIR / f"{name}.csv"
    if target.exists():
        return {"name": name, "status": "cached", "file": target.name}
    content = _fetch(name)
    if content is None:
        return {"name": name, "status": "missing"}
    archive = zipfile.ZipFile(io.BytesIO(content))
    member = _pick_csv(archive)
    data = archive.read(member)
    target.write_bytes(data)
    return {
        "name": name, "status": "downloaded", "file": target.name, "member": member,
        "revised": member.lower().endswith("_rv.csv"), "bytes": len(data),
        "sha1": hashlib.sha1(data).hexdigest(),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def download_cpi() -> dict:
    if CPI_PATH.exists():
        return {"name": CPI_PATH.stem, "status": "cached"}
    resp = requests.get(CPI_URL, timeout=60)
    resp.raise_for_status()
    CPI_PATH.write_bytes(resp.content)
    return {"name": CPI_PATH.stem, "status": "downloaded", "file": CPI_PATH.name, "bytes": len(resp.content),
            "sha1": hashlib.sha1(resp.content).hexdigest(),
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def load(name: str, usecols=None) -> pd.DataFrame | None:
    path = RAW_DIR / f"{name}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = [re.sub(r"^[^A-Za-z0-9_]+", "", c.replace("ï»¿", "")).strip().upper() for c in df.columns]
    if usecols is not None:
        df = df[[c for c in usecols if c in df.columns]]
    return df


def main():
    parser = argparse.ArgumentParser(description="Download IPEDS complete data files")
    parser.add_argument("--years", nargs="*", type=int, default=YEARS)
    args = parser.parse_args()
    previous = pd.read_csv(MANIFEST_PATH) if MANIFEST_PATH.exists() else pd.DataFrame()
    rows = []
    for year in args.years:
        for component, name in files_for_year(year).items():
            row = {"year": year, "component": component, **download(name)}
            print(row["name"], row["status"], flush=True)
            rows.append(row)
    rows.append({"year": None, "component": "cpi", **download_cpi()})
    fresh = pd.DataFrame(rows)
    fresh = fresh[fresh["status"] != "cached"]
    manifest = pd.concat([previous, fresh], ignore_index=True).drop_duplicates("name", keep="last")
    manifest.sort_values(["year", "component"]).to_csv(MANIFEST_PATH, index=False)


if __name__ == "__main__":
    main()
