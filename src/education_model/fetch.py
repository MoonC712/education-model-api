from __future__ import annotations

import argparse
import hashlib
import shutil
import time
import zipfile
from pathlib import Path

import requests

FILES = {
    "student": {
        "url": "https://webfs.oecd.org/pisa2022/STU_QQQ_SPSS.zip",
        "expected_sav": "CY08MSP_STU_QQQ.sav",
        "expected_md5": "0093d5302fd5b736e62e1c3de06f3b42"
    },
    "school": {
        "url": "https://webfs.oecd.org/pisa2022/SCH_QQQ_SPSS.zip",
        "expected_sav": "CY08MSP_SCH_QQQ.sav",
        "expected_md5": "bdbff44ba7331b3b3e13d1dcb35ee2df"
    }
}


def md5(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def download_with_resume(url: str, destination: Path, retries: int = 4) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, retries + 1):
        existing = partial.stat().st_size if partial.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        try:
            with requests.get(url, stream=True, timeout=(30, 180), headers=headers) as response:
                if existing and response.status_code == 200:
                    partial.unlink(missing_ok=True)
                    existing = 0
                response.raise_for_status()
                mode = "ab" if existing and response.status_code == 206 else "wb"
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            partial.replace(destination)
            return
        except (requests.RequestException, OSError) as exc:
            if attempt == retries:
                raise RuntimeError(f"Failed to download {url}: {exc}") from exc
            time.sleep(2 ** attempt)


def extract_and_find(zip_path: Path, output_dir: Path, expected_name: str) -> Path:
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"Downloaded file is not a valid ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(output_dir)
    exact = list(output_dir.rglob(expected_name))
    if exact:
        return exact[0]
    candidates = list(output_dir.rglob("*.sav"))
    if len(candidates) == 1:
        target = output_dir / expected_name
        if candidates[0] != target:
            shutil.move(str(candidates[0]), target)
        return target
    raise FileNotFoundError(f"Could not uniquely locate {expected_name} after extraction")


def fetch_all(output_dir: Path, keep_zip: bool = False) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    for kind, spec in FILES.items():
        sav_path = output_dir / spec["expected_sav"]
        if sav_path.exists():
            results[kind] = sav_path
            continue
        zip_path = output_dir / f"pisa2022_{kind}.zip"
        print(f"Downloading official PISA 2022 {kind} file…")
        download_with_resume(spec["url"], zip_path)
        found = extract_and_find(zip_path, output_dir, spec["expected_sav"])
        actual_hash = md5(found)
        if actual_hash != spec["expected_md5"]:
            raise ValueError(
                f"Checksum mismatch for {found.name}. Expected {spec['expected_md5']}, got {actual_hash}."
            )
        if not keep_zip:
            zip_path.unlink(missing_ok=True)
        results[kind] = found
        print(f"Verified {found.name} ({actual_hash})")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and verify official PISA 2022 SPSS files.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--keep-zip", action="store_true")
    args = parser.parse_args()
    paths = fetch_all(args.output_dir, args.keep_zip)
    for kind, path in paths.items():
        print(f"{kind}: {path.resolve()}")


if __name__ == "__main__":
    main()
