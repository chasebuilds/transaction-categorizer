# transaction-categorizer

[![ci](https://github.com/chasebuilds/transaction-categorizer/actions/workflows/ci.yml/badge.svg)](https://github.com/chasebuilds/transaction-categorizer/actions/workflows/ci.yml) ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue) [![MIT license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Categorizes bank and card transaction exports (CSV or Excel) for bookkeeping using a rules file you can edit in any text editor. It cleans up merchant names (`SQ *BEAN BARN #1043` becomes `Bean Barn`), flags rows no rule matched, flags possible duplicate charges, and writes an Excel report with three sheets: every transaction with its category and the rule that matched, the uncategorized rows, and a monthly summary by category. Everything runs offline.

## Measured result

5,000 seeded synthetic transactions with known categories and 100 planted duplicates were run through the sample rules and every result was checked against the truth. The table is written by the benchmark script from a real run, not typed by hand. Method and limits: [BENCHMARK.md](BENCHMARK.md).

<!-- benchmark:start -->
<!-- benchmark:end -->

The rules were written for the synthetic merchants, so this is a best case. [LIMITATIONS.md](LIMITATIONS.md) lists what a real export can do to it.

## Quick start

Windows (on macOS or Linux use `.venv/bin/` in place of `.venv\Scripts\`):

```
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\txcat run export.csv --rules samples\rules.yml -o categorized.xlsx
```

The export needs a date column (`Date`, `Posted Date` or `Transaction Date`), a description column (`Description`, `Merchant`, `Name` or `Payee`) and an `Amount` column. Amounts like `(1,234.50)` and `$12` are read as numbers.

## Rules file

```yaml
rules:
  - name: payroll
    category: Income
    contains: [payroll]      # any of these, case-insensitive
    min_amount: 0
    priority: 10             # higher runs first; file order breaks ties
  - name: fuel
    category: Auto
    regex: "fuelstop|quickpump"
  - name: big-supplies
    category: Equipment
    contains: [office depotz]
    max_amount: -200
    priority: 5
```

A rule matches when every condition it lists is true. The first matching rule wins. Rows no rule matches go to the Uncategorized sheet, so you can add a rule and run again.

## Duplicates

A charge is flagged as a possible duplicate when an earlier charge has the same cleaned merchant name and the same amount within 3 days. The Transactions sheet shows which row it may duplicate. Nothing is removed.

## Development

```
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m mypy
.venv\Scripts\python -m pytest --cov
.venv\Scripts\python -m benchmark.run
```

## License

MIT, Chase Builds.
