# Limitations

- **Rules decide everything.** The benchmark rules were written for the synthetic merchants. A new real export will have uncategorized rows until rules are added for it.
- **Merchant cleanup is pattern based.** It strips common prefixes (`SQ *`, `TST*`, `POS`, `ACH`) and trailing store numbers and state codes. Unusual bank formats can leave noise in the name, which can split one merchant into two for duplicate checks.
- **Duplicates are possible, not certain.** Same merchant and same amount within 3 days is flagged. Two real coffee purchases at the same price get flagged; a duplicate with a different amount or a renamed merchant is missed.
- **Sign convention.** Amount ranges assume spending is negative. Exports that show spending as positive need rules written that way.
- **One amount column.** Exports with separate debit and credit columns need to be merged first.
- **Dates** are read in a few common formats (`2026-01-31`, `01/31/2026`, `01/31/26`, `31.01.2026`). Day-first slashes are not supported.
- **No split transactions** and no learning from past categorizations.
