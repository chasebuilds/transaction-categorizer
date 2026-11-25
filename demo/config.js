window.DEMO = {
  repo: "transaction-categorizer",
  title: "transaction-categorizer",
  tagline: "Drop in a bank or card export. Every transaction gets a category from a plain YAML rules file, with the rule that matched, a list of what is left uncategorized and possible duplicate charges.",
  pkg: "transaction_categorizer",
  packages: ["openpyxl", "pyyaml"],
  inputs: [
    { id: "export", label: "Export (CSV or XLSX: date, description, amount)", accept: ".csv,.xlsx", sample: "samples/export.csv" },
    { id: "rules", label: "Rules file (YAML)", accept: ".yml,.yaml", optional: true, sample: "samples/rules.yml" },
  ],
  options: [],
  sampleNote: 'The sample is <a href="samples/export.csv">export.csv</a>: 64 synthetic transactions from invented merchants with 4 planted duplicate charges, and the rules in <a href="samples/rules.yml">rules.yml</a>. Leave the rules box empty to use those rules on your own export.',
  python: `
from pathlib import Path
from transaction_categorizer.cli import main as cli_main

def run(paths, opts):
    src = paths["export"][0]
    out = "/work/" + Path(src).stem + "-categorized.xlsx"
    code, log = run_cli(cli_main, ["run", src, "--rules", paths["rules"][0], "-o", out])
    if code != 0 or not Path(out).exists():
        return {"ok": False, "log": log, "sheets": [], "download": None}
    return {"ok": True, "log": log, "sheets": sheets_from_xlsx(out), "download": out}
`,
};
