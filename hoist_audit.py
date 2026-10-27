#!/usr/bin/env python3
"""hoist audit: reverse-engineer the lasting decisions baked into a repo.

Reads the files that reveal decisions (manifests, Dockerfiles, CI, infra config),
asks Muse Spark to infer each decision, then writes ADR files and a Mermaid graph.

Spend guardrails (Meta's console only offers notifications, so they live here):
  * cost estimate printed before every call, and the call is refused if it could exceed --max-cost
  * output is capped with max_completion_tokens, so the worst case is known up front
  * every call is logged to ~/.hoist/spend.json and refused once --budget is used up

Usage:
  export MODEL_API_KEY=...                       # from dev.meta.ai, never commit it
  python hoist_audit.py ./my-repo --dry-run      # free: shows what would be sent and the cost ceiling
  python hoist_audit.py ./my-repo                # one call to Muse Spark
  python hoist_audit.py https://github.com/org/repo
  python hoist_audit.py ./my-repo --from-json .hoist/last_response.json   # re-render, no API call
"""
import argparse, fnmatch, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

# Published "starting at" prices for Muse Spark (USD per 1M tokens). Reasoning tokens bill as output.
PRICE_IN, PRICE_OUT = 1.25, 4.25
BASE_URL = "https://api.meta.ai/v1"
LEDGER = Path.home() / ".hoist" / "spend.json"

EVIDENCE = [  # files that reveal decisions, in priority order
    "package.json", "pnpm-workspace.yaml", "turbo.json", "nx.json", "deno.json",
    "pyproject.toml", "requirements*.txt", "Pipfile", "setup.py", "go.mod", "Cargo.toml",
    "Gemfile", "composer.json", "pom.xml", "build.gradle*", "mix.exs",
    "Dockerfile*", "docker-compose*.y*ml", "compose*.y*ml", "Procfile",
    ".github/workflows/*.y*ml", ".gitlab-ci.yml", ".circleci/config.yml", "buildkite*.y*ml", "Jenkinsfile",
    "vercel.json", "netlify.toml", "fly.toml", "render.yaml", "railway.json", "app.yaml", "serverless.y*ml",
    "*.tf", "wrangler.toml", "Chart.yaml", "k8s/*.y*ml", "kubernetes/*.y*ml",
    "prisma/schema.prisma", "drizzle.config.*", "schema.sql", "alembic.ini", "supabase/config.toml",
    "tsconfig.json", "next.config.*", "vite.config.*", "nuxt.config.*", "astro.config.*",
    ".env.example", ".env.sample", "LICENSE*", "README*", "docs/decisions/*.md", "docs/adr/*.md",
]
SKIP_DIRS = {".git", ".hoist", ".hoist-test-backup", ".muse", ".agents", "node_modules", "vendor", "dist", "build", ".next", "venv", ".venv", "__pycache__", "target", ".turbo", "coverage"}
PER_FILE_CHARS = 6000
MAX_FILES = 80

SYSTEM = """You are Hoist, an auditor that reverse-engineers the lasting technical decisions in a codebase.
Only report decisions that are costly to change (language, framework, database, ORM, auth, hosting,
CI, repo/monorepo layout, package manager, queue, cache, API style, license, model provider).
Skip trivial library picks. For every claim, cite the file that shows it.

Tag each decision's confidence:
  "seen"     - a file states it directly
  "inferred" - strongly implied by evidence but not stated
  "unknown"  - the repo needs this decision but shows no clear answer

door: 1 = two-way (an afternoon to undo), 2 = heavy (days), 3 = one-way (rewrite to undo).

Reply with JSON only, no prose, matching:
{"project": str, "summary": str,
 "decisions": [{"id": "kebab-case", "title": str, "choice": str, "alternatives": [str],
   "door": 1|2|3, "confidence": "seen"|"inferred"|"unknown",
   "evidence": [{"file": str, "detail": str}],
   "depends_on": [decision ids], "why_it_matters": str,
   "flip_if": str, "verify": [str]}]}
Order decisions so that ones others depend on come first. Plain language, short sentences."""


