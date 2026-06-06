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

def main():
    files = glob.glob(os.path.join(ROOT, "**", "*.jsonl"), recursive=True)

    intok = outtok = cacheread = cachecreate = 0
    assistant_turns = user_turns = agents = web_calls = 0
    models = Counter(); tools = Counter()
    by_day_events = Counter(); by_day_out = Counter(); by_hour = Counter()
    proj_out = Counter(); proj_agents = Counter(); proj_turns = Counter()

    for fp in files:
        d = os.path.basename(os.path.dirname(fp))
        lab = label_for(d)
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
                u = msg.get("usage")
                if isinstance(u, dict):
                    o_ = u.get("output_tokens", 0)
                    intok += u.get("input_tokens", 0); outtok += o_
                    cacheread += u.get("cache_read_input_tokens", 0)
                    cachecreate += u.get("cache_creation_input_tokens", 0)
                    proj_out[lab] += o_
                    if len(ts) >= 10:
                        by_day_out[ts[:10]] += o_
                c = msg.get("content")
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            n = b.get("name", "?")
                            tools[n] += 1
                            if n in ("Agent", "TaskCreate"):
                                agents += 1; proj_agents[lab] += 1
                            if n in ("WebSearch", "WebFetch"):
                                web_calls += 1

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

    data = {
        "totals": {
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
        },
        "models": [{"name": m, "count": c} for m, c in models.most_common()],
        "tools": top_tools,
        "timeline": timeline,
        "projects": projects,
        "hours": [{"hour": h, "count": by_hour.get(h, 0)} for h in range(24)],
    }
    out_path = os.path.join(os.path.dirname(__file__), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print("wrote", out_path)
    print(json.dumps(data["totals"], indent=2))

if __name__ == "__main__":
    main()
