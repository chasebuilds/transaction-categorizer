"""Load transactions and rules, categorize, flag duplicates, write the Excel report."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from openpyxl import Workbook, load_workbook

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d.%m.%Y")
PREFIX = re.compile(r"^(pos|debit|purchase|ach|card|sq ?\*|tst ?\*|pp ?\*|paypal ?\*)\s*", re.I)
SUFFIX = re.compile(r"(\s+#?\d{3,}.*$|\s+[A-Z]{2}$|\*\w+$|\s+(ach|dir dep)$)", re.I)


@dataclass
class Txn:
    date: date
    description: str
    amount: float
    merchant: str = ""
    category: str = ""
    rule: str = ""
    duplicate_of: int | None = None
    row: int = 0


@dataclass
class Rule:
    name: str
    category: str
    contains: list[str] = field(default_factory=list)
    regex: str | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    priority: int = 0

    def matches(self, t: Txn) -> bool:
        text = f"{t.merchant} {t.description}".lower()
        checks: list[bool] = []
        if self.contains:
            checks.append(any(c.lower() in text for c in self.contains))
        if self.regex is not None:
            checks.append(bool(re.search(self.regex, text, re.I)))
        if self.min_amount is not None:
            checks.append(t.amount >= self.min_amount)
        if self.max_amount is not None:
            checks.append(t.amount <= self.max_amount)
        return bool(checks) and all(checks)


def normalize_merchant(desc: str) -> str:
    s = " ".join(desc.split())
    prev = None
    while prev != s:
        prev = s
        s = SUFFIX.sub("", PREFIX.sub("", s).strip()).strip()
    return s.title()


def parse_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(str(v).strip(), f).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognized date: {v!r}")


def parse_amount(v: Any) -> float:
    if isinstance(v, int | float):
        return float(v)
    s = str(v).strip().replace(",", "").replace("$", "")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(s)


def _pick(header: list[str], *names: str) -> int:
    low = [h.strip().lower() for h in header]
    for n in names:
        if n in low:
            return low.index(n)
    raise ValueError(f"missing column, expected one of {names}; got {header}")


def load_transactions(path: str | Path) -> list[Txn]:
    p = Path(path)
    rows: list[list[Any]]
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        ws = load_workbook(p, read_only=True, data_only=True).active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    else:
        with p.open(newline="", encoding="utf-8-sig") as fh:
            rows = [list(r) for r in csv.reader(fh)]
    header = [str(h or "") for h in rows[0]]
    di = _pick(header, "date", "posted date", "transaction date")
    ti = _pick(header, "description", "merchant", "name", "payee")
    ai = _pick(header, "amount")
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if not r or all(c in (None, "") for c in r):
            continue
        desc = str(r[ti] or "")
        out.append(
            Txn(parse_date(r[di]), desc, parse_amount(r[ai]), normalize_merchant(desc), row=i)
        )
    return out


def load_rules(path: str | Path) -> list[Rule]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rules = []
    for i, r in enumerate(data.get("rules", [])):
        c = r.get("contains", [])
        rules.append(
            Rule(
                name=str(r.get("name", f"rule{i + 1}")),
                category=str(r["category"]),
                contains=[c] if isinstance(c, str) else [str(x) for x in c],
                regex=r.get("regex"),
                min_amount=r.get("min_amount"),
                max_amount=r.get("max_amount"),
                priority=int(r.get("priority", 0)),
            )
        )
    # Higher priority first; sorted() is stable so file order breaks ties.
    return sorted(rules, key=lambda r: -r.priority)


def categorize(txns: list[Txn], rules: list[Rule]) -> None:
    for t in txns:
        hit = next((r for r in rules if r.matches(t)), None)
        t.category, t.rule = (hit.category, hit.name) if hit else ("", "")


def find_duplicates(txns: list[Txn], window_days: int = 3) -> int:
    """Flag a charge as a possible duplicate of an earlier one with the same merchant
    and amount within window_days. Returns how many were flagged."""
    seen: dict[tuple[str, float], list[Txn]] = defaultdict(list)
    n = 0
    for t in sorted(txns, key=lambda x: (x.date, x.row)):
        key = (t.merchant.lower(), round(t.amount, 2))
        prior = [p for p in seen[key] if (t.date - p.date).days <= window_days]
        if prior:
            t.duplicate_of = prior[-1].row
            n += 1
        seen[key].append(t)
    return n


def write_report(txns: list[Txn], out: str | Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    cols = ["Row", "Date", "Description", "Merchant", "Amount", "Category", "Matched rule",
            "Possible duplicate of row"]
    ws.append(cols)
    for t in txns:
        ws.append([t.row, t.date, t.description, t.merchant, t.amount,
                   t.category or "Uncategorized", t.rule, t.duplicate_of])
    un = wb.create_sheet("Uncategorized")
    un.append(cols[:5])
    for t in txns:
        if not t.category:
            un.append([t.row, t.date, t.description, t.merchant, t.amount])
    sm = wb.create_sheet("Monthly summary")
    months = sorted({t.date.strftime("%Y-%m") for t in txns})
    pivot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for t in txns:
        pivot[t.category or "Uncategorized"][t.date.strftime("%Y-%m")] += t.amount
    sm.append(["Category", *months, "Total"])
    for cat in sorted(pivot):
        vals = [round(pivot[cat][m], 2) for m in months]
        sm.append([cat, *vals, round(sum(vals), 2)])
    for sheet in (ws, un, sm):
        sheet.freeze_panes = "A2"
    wb.save(out)


def run(src: str | Path, rules_path: str | Path, out: str | Path) -> dict[str, int]:
    txns = load_transactions(src)
    categorize(txns, load_rules(rules_path))
    dups = find_duplicates(txns)
    write_report(txns, out)
    return {"rows": len(txns), "uncategorized": sum(not t.category for t in txns),
            "duplicates": dups}
