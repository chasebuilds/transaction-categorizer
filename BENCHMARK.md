# Benchmark

Written by `python -m benchmark.run`. Do not edit by hand.

## Method

5,000 transactions are generated with a fixed seed from invented merchants, with bank-style descriptions (prefixes like `SQ *` and `POS`, store numbers, state codes). Each row has a known true category. 100 rows are copied again 0 to 1 days later as planted duplicates. `samples/rules.yml` is applied and every result is compared with the truth.

## Result

| Measure | Result |
|---|---|
| Transactions (seeded synthetic CSV) | 5,100 |
| Categorized correctly vs known truth | **100.0%** (5,100 of 5,100) |
| Left uncategorized (truth: 467 have no rule) | 467 |
| Planted duplicates found | **100 of 100** |
| Total flagged as possible duplicates | 105 |
| Time to load, categorize and check duplicates | 0.10 s |

Flags beyond the planted duplicates are same-merchant, same-amount charges that the generator happened to place within 3 days of each other, which is what a real duplicate check also has to sort through by hand. The rules were written for these merchants, so this shows the engine works, not how a new rules file does on a real export. See [LIMITATIONS.md](LIMITATIONS.md).
