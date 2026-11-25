// Generic in-browser runner: loads Pyodide, unpacks this repo's own package, runs the real CLI.
const PYODIDE_VERSION = "0.27.7";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
const D = window.DEMO;
const $ = (s) => document.querySelector(s);

const HELPERS = `
import io, os, sys, json, contextlib, zipfile, csv, datetime
from openpyxl import load_workbook

def _fill(c):
    f = c.fill
    if f is None or f.fill_type != "solid":
        return None
    rgb = f.fgColor.rgb if f.fgColor is not None and f.fgColor.type == "rgb" else None
    if not isinstance(rgb, str) or rgb in ("00000000", "FFFFFFFF"):
        return None
    return "#" + rgb[-6:]

def _text(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime) and v.time() == datetime.time(0):
        return v.date().isoformat()
    return str(v)

def sheets_from_xlsx(path, limit=200):
    wb = load_workbook(path)
    out = []
    for ws in wb.worksheets:
        rows, fills, total = [], [], 0
        for row in ws.iter_rows():
            total += 1
            if len(rows) <= limit:
                rows.append([_text(c.value) for c in row])
                fills.append([_fill(c) for c in row])
        out.append({"name": ws.title, "rows": rows, "fills": fills, "total": max(total - 1, 0)})
    return out

def sheet_from_csv(path, name, limit=200):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        all_rows = list(csv.reader(fh))
    return {"name": name, "rows": all_rows[: limit + 1], "fills": None, "total": max(len(all_rows) - 1, 0)}

def zip_dir(folder, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(os.listdir(folder)):
            z.write(os.path.join(folder, n), n)
    return dest

def run_cli(main, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            code = main(argv)
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()
`;

let py = null;
let picked = {}; // input id -> [{name, bytes}]
let lastOutput = null;

function setStatus(text, kind = "") {
  const el = $("#status");
  el.textContent = text;
  el.dataset.kind = kind;
}

async function boot() {
  setStatus("Loading Python in your browser (first load takes a few seconds)...", "busy");
  try {
    const { loadPyodide } = await import(`${PYODIDE_URL}pyodide.mjs`);
    py = await loadPyodide({ indexURL: PYODIDE_URL });
    await py.loadPackage("micropip");
    const micropip = py.pyimport("micropip");
    await micropip.install(D.packages);
    // Packages whose only non-pure dependency is not needed by this tool (named on the page).
    if (D.pip_nodeps) await micropip.install.callKwargs(D.pip_nodeps, { deps: false });
    const zip = await (await fetch("pkg.zip")).arrayBuffer();
    py.FS.mkdirTree("/app");
    py.unpackArchive(zip, "zip", { extractDir: "/app" });
    await py.runPythonAsync(`import sys\nsys.path.insert(0, "/app")\n${HELPERS}\n${D.python}`);
    setStatus(`Ready. Python ${py.version} with ${D.pkg} loaded.`, "ok");
    document.body.dataset.ready = "1";
    for (const b of document.querySelectorAll("button.run")) b.disabled = false;
  } catch (err) {
    setStatus(`Could not load the Python runtime: ${err.message}`, "bad");
    console.error(err);
  }
}

function buildInputs() {
  const box = $("#inputs");
  for (const inp of D.inputs) {
    const zone = document.createElement("label");
    zone.className = "drop card";
    zone.innerHTML = `<input type="file" accept="${inp.accept}" ${inp.multiple ? "multiple" : ""} hidden>
      <span class="drop-label">${inp.label}</span>
      <span class="drop-file" data-for="${inp.id}">${inp.optional ? "Optional: leave empty to use the sample" : "Drop a file here or click to choose"}</span>`;
    const fileInput = zone.querySelector("input");
    const take = async (files) => {
      picked[inp.id] = await Promise.all(
        [...files].map(async (f) => ({ name: f.name, bytes: new Uint8Array(await f.arrayBuffer()) })),
      );
      zone.querySelector(".drop-file").textContent = picked[inp.id].map((f) => f.name).join(", ");
      zone.classList.add("has");
    };
    fileInput.addEventListener("change", () => take(fileInput.files));
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("over"));
    zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); take(e.dataTransfer.files); });
    box.appendChild(zone);
  }
  const opts = $("#options");
  for (const o of D.options || []) {
    const row = document.createElement("label");
    row.className = "opt";
    if (o.type === "checkbox") {
      row.innerHTML = `<input type="checkbox" id="opt-${o.id}" ${o.value ? "checked" : ""}> <span>${o.label}</span>`;
    } else if (o.type === "select") {
      row.innerHTML = `<span>${o.label}</span> <select id="opt-${o.id}">${o.choices
        .map((c) => `<option value="${c[0]}" ${c[0] === o.value ? "selected" : ""}>${c[1]}</option>`).join("")}</select>`;
    } else {
      row.innerHTML = `<span>${o.label}</span> <input type="text" id="opt-${o.id}" value="${escapeHtml(o.value)}" placeholder="${escapeHtml(o.placeholder || "")}">`;
    }
    opts.appendChild(row);
  }
}

