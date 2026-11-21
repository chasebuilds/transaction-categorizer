"""Seeded synthetic transactions with known categories and planted duplicates.
Writes BENCHMARK.md and the README measured-result table from a real run."""

from __future__ import annotations

import csv
import random
import re
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

from transaction_categorizer.core import categorize, find_duplicates, load_rules, load_transactions

ROOT = Path(__file__).resolve().parent.parent
# (raw description variants, true category, amount range). Invented merchants only.
MERCHANTS = [
    (["SQ *BEAN BARN #1043", "Bean Barn 2210 OH"], "Meals", (-18.0, -4.0)),
    (["TST* KETTLE CORNER", "KETTLE CORNER 88812"], "Meals", (-30.0, -6.0)),
    (["GREENLEAF MARKET #221", "POS GREENLEAF MARKET"], "Groceries", (-160.0, -20.0)),
    (["FRESH BASKET 0091 KY"], "Groceries", (-90.0, -15.0)),
    (["FUELSTOP 4471", "QUICKPUMP #12"], "Auto", (-70.0, -25.0)),
    (["CLOUDNEST.IO*SUB", "PixelForge Pro 99812"], "Software", (-60.0, -9.0)),
    (["RIVERTON POWER ACH", "CLEARWAVE INTERNET"], "Utilities", (-140.0, -50.0)),
    (["OFFICE DEPOTZ #5512"], "Office supplies", (-150.0, -5.0)),
    (["OFFICE DEPOTZ #5512"], "Equipment", (-900.0, -250.0)),
    (["ACME PAYROLL DIR DEP"], "Income", (1500.0, 2500.0)),
    (["MOONRIVER GIFTS 7781", "ZEPHYR TOYS 112"], "", (-80.0, -10.0)),
]


def generate(n: int, dup_count: int, seed: int, path: Path) -> tuple[list[str], set[int]]:
    rng = random.Random(seed)
    start = date(2026, 1, 1)
    rows: list[tuple[date, str, float, str]] = []
    for _ in range(n):
        variants, cat, (lo, hi) = rng.choice(MERCHANTS)
        day = start + timedelta(days=rng.randrange(180))
        rows.append((day, rng.choice(variants), round(rng.uniform(lo, hi), 2), cat))
    rows.sort(key=lambda r: r[0])
    planted: set[int] = set()
    for i in rng.sample(range(n), dup_count):
        d, desc, amt, cat = rows[i]
        rows.append((d + timedelta(days=rng.randrange(2)), desc, amt, cat))
        planted.add(len(rows) + 1)  # CSV row number, header is row 1
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Date", "Description", "Amount"])
        for d, desc, amt, _ in rows:
            w.writerow([d.isoformat(), desc, f"{amt:.2f}"])
    return [r[3] for r in rows], planted


def measure(n: int = 5000, dup_count: int = 100, seed: int = 7) -> dict[str, float]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synthetic.csv"
        truth, planted = generate(n, dup_count, seed, path)
        t0 = time.perf_counter()
        txns = load_transactions(path)
        categorize(txns, load_rules(ROOT / "samples" / "rules.yml"))
        find_duplicates(txns)
        secs = time.perf_counter() - t0
    flagged = {t.row for t in txns if t.duplicate_of}
    return {
        "rows": len(txns),
        "correct": sum(t.category == truth[t.row - 2] for t in txns),
        "uncat_truth": truth.count(""),
        "uncat_found": sum(not t.category for t in txns),
        "planted": len(planted),
        "dup_hit": len(flagged & planted),
        "flagged": len(flagged),
        "secs": secs,
    }


def table(m: dict[str, float]) -> str:
    r = int(m["rows"])
    return "\n".join([
        "| Measure | Result |",
        "|---|---|",
        f"| Transactions (seeded synthetic CSV) | {r:,} |",
        f"| Categorized correctly vs known truth | **{100 * m['correct'] / r:.1f}%** "
        f"({int(m['correct']):,} of {r:,}) |",
        f"| Left uncategorized (truth: {int(m['uncat_truth']):,} have no rule) | "
        f"{int(m['uncat_found']):,} |",
        f"| Planted duplicates found | **{int(m['dup_hit'])} of {int(m['planted'])}** |",
        f"| Total flagged as possible duplicates | {int(m['flagged'])} |",
        f"| Time to load, categorize and check duplicates | {m['secs']:.2f} s |",
    ])


def main() -> None:
    t = table(measure())
    (ROOT / "BENCHMARK.md").write_text(
        "# Benchmark\n\nWritten by `python -m benchmark.run`. Do not edit by hand.\n\n"
        "## Method\n\n5,000 transactions are generated with a fixed seed from invented "
        "merchants, with bank-style descriptions (prefixes like `SQ *` and `POS`, store "
        "numbers, state codes). Each row has a known true category. 100 rows are copied "
        "again 0 to 1 days later as planted duplicates. `samples/rules.yml` is applied and "
        "every result is compared with the truth.\n\n## Result\n\n" + t + "\n\n"
        "Flags beyond the planted duplicates are same-merchant, same-amount charges that the "
        "generator happened to place within 3 days of each other, which is what a real "
        "duplicate check also has to sort through by hand. The rules were written for these "
        "merchants, so this shows the engine works, not how a new rules file does on a real "
        "export. See [LIMITATIONS.md](LIMITATIONS.md).\n",
        encoding="utf-8",
    )
    readme = ROOT / "README.md"
    txt = readme.read_text(encoding="utf-8")
    readme.write_text(
        re.sub(
            r"(<!-- benchmark:start -->\n).*?(\n<!-- benchmark:end -->)",
            lambda mm: mm.group(1) + t + mm.group(2),
            txt,
            flags=re.S,
        ),
        encoding="utf-8",
    )
    print(t)


if __name__ == "__main__":
    main()
