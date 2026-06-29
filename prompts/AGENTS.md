# Project Context — Levesia VPS Agent

## Environment
- OS: Ubuntu 22/24 LTS
- Shell: bash
- Python: 3.11+
- Node.js: 20+
- AI Backend: Groq API (llama3-70b-8192)
- Web Search: DuckDuckGo (no API key required)
- Discord Framework: discord.py 2.x

## Directory Layout
```
/home/levesia/
  bot/          # Discord bot + cogs
  workspace/    # Per-task code execution dirs (auto-cleaned)
  output/       # Zipped deliverables
  skills/       # Hermes-style skill scripts (.sh + .yaml pairs)
  logs/         # Execution + bot logs
  config/       # config.yaml
  prompts/      # SOUL.md, AGENTS.md, MEMORY.md, USER.md
```

## Hermes Skill System
Skills are reusable multi-step workflows stored as .sh scripts
with a YAML front-matter header. They run on demand via !skill run <name>.
Skills can also be AI-generated via !skill create <name> <description>.

## Code Generation Pipeline
1. !code <prompt> → Groq generates structured JSON {language, files, description}
2. Files written to /home/levesia/workspace/<task_id>/
3. Deps installed (requirements.txt / package.json etc.)
4. Code executed, stdout+stderr → run.log
5. On success: zipped → /home/levesia/output/<task_id>.zip → sent to Discord
6. On failure: error excerpt sent inline

## Web Search Pipeline
!search <query> → DuckDuckGo scrape → Groq summarizes results → Discord embed
!ask <question> → same pipeline but framed as Q&A with sources

## Coding Rules
- Always include a runnable entrypoint
- Always include a README.md in every zip
- Never hardcode secrets — use .env + python-dotenv
- Generated code must run cleanly before zipping
- Never expose /etc/passwd, SSH keys, .env via Discord
