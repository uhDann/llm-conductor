#!/usr/bin/env python3
"""
Aggregate Claude Code session telemetry into a single anonymized data.json.

PRIVACY: This script reads ONLY metadata (token counts, tool names, models,
timestamps, message *types*). It never reads, stores, or emits the *content*
of any prompt, file, or response. Project directories are mapped to generic
labels. The output is pure aggregate numbers — nothing identifying ships.
"""
import os, json, glob
from collections import Counter

ROOT = os.path.expanduser("~/.claude/projects")

# Anonymized, generic labels for the project dirs. Anything not listed is
# folded into "Background workflows" so no raw dir name ever leaks.
PROJECT_LABELS = {
    "-Users-danilakozlov":                    "Orchestration & personal automation",
    "-Users-danilakozlov-Desktop-Group-Project": "Collaborative multi-agent build",
    "-Users-danilakozlov-Desktop-build-space":   "Agentic dev sandbox",
    "-Users-danilakozlov-Desktop-fin-kg":        "Financial knowledge-graph engine",
    "-Users-danilakozlov-Desktop-slam":          "Robotics perception (SLAM)",
    "-Users-danilakozlov-Desktop-spatial-kittens": "Spatial-AI experiment",
}
def label_for(dirname):
    return PROJECT_LABELS.get(dirname, "Background workflows")

# Anthropic list prices, USD per million tokens. Used to estimate the *value*
# of inference directed (notional, at public API rates — not subscription spend).
# (input, output, cache_read, cache_write)
PRICING = {
    "opus":   (15.0, 75.0, 1.50, 18.75),
    "sonnet": (3.0,  15.0, 0.30, 3.75),
    "haiku":  (1.0,  5.0,  0.10, 1.25),
}
def price_tier(model):
    if "haiku" in model:  return "haiku"
    if "sonnet" in model: return "sonnet"
    return "opus"

def cost_for(tier, inp, out, cr, cw):
    i, o, r, w = PRICING[tier]
    return (inp*i + out*o + cr*r + cw*w) / 1_000_000

# Map file extensions to a human language/format label for the "code shipped" view.
LANG_EXT = {
    "py":"Python", "ts":"TypeScript", "tsx":"TypeScript (React)", "js":"JavaScript",
    "jsx":"JavaScript (React)", "vue":"Vue", "astro":"Astro", "svelte":"Svelte",
    "html":"HTML", "css":"CSS", "scss":"CSS", "tex":"LaTeX", "md":"Markdown",
    "sh":"Shell", "bash":"Shell", "zsh":"Shell", "rs":"Rust", "go":"Go",
    "c":"C", "h":"C/C++", "cc":"C++", "cpp":"C++", "hpp":"C++", "cu":"CUDA",
    "java":"Java", "rb":"Ruby", "swift":"Swift", "sol":"Solidity",
    "json":"JSON", "toml":"TOML", "yaml":"YAML", "yml":"YAML", "sql":"SQL",
    "ipynb":"Jupyter", "txt":"Text",
}
def lang_for(path):
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return LANG_EXT.get(ext)

# Human comparison anchors for the headline token figure (clearly notional).
TOKENS_PER_BOOK = 90_000     # ~300-page book at ~750 tokens/page
CHARS_PER_LINE  = 40         # rough average for code/markup

