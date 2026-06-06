# usage record

A plain record of how I actually work with language models, read back from my own Claude Code session logs. Live at **[llms.danilakozlov.com](https://llms.danilakozlov.com)**.

Instead of describing how I use LLMs, I had a script read all 519 of my own session transcripts and sum the metadata. The page is the result.

## What it shows

- **7.3 tool actions per instruction** I give — I mostly direct the model and it does the rest
- **108 sub-agents** running in parallel under a single workflow, nested **6 levels** deep
- **98% of input** read back from cache, the signature of long, stateful sessions rather than one-off prompts
- **~339K lines** of code edited or written across **1,170 files** (Python, TypeScript, LaTeX, Astro, and more)
- Each new frontier model adopted within a day or two of release
- Daily-output timeline, tool-call breakdown, per-project view, and a few of the things this turned into

## Privacy

`build_data.py` reads **only metadata** — token counts, tool names, models, timestamps, and file extensions. It never reads, stores, or emits the content of any prompt, file, or response. Project names are generic. Everything published is an aggregate, and the source is here so it can be checked.

## Run it yourself

```bash
python3 build_data.py        # regenerate data.json from ~/.claude/projects
python3 -m http.server 8777  # then open http://localhost:8777
```

`index.html` + `data.json`, no build step, no tracking. Inference value is estimated at Anthropic public list prices (notional, not subscription spend).
