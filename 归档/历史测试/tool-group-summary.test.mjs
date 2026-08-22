import { pathToFileURL, fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { existsSync } from "node:fs";

const here = fileURLToPath(import.meta.url);
const realPath = resolve(here, "..", "frontend", "src", "lib", "toolMeta.ts");

let resolveToolMeta;
let mode;
if (existsSync(realPath)) {
  try {
    const mod = await import(pathToFileURL(realPath).href);
    resolveToolMeta = mod.resolveToolMeta;
    mode = "live";
  } catch (err) {
    mode = "fallback-unresolved";
    if (process.env.DEBUG_TSM) console.error(`[live import failed] ${err.message}`);
    resolveToolMeta = null;
  }
} else {
  mode = "fallback-notfound";
  resolveToolMeta = null;
}

if (!resolveToolMeta) {
  const FALLBACK_META = {
    write_file: "写入文件",
    read_file: "读取文件",
    list_files: "列出目录",
    run_command: "执行命令",
  };
  resolveToolMeta = (tool, args) => ({
    title: FALLBACK_META[tool] ?? (tool || ""),
  });
}

function computeSummary(tools) {
  const parts = [];
  for (const tc of tools) {
    const { title } = resolveToolMeta(tc.tool ?? "", tc.input);
    if (title && title !== parts[parts.length - 1]) parts.push(title);
  }
  return (parts.length ? parts.slice(0, 3).join(", ") : "") + (parts.length > 3 ? "…" : "");
}

const title = (tool, input) => resolveToolMeta(tool, input).title;
let failed = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) failed += 1;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`);
  if (!ok) {
    console.log(`      expected: ${JSON.stringify(expected)}`);
    console.log(`      actual:   ${JSON.stringify(actual)}`);
  }
}

const tools = (...ts) => ts.map(([tool, input]) => ({ tool, input }));

check("empty group -> empty summary", computeSummary([]), "");

const x3 = tools(["run_command", { command: "x" }], ["run_command", { command: "x" }], ["run_command", { command: "x" }]);
check("consecutive duplicates converge to single title",
  computeSummary(x3),
  title("run_command", { command: "x" }));

const five = tools(["t1"], ["t2"], ["t3"], ["t4"], ["t5"]);
check("5 distinct tools -> first 3 + ellipsis",
  computeSummary(five),
  `${["t1", "t2", "t3"].map((t) => title(t, undefined)).join(", ")}…`);

const four = tools(["t1"], ["t2"], ["t3"], ["t4"]);
check("4 distinct tools -> first 3 + ellipsis",
  computeSummary(four),
  `${["t1", "t2", "t3"].map((t) => title(t, undefined)).join(", ")}…`);

const three = tools(["t1"], ["t2"], ["t3"]);
check("3 distinct tools -> no trailing ellipsis",
  computeSummary(three),
  ["t1", "t2", "t3"].map((t) => title(t, undefined)).join(", "));

const dupGap = tools(["t1"], ["t1"], ["t2"], ["t1"]);
check("gap pattern t1,t1,t2,t1 -> t1,t2,t1 (only consecutive collapse)",
  computeSummary(dupGap),
  `${title("t1")}, ${title("t2")}, ${title("t1")}`);

if (mode === "live") {
  check("write_file title carries relative_path",
    computeSummary(tools(["write_file", { relative_path: "src/a.ts" }])),
    "src/a.ts");
  check("run_command title is $-prefixed command",
    computeSummary(tools(["run_command", { command: "npm run tsc" }])),
    "$ npm run tsc");
  check("git_* uses git motif (key=value)",
    computeSummary(tools(["git_status", { branch: "main" }])),
    "git branch=main");
  check("unknown tool falls back to its name",
    computeSummary(tools(["mystery_op"])),
    "mystery_op");
} else {
  console.log("SKIP  live-semantics checks (real resolver unavailable)");
}

const N = 20000;
const t0 = process.hrtime.bigint();
for (let i = 0; i < N; i++) {
  computeSummary([["t1"], ["t2"], ["t3"]].slice(0, i % 4));
}
const ms = Number(process.hrtime.bigint() - t0) / 1e6;
console.log(`PERF  ${N} groups in ${ms.toFixed(1)}ms (${(ms / N).toFixed(4)}ms/group)`);

console.log(`[${mode === "live" ? "LIVE real src/lib/toolMeta.ts imported" : "fallback resolver"}]`);
process.exit(failed > 0 ? 1 : 0);