def main():
    files = glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True)

    intok = outtok = cacheread = cachecreate = 0
    assistant_turns = user_turns = agents = web_calls = 0
    models = Counter(); tools = Counter()
    by_day_events = Counter(); by_day_out = Counter(); by_hour = Counter()
    proj_out = Counter(); proj_agents = Counter(); proj_turns = Counter()
    # per-tier token accumulation for cost estimation
    tier_tok = {t: {"in":0,"out":0,"cr":0,"cw":0} for t in PRICING}

    # --- new metric accumulators ---
    total_tool_calls = 0
    human_prompts = 0                 # genuine user instructions (str content, not sidechain)
    edit_calls = write_calls = 0
    code_chars = 0
    touched_files = set()             # distinct file paths edited/written
    lang_calls = Counter()            # Edit/Write/Read calls per language
    model_first = {}                  # model id -> earliest ISO timestamp seen

    for fp in files:
        # Attribute by the TOP-LEVEL project dir under ~/.claude/projects, so that
        # nested sub-agent / workflow transcripts (…/<session>/subagents/wf_*/agent-*.jsonl)
        # roll up to the project they belong to rather than a generic bucket.
        top = os.path.relpath(fp, ROOT).split(os.sep)[0]
        lab = label_for(top)
        try:
            fh = open(fp, errors="ignore")
        except Exception:
            continue
        for line in fh:
            try:
                o = json.loads(line)
            except Exception:
                continue
            t = o.get("type")
            if t == "assistant":
                assistant_turns += 1; proj_turns[lab] += 1
            elif t == "user":
                user_turns += 1
                # A genuine human instruction: plain string content, not an
                # agent-to-agent sidechain message or a tool_result echo.
                if not o.get("isSidechain"):
                    uc = o.get("message", {}).get("content") if isinstance(o.get("message"), dict) else None
                    if isinstance(uc, str) and uc.strip():
                        human_prompts += 1
            ts = o.get("timestamp", "")
            if len(ts) >= 10:
                by_day_events[ts[:10]] += 1
                if len(ts) >= 13 and ts[11:13].isdigit():
                    by_hour[int(ts[11:13])] += 1
            msg = o.get("message", {})
            if isinstance(msg, dict):
                m = msg.get("model")
                if m and m != "<synthetic>":
                    models[m] += 1
                    if ts and (m not in model_first or ts < model_first[m]):
                        model_first[m] = ts
                u = msg.get("usage")
                if isinstance(u, dict):
                    o_ = u.get("output_tokens", 0)
                    i_ = u.get("input_tokens", 0)
                    cr_ = u.get("cache_read_input_tokens", 0)
                    cw_ = u.get("cache_creation_input_tokens", 0)
                    intok += i_; outtok += o_
                    cacheread += cr_; cachecreate += cw_
                    proj_out[lab] += o_
                    if len(ts) >= 10:
                        by_day_out[ts[:10]] += o_
                    if m and m != "<synthetic>":
                        bucket = tier_tok[price_tier(m)]
                        bucket["in"]+=i_; bucket["out"]+=o_; bucket["cr"]+=cr_; bucket["cw"]+=cw_
                c = msg.get("content")
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            n = b.get("name", "?")
                            tools[n] += 1
                            total_tool_calls += 1
                            if n in ("Agent", "TaskCreate"):
                                agents += 1; proj_agents[lab] += 1
                            if n in ("WebSearch", "WebFetch"):
                                web_calls += 1
                            inp = b.get("input") or {}
                            if isinstance(inp, dict):
                                if n == "Edit":
                                    edit_calls += 1
                                    code_chars += len(inp.get("new_string") or "")
                                elif n == "Write":
                                    write_calls += 1
                                    code_chars += len(inp.get("content") or "")
                                fpth = inp.get("file_path")
                                if fpth and n in ("Edit", "Write", "Read"):
                                    if n in ("Edit", "Write"):
                                        touched_files.add(fpth)
                                    lg = lang_for(fpth)
                                    if lg:
                                        lang_calls[lg] += 1

    days = sorted(by_day_events)
    timeline = [
        {"date": d, "events": by_day_events[d], "out_tokens": by_day_out[d]}
        for d in days
    ]
    projects = sorted(
        ({"label": lab, "out_tokens": proj_out[lab],
          "agents": proj_agents[lab], "turns": proj_turns[lab]}
         for lab in proj_out),
        key=lambda x: -x["out_tokens"],
    )

    # Friendly display names for tools
    TOOL_NAMES = {
        "mcp__playwright__browser_navigate": "Browser (Playwright)",
        "mcp__playwright__browser_snapshot": "Browser snapshot",
        "mcp__playwright__browser_evaluate": "Browser eval",
    }
    top_tools = [
        {"name": TOOL_NAMES.get(n, n), "count": c}
        for n, c in tools.most_common(14)
    ]

    est_cost = sum(cost_for(t, b["in"], b["out"], b["cr"], b["cw"])
                   for t, b in tier_tok.items())
    cost_by_tier = {t: round(cost_for(t, b["in"], b["out"], b["cr"], b["cw"]), 2)
                    for t, b in tier_tok.items() if b["out"] or b["in"]}

    # Cache efficiency: share of all input-side tokens served from cache.
    input_side = intok + cacheread + cachecreate
    cache_ratio = round(cacheread / input_side, 4) if input_side else 0

    # Parallel-agent fan-out and nesting depth, from the on-disk transcript tree.
    # A workflow dir (wf_*) or a session's subagents/ tree holds one file per agent.
    wf_counts = Counter(); session_counts = Counter(); max_depth = 0
    for fp in files:
        parts = os.path.relpath(fp, ROOT).split(os.sep)
        max_depth = max(max_depth, len(parts))
        for i, p in enumerate(parts):
            if p.startswith("wf_"):
                wf_counts[os.sep.join(parts[:i + 1])] += 1
        if "subagents" in parts:
            si = parts.index("subagents")
            session_counts[os.sep.join(parts[:si])] += 1
    peak_fanout = max(wf_counts.values()) if wf_counts else 0
    peak_session_agents = max(session_counts.values()) if session_counts else 0

    # Leverage: autonomous actions per genuine human instruction.
    leverage = round(total_tool_calls / human_prompts, 1) if human_prompts else 0
    code_lines = round(code_chars / CHARS_PER_LINE)
    books = round((intok + outtok + cacheread + cachecreate) / TOKENS_PER_BOOK)

    languages = [{"name": n, "count": c} for n, c in lang_calls.most_common(10)]
    model_timeline = sorted(
        ({"name": m.replace("claude-", "").replace("-20251001", ""), "first": ts[:10]}
         for m, ts in model_first.items()),
        key=lambda x: x["first"],
    )

    data = {
        "totals": {
            "est_value_usd": round(est_cost),
            "cost_by_tier": cost_by_tier,
            "cache_ratio": cache_ratio,
            "transcripts": len(files),
            "active_days": len(by_day_events),
            "first_day": days[0] if days else None,
            "last_day": days[-1] if days else None,
            "assistant_turns": assistant_turns,
            "user_turns": user_turns,
            "total_turns": assistant_turns + user_turns,
            "agents_spawned": agents,
            "web_calls": web_calls,
            "input_tokens": intok,
            "output_tokens": outtok,
            "cache_read_tokens": cacheread,
            "cache_create_tokens": cachecreate,
            "total_tokens": intok + outtok + cacheread + cachecreate,
            "distinct_models": len(models),
            "distinct_tools": len(tools),
            # --- new headline metrics ---
            "total_tool_calls": total_tool_calls,
            "human_prompts": human_prompts,
            "leverage": leverage,            # tool actions per human instruction
            "peak_fanout": peak_fanout,      # most agents under one workflow
            "peak_session_agents": peak_session_agents,
            "max_depth": max_depth,          # deepest agent-spawning-agent nesting
            "edit_calls": edit_calls,
            "write_calls": write_calls,
            "code_edits": edit_calls + write_calls,
            "code_lines": code_lines,
            "files_touched": len(touched_files),
            "books_equiv": books,
        },
        "models": [{"name": m, "count": c} for m, c in models.most_common()],
        "tools": top_tools,
        "timeline": timeline,
        "projects": projects,
        "languages": languages,
        "model_timeline": model_timeline,
        "hours": [{"hour": h, "count": by_hour.get(h, 0)} for h in range(24)],
    }
    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print("wrote", out_path)
    print(json.dumps(data["totals"], indent=2))

if __name__ == "__main__":
    main()
