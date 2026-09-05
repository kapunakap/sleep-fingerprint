from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import requests
from scipy.io import loadmat, whosmat

URL = "https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0306074.s001"
OUT = Path(".research-cache/pone.0306074.s001.mat")


def describe(value: Any, name: str, depth: int = 0) -> None:
    prefix = "  " * depth
    if depth > 4:
        print(f"{prefix}{name}: <max-depth>")
        return
    if isinstance(value, dict):
        print(f"{prefix}{name}: dict keys={sorted(map(str, value.keys()))}")
        for key, item in value.items():
            if str(key).startswith("__"):
                continue
            describe(item, str(key), depth + 1)
        return
    if isinstance(value, np.ndarray):
        extra = ""
        if value.size and np.issubdtype(value.dtype, np.number):
            flat = np.asarray(value).ravel()
            finite = flat[np.isfinite(flat)]
            if finite.size:
                extra = f" min={float(np.min(finite)):.6g} max={float(np.max(finite)):.6g}"
        print(f"{prefix}{name}: ndarray shape={value.shape} dtype={value.dtype}{extra}")
        if value.dtype == object and value.size <= 20:
            for i, item in enumerate(value.ravel()):
                describe(item, f"[{i}]", depth + 1)
        return
    if hasattr(value, "_fieldnames"):
        fields = list(getattr(value, "_fieldnames", []) or [])
        print(f"{prefix}{name}: mat_struct fields={fields}")
        for field in fields:
            describe(getattr(value, field), field, depth + 1)
        return
    text = repr(value)
    if len(text) > 300:
        text = text[:297] + "..."
    print(f"{prefix}{name}: {type(value).__name__} {text}")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(URL, stream=True, timeout=(30, 120), headers={"User-Agent": "sleep-fingerprint-research/0.1"}) as response:
        response.raise_for_status()
        with OUT.open("wb") as handle:
            for chunk in response.iter_content(8 * 1024 * 1024):
                if chunk:
                    handle.write(chunk)
    raw = OUT.read_bytes()
    print("url", URL)
    print("final_url", response.url)
    print("bytes", len(raw))
    print("md5", hashlib.md5(raw, usedforsecurity=False).hexdigest())
    print("sha256", hashlib.sha256(raw).hexdigest())
    print("header", raw[:128])
    print("whosmat", whosmat(OUT))
    try:
        payload = loadmat(OUT, squeeze_me=True, struct_as_record=False)
    except NotImplementedError as error:
        print("loadmat_not_implemented", error)
        import h5py

        with h5py.File(OUT, "r") as handle:
            def walk(name: str, obj: Any) -> None:
                if hasattr(obj, "shape"):
                    print("h5", name, "shape", obj.shape, "dtype", obj.dtype)
                else:
                    print("h5", name, type(obj).__name__)
            handle.visititems(walk)
        return
    describe(payload, "root")


if __name__ == "__main__":
    main()
