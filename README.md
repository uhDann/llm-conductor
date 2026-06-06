# I don't use LLMs. I conduct them.

A self-referential dashboard built for the **Paradigm Fellowship** question *"Show us how you're making use of LLMs."*

Instead of describing how I use language models, I let an LLM agent answer the question by parsing **my own usage**. It streamed **505 Claude Code session transcripts** spanning 54 active days and aggregated them into the numbers you see live at the site.

**The dashboard about how I use LLMs was built by one.**

## What it shows

- **19.1B tokens** processed and **57.4M** generated end-to-end
- **959 autonomous sub-agents** spawned (Agent + Task delegations)
- **103.5K directed turns** across 54 active days
- Four models chosen by job and economics (Opus 4.6 / 4.7 / 4.8 + Haiku 4.5)
- Tool-call distribution, daily output, per-project breadth, and hour-of-day rhythm

## Privacy

`build_data.py` reads **only metadata** — token counts, tool names, models, timestamps, and message *types*. It never reads, stores, or emits the content of any prompt, file, or response. Project directories are mapped to generic labels. Everything published is a pure aggregate. The source is here so you can verify that.

## Run it yourself

```bash
python3 build_data.py        # regenerate data.json from ~/.claude/projects
python3 -m http.server 8777  # then open http://localhost:8777
```

Built by [Danila Kozlov](https://github.com/uhDann) · `index.html` + `data.json`, no build step, no tracking.