function readOptions() {
  const out = {};
  for (const o of D.options || []) {
    const el = $(`#opt-${o.id}`);
    out[o.id] = o.type === "checkbox" ? el.checked : el.value;
  }
  return out;
}

async function loadSamples(only = D.inputs) {
  const out = {};
  for (const inp of only) {
    const list = Array.isArray(inp.sample) ? inp.sample : [inp.sample];
    out[inp.id] = await Promise.all(list.map(async (p) => ({
      name: p.split("/").pop(),
      bytes: new Uint8Array(await (await fetch(p)).arrayBuffer()),
    })));
  }
  return out;
}

async function run(useSample) {
  if (!py) return;
  if (!useSample && D.inputs.some((i) => !i.optional && !picked[i.id]?.length)) {
    setStatus("Choose a file for each box first, or use the sample.", "bad");
    return;
  }
  setStatus("Running...", "busy");
  for (const b of document.querySelectorAll("button.run")) b.disabled = true;
  try {
    // An optional box left empty falls back to its bundled sample (for example a rules file).
    const files = useSample
      ? await loadSamples()
      : { ...(await loadSamples(D.inputs.filter((i) => i.optional && !picked[i.id]?.length))), ...picked };
    py.runPython(`import shutil, os\nshutil.rmtree("/work", ignore_errors=True)\nos.makedirs("/work/in")`);
    const paths = {};
    for (const [id, list] of Object.entries(files)) {
      py.FS.mkdirTree(`/work/in/${id}`);
      paths[id] = list.map((f) => {
        const p = `/work/in/${id}/${f.name}`;
        py.FS.writeFile(p, f.bytes);
        return p;
      });
    }
    py.globals.set("_paths_json", JSON.stringify(paths));
    py.globals.set("_opts_json", JSON.stringify(readOptions()));
    const res = JSON.parse(await py.runPythonAsync(`json.dumps(run(json.loads(_paths_json), json.loads(_opts_json)))`));
    render(res, useSample);
    setStatus(res.ok === false ? "The tool reported an error, see the log." : "Done.", res.ok === false ? "bad" : "ok");
  } catch (err) {
    setStatus(`Error: ${err.message.split("\n").slice(-2).join(" ")}`, "bad");
    console.error(err);
  } finally {
    for (const b of document.querySelectorAll("button.run")) b.disabled = false;
  }
}

function render(res, useSample) {
  $("#results").hidden = false;
  $("#log").textContent = res.log.trim() || "(no output)";
  const tabs = $("#tabs");
  const table = $("#table");
  tabs.innerHTML = "";
  const show = (i) => {
    [...tabs.children].forEach((t, j) => t.classList.toggle("on", i === j));
    const s = res.sheets[i];
    const [head, ...body] = s.rows;
    const fills = s.fills || [];
    const cell = (v, r, c, tag) => {
      const f = fills[r]?.[c];
      return `<${tag}${f ? ` style="background:${f}33"` : ""}>${escapeHtml(v)}</${tag}>`;
    };
    table.innerHTML = `<thead><tr>${(head || []).map((v, c) => cell(v, 0, c, "th")).join("")}</tr></thead>
      <tbody>${body.map((row, r) => `<tr>${row.map((v, c) => cell(v, r + 1, c, "td")).join("")}</tr>`).join("")}</tbody>`;
    $("#more").textContent = s.total > body.length ? `Showing ${body.length} of ${s.total} rows. The download has all of them.` : `${s.total} rows.`;
  };
  res.sheets.forEach((s, i) => {
    const b = document.createElement("button");
    b.className = "tab";
    b.textContent = `${s.name} (${s.total})`;
    b.onclick = () => show(i);
    tabs.appendChild(b);
  });
  if (res.sheets.length) show(0);
  const dl = $("#download");
  if (lastOutput) URL.revokeObjectURL(lastOutput);
  if (res.download) {
    const bytes = py.FS.readFile(res.download);
    const name = res.download.split("/").pop();
    lastOutput = URL.createObjectURL(new Blob([bytes]));
    dl.href = lastOutput;
    dl.download = name;
    dl.textContent = `Download ${name}`;
    dl.hidden = false;
  } else {
    dl.hidden = true;
  }
  $("#source").textContent = useSample ? "Input: bundled synthetic sample." : "Input: your file (it stayed in this browser tab).";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

document.title = `${D.title} | Live demo`;
$("#title").textContent = D.title;
$("#tagline").textContent = D.tagline;
$("#repo").href = `https://github.com/chasebuilds/${D.repo}`;
$("#sample-note").innerHTML = D.sampleNote;
buildInputs();
$("#run-sample").onclick = () => run(true);
$("#run-mine").onclick = () => run(false);
boot();