def collect(root: Path):
    files, seen = [], set()
    for pat in EVIDENCE:
        for p in sorted(root.glob(pat)) + sorted(root.glob("*/" + pat)) + sorted(root.glob("*/*/" + pat)):
            if any(part in SKIP_DIRS for part in p.parts) or not p.is_file() or p in seen:
                continue
            seen.add(p); files.append(p)
            if len(files) >= MAX_FILES:
                return files
    return files


def tree(root: Path, depth=2):
    lines = []
    def walk(d, lvl):
        try:
            kids = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name))
        except OSError:
            return
        for k in kids[:40]:
            if k.name in SKIP_DIRS or (k.name.startswith(".") and k.name not in {".github", ".gitlab-ci.yml", ".env.example"}):
                continue
            lines.append("  " * lvl + k.name + ("/" if k.is_dir() else ""))
            if k.is_dir() and lvl + 1 < depth:
                walk(k, lvl + 1)
    walk(root, 0)
    return "\n".join(lines[:300])


def pack(root: Path):
    parts = [f"# Directory layout\n{tree(root)}"]
    for p in collect(root):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        if p.name.lower().startswith("readme"):
            text = text[:2500]
        tail = "\n[...truncated]" if len(text) > PER_FILE_CHARS else ""
        parts.append(f"# File: {p.relative_to(root)}\n{text[:PER_FILE_CHARS]}{tail}")
    return "\n\n".join(parts)


def est_tokens(s):  # rough: ~4 chars per token
    return len(s) // 4 + 1


def ledger():
    try:
        return json.loads(LEDGER.read_text())
    except (OSError, ValueError):
        return {"total_usd": 0.0, "calls": []}


def record(entry):
    led = ledger(); led["total_usd"] = round(led["total_usd"] + entry["usd"], 6); led["calls"].append(entry)
    LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text(json.dumps(led, indent=2))
    return led


