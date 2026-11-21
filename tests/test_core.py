from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from benchmark.run import measure
from transaction_categorizer.cli import main
from transaction_categorizer.core import (
    Rule,
    Txn,
    categorize,
    find_duplicates,
    load_rules,
    load_transactions,
    normalize_merchant,
    parse_amount,
)

RULES = Path(__file__).resolve().parent.parent / "samples" / "rules.yml"


def t(desc: str, amt: float, d: date = date(2026, 1, 5), row: int = 2) -> Txn:
    return Txn(d, desc, amt, normalize_merchant(desc), row=row)


def test_normalize_merchant() -> None:
    assert normalize_merchant("SQ *BEAN BARN #1043") == "Bean Barn"
    assert normalize_merchant("POS GREENLEAF MARKET") == "Greenleaf Market"
    assert normalize_merchant("FRESH BASKET 0091 KY") == "Fresh Basket"


def test_parse_amount() -> None:
    assert parse_amount("(1,234.50)") == -1234.5
    assert parse_amount("$12") == 12.0


def test_priority_and_amount_range() -> None:
    rules = load_rules(RULES)
    small, big, pay = t("OFFICE DEPOTZ #5512", -40), t("OFFICE DEPOTZ #5512", -400), t(
        "ACME PAYROLL DIR DEP", 2000
    )
    other = t("MOONRIVER GIFTS 7781", -20)
    categorize([small, big, pay, other], rules)
    cats = (small.category, big.category, pay.category)
    assert cats == ("Office supplies", "Equipment", "Income")
    assert big.rule == "big-supplies"
    assert other.category == ""


def test_regex_rule_and_empty_rule() -> None:
    assert Rule("r", "Auto", regex="fuel").matches(t("FUELSTOP 1", -30))
    assert not Rule("empty", "X").matches(t("anything", -1))


def test_duplicates() -> None:
    a = t("BEAN BARN", -5, date(2026, 1, 1), 2)
    b = t("BEAN BARN", -5, date(2026, 1, 3), 3)
    c = t("BEAN BARN", -5, date(2026, 1, 20), 4)
    assert find_duplicates([a, b, c]) == 1
    assert b.duplicate_of == 2 and c.duplicate_of is None


def test_cli_end_to_end(tmp_path: Path, capsys: object) -> None:
    src = tmp_path / "export.csv"
    src.write_text(
        "Posted Date,Description,Amount\n"
        "01/05/2026,SQ *BEAN BARN #1043,-4.50\n"
        "01/06/2026,SQ *BEAN BARN #1043,-4.50\n"
        "02/01/2026,ZEPHYR TOYS 112,-20.00\n"
        "02/02/2026,ACME PAYROLL DIR DEP,\"2,000.00\"\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.xlsx"
    assert main(["run", str(src), "--rules", str(RULES), "-o", str(out)]) == 0
    wb = load_workbook(out)
    assert wb.sheetnames == ["Transactions", "Uncategorized", "Monthly summary"]
    assert wb["Uncategorized"].max_row == 2
    assert wb["Transactions"]["H3"].value == 2
    summary = {r[0]: r[-1] for r in wb["Monthly summary"].iter_rows(min_row=2, values_only=True)}
    assert summary == {"Income": 2000.0, "Meals": -9.0, "Uncategorized": -20.0}
    assert len(load_transactions(src)) == 4


def test_benchmark_small() -> None:
    m = measure(n=500, dup_count=10, seed=1)
    assert m["correct"] == m["rows"]
    assert m["dup_hit"] == m["planted"]
