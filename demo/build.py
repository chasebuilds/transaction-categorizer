"""Build the static demo site into _site/: page files, the package as pkg.zip, and the samples."""

from __future__ import annotations

import importlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
PKG = "transaction_categorizer"
SAMPLES = [
    "samples/export.csv",
    "samples/rules.yml",
]  # paths relative to the repo root, published under samples/
# Installed packages whose pure-Python modules go into the bundle (no wheel exists for Pyodide).
VENDOR: list[str] = []


def build(out: Path = ROOT / "_site") -> Path:
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for name in ("index.html", "app.js", "config.js"):
        shutil.copy2(DEMO / name, out / name)
    (out / ".nojekyll").write_text("")
    with zipfile.ZipFile(out / "pkg.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((ROOT / "src" / PKG).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(ROOT / "src").as_posix())
        for name in VENDOR:
            base = Path(importlib.import_module(name).__file__ or "").parent
            for f in sorted(base.rglob("*.py")):
                if "__pyinstaller" not in f.parts:
                    z.write(f, (Path(name) / f.relative_to(base)).as_posix())
    (out / "samples").mkdir()
    for rel in SAMPLES:
        shutil.copy2(ROOT / rel, out / "samples" / Path(rel).name)
    if (DEMO / "meta.json").exists():  # title, description and share preview for the page
        sys.path.insert(0, str(DEMO))
        page_meta = importlib.import_module("page_meta")
        meta = json.loads((DEMO / "meta.json").read_text(encoding="utf-8"))
        page_meta.apply(out, meta, ROOT)
    return out


if __name__ == "__main__":
    print(f"built {build(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / '_site')}")
