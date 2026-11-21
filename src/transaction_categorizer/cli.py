"""Command line: txcat run export.csv --rules rules.yml -o categorized.xlsx"""

from __future__ import annotations

import argparse

from transaction_categorizer.core import run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="txcat", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="categorize an export and write an Excel report")
    r.add_argument("export", help="CSV or .xlsx with date, description, amount columns")
    r.add_argument("--rules", required=True, help="YAML rules file")
    r.add_argument("-o", "--output", default="categorized.xlsx")
    a = ap.parse_args(argv)
    s = run(a.export, a.rules, a.output)
    print(
        f"{s['rows']} rows: {s['rows'] - s['uncategorized']} categorized, "
        f"{s['uncategorized']} uncategorized, {s['duplicates']} possible duplicates "
        f"-> {a.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