def call_muse(prompt, args):
    from openai import OpenAI  # imported here so --dry-run and --from-json need no install
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("Set MODEL_API_KEY first (create a key at dev.meta.ai).")
    client = OpenAI(base_url=BASE_URL, api_key=key)
    t = time.time()
    kw = dict(model=args.model, max_completion_tokens=args.max_output,
              messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
    if args.effort:
        kw["extra_body"] = {"reasoning_effort": args.effort}
    resp = client.chat.completions.create(**kw)
    u = resp.usage
    usd = (u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT) / 1e6
    led = record({"at": time.strftime("%Y-%m-%d %H:%M"), "model": args.model, "repo": args.target,
                  "in": u.prompt_tokens, "out": u.completion_tokens, "usd": round(usd, 5)})
    print(f"Muse Spark: {u.prompt_tokens:,} in / {u.completion_tokens:,} out · ${usd:.4f} · {time.time()-t:.0f}s · "
          f"total spent via hoist ${led['total_usd']:.2f} of ${args.budget:.2f} budget")
    return resp.choices[0].message.content or "", resp.choices[0].finish_reason


def ask_muse(system, prompt, label, max_output=8000, max_cost=0.50, budget=25.0, effort="low"):
    """One guarded Muse Spark call for other Hoist commands: estimate, check the caps, call, log to the ledger."""
    model = os.environ.get("HOIST_MODEL", "muse-spark-1.1")
    tin = est_tokens(prompt) + est_tokens(system)
    worst = (tin * PRICE_IN + max_output * PRICE_OUT) / 1e6
    if worst > max_cost:
        sys.exit(f"Stopped: worst case ${worst:.3f} is above the ${max_cost:.2f} cap per call.")
    if ledger()["total_usd"] + worst > budget:
        sys.exit(f"Stopped: this call could push hoist's total past the ${budget:.2f} budget.")
    from openai import OpenAI
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("Set MODEL_API_KEY first (create a key at dev.meta.ai).")
    t = time.time()
    kw = dict(model=model, max_completion_tokens=max_output,
              messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    if effort:
        kw["extra_body"] = {"reasoning_effort": effort}
    resp = OpenAI(base_url=BASE_URL, api_key=key).chat.completions.create(**kw)
    u = resp.usage
    usd = (u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT) / 1e6
    led = record({"at": time.strftime("%Y-%m-%d %H:%M"), "model": model, "repo": label,
                  "in": u.prompt_tokens, "out": u.completion_tokens, "usd": round(usd, 5)})
    print(f"Muse Spark: {u.prompt_tokens:,} in / {u.completion_tokens:,} out · ${usd:.4f} · {time.time()-t:.0f}s · "
          f"total spent via hoist ${led['total_usd']:.2f} of ${budget:.2f}", file=sys.stderr)
    return resp.choices[0].message.content or "", resp.choices[0].finish_reason


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON object in the reply")
    return json.loads(m.group(0))


DOOR = {1: "Two-way door", 2: "Heavy door", 3: "One-way door"}
CONF = {"seen": "Seen", "inferred": "Inferred", "unknown": "Unknown"}


def write_outputs(data, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    decs = data.get("decisions", [])
    ids = {d["id"]: i + 1 for i, d in enumerate(decs)}
    for i, d in enumerate(decs, 1):
        adr = f"ADR-{i:03d}"
        ev = "\n".join(f"- `{e.get('file','?')}`: {e.get('detail','')}" for e in d.get("evidence", [])) or "- No direct evidence found."
        deps = ", ".join(f"ADR-{ids[x]:03d} ({x})" for x in d.get("depends_on", []) if x in ids) or "None"
        body = (f"# {adr}: {d['title']} → {d.get('choice') or 'Undecided'}\n\n"
                f"Status: Reconstructed by hoist audit · Confidence: {CONF.get(d.get('confidence'), '?')}\n"
                f"Door: {DOOR.get(d.get('door'), '?')} · Depends on: {deps}\n\n"
                f"## Evidence\n{ev}\n\n## Why it matters\n{d.get('why_it_matters','')}\n\n"
                f"## Alternatives\n" + "\n".join(f"- {a}" for a in d.get("alternatives", [])) +
                f"\n\n## Would change if\n- {d.get('flip_if','')}\n\n## Verify\n" +
                "\n".join(f"- [ ] {v}" for v in d.get("verify", [])) + "\n")
        (out / f"{adr}-{d['id']}.md").write_text(body)

    def label(d):
        s = f"{d['title']}: {d.get('choice') or '?'}"
        return s.replace('"', "'")
    g = ["graph LR"]
    for d in decs:
        g.append(f'  {d["id"].replace("-", "_")}["{label(d)}"]:::{"d" + str(d.get("door", 2))}{"_unk" if d.get("confidence") == "unknown" else ""}')
    for d in decs:
        for dep in d.get("depends_on", []):
            if dep in ids:
                g.append(f'  {dep.replace("-", "_")} --> {d["id"].replace("-", "_")}')
    g += ["  classDef d1 stroke:#2B7A57,stroke-width:2px",
          "  classDef d2 stroke:#9C640F,stroke-width:2px",
          "  classDef d3 stroke:#B03737,stroke-width:3px",
          "  classDef d1_unk stroke:#2B7A57,stroke-dasharray:4 3",
          "  classDef d2_unk stroke:#9C640F,stroke-dasharray:4 3",
          "  classDef d3_unk stroke:#B03737,stroke-width:3px,stroke-dasharray:4 3"]
    rows = "\n".join(f"| ADR-{i:03d} | {d['title']} | {d.get('choice') or '—'} | {DOOR.get(d.get('door'),'?')} | {CONF.get(d.get('confidence'),'?')} |"
                     for i, d in enumerate(decs, 1))
    (out / "graph.md").write_text(
        f"# Decision graph: {data.get('project','')}\n\n{data.get('summary','')}\n\n"
        "Red = one-way door, amber = heavy door, green = two-way door. Dashed = unknown, needs a decision.\n\n"
        "```mermaid\n" + "\n".join(g) + "\n```\n\n"
        "| ADR | Decision | Choice | Door | Confidence |\n|---|---|---|---|---|\n" + rows + "\n")
    return len(decs)


def main():
    ap = argparse.ArgumentParser(description="Reverse-engineer a repo's lasting decisions with Muse Spark.")
    ap.add_argument("target", help="Local path or git URL")
    ap.add_argument("--model", default=os.environ.get("HOIST_MODEL", "muse-spark-1.1"))
    ap.add_argument("--effort", default="low", help="reasoning_effort: minimal|low|medium|high|xhigh ('' to omit)")
    ap.add_argument("--max-input", type=int, default=120_000, help="Refuse if the prompt is estimated above this many tokens")
    ap.add_argument("--max-output", type=int, default=12_000, help="Hard cap on output + reasoning tokens")
    ap.add_argument("--max-cost", type=float, default=0.50, help="Refuse a single call whose worst case exceeds this (USD)")
    ap.add_argument("--budget", type=float, default=25.0, help="Refuse once hoist's logged total spend reaches this (USD)")
    ap.add_argument("--out", default=None, help="Output folder (default: <repo>/docs/decisions)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be sent and the cost ceiling; no API call")
    ap.add_argument("--from-json", help="Render from a saved response; no API call")
    args = ap.parse_args()

    tmp = None
    if re.match(r"^(https?://|git@)", args.target):
        tmp = tempfile.mkdtemp(prefix="hoist-")
        subprocess.run(["git", "clone", "--depth", "1", "-q", args.target, tmp], check=True)
        root = Path(tmp)
    else:
        root = Path(args.target).resolve()
    name = re.sub(r"\.git$", "", args.target.rstrip("/").split("/")[-1].split(":")[-1]) if tmp else root.name
    out = Path(args.out) if args.out else (Path.cwd() / "hoist-out" / name if tmp else root / "docs" / "decisions")

    if args.from_json:
        n = write_outputs(parse(Path(args.from_json).read_text()), out)
        print(f"Wrote {n} ADRs and graph.md to {out}"); return

    prompt = f"Repository: {args.target}\n\n" + pack(root)
    tin = est_tokens(prompt) + est_tokens(SYSTEM)
    worst = (tin * PRICE_IN + args.max_output * PRICE_OUT) / 1e6
    spent = ledger()["total_usd"]
    print(f"Evidence: {len(collect(root))} files · ~{tin:,} input tokens · worst case ${worst:.3f} "
          f"(cap ${args.max_cost:.2f}) · spent so far ${spent:.2f} of ${args.budget:.2f}")

    if args.dry_run:
        dump = Path.cwd() / ".hoist" / "last_prompt.txt"; dump.parent.mkdir(exist_ok=True); dump.write_text(prompt)
        print(f"Dry run. Prompt saved to {dump}"); return
    if tin > args.max_input:
        sys.exit(f"Stopped: prompt is ~{tin:,} tokens, above --max-input {args.max_input:,}.")
    if worst > args.max_cost:
        sys.exit(f"Stopped: worst case ${worst:.3f} is above --max-cost ${args.max_cost:.2f}.")
    if spent + worst > args.budget:
        sys.exit(f"Stopped: this call could push hoist's total past the ${args.budget:.2f} budget.")

    raw, finish = call_muse(prompt, args)
    runs = Path.cwd() / ".hoist" / "responses"; runs.mkdir(parents=True, exist_ok=True)
    save = runs / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}.json"; save.write_text(raw)
    (Path.cwd() / ".hoist" / "last_response.json").write_text(raw)
    if finish != "stop":
        sys.exit(f"Muse Spark stopped early (finish reason: {finish}). Nothing was written; raw reply saved to {save}. Run again, or raise --max-output if the reason is 'length'.")
    try:
        n = write_outputs(parse(raw), out)
    except (ValueError, KeyError) as e:
        sys.exit(f"Muse Spark replied, but the JSON did not parse ({e}). Raw reply saved to {save}.")
    print(f"Wrote {n} ADRs and graph.md to {out}")


if __name__ == "__main__":
    main()
