# ⚡ Levesia — Discord-Controlled VPS Engineering Assistant

A layered AI assistant (inspired by the Hermes Agent blueprint) running on your VPS,
controlled entirely via Discord. Powered by **Groq API** for fast inference and
**DuckDuckGo** for web search — no extra API keys needed for search.

---

## ✨ What Levesia Can Do

| Capability | How |
|---|---|
| Generate multi-file code in any language | `!code <prompt>` |
| Run & compile the code on your VPS | Automatic after generation |
| Zip everything + send back to Discord | Automatic after execution |
| Search the web + AI-summarize results | `!search <query>` |
| Answer questions using live web data | `!ask <question>` |
| Run Hermes-style reusable skill scripts | `!skill run <name>` |
| AI-generate new skills on demand | `!skill create <name> <desc>` |
| Monitor your VPS (CPU, RAM, disk, processes) | `!status`, `!ps`, `!mem` |
| All commands locked to your Discord user ID | Automatic — 🔒 for everyone else |

---

## 🗂️ Project Structure

```
levesia/
├── bot/
│   ├── bot.py              # Main entry point — loads all cogs
│   ├── executor.py         # Sandboxed code runner + zipper pipeline
│   ├── requirements.txt    # Python dependencies
│   └── cogs/
│       ├── codegen.py      # !code  !codefile  !run  !langs
│       ├── search.py       # !search  !ask  (DuckDuckGo + Groq)
│       ├── skills.py       # !skill list/run/show/create/delete
│       └── system.py       # !status !disk !mem !ps !logs !outputs !help
├── config/
│   └── config.yaml         # ⚠️  Edit this first
├── prompts/                # Hermes-style layered prompt architecture
│   ├── SOUL.md             # Identity, reasoning philosophy, defaults
│   ├── AGENTS.md           # VPS environment, pipelines, conventions
│   ├── MEMORY.md           # Persistent facts (paths, prefs, limits)
│   └── USER.md             # Owner profile
├── skills/                 # Hermes-style reusable skill scripts
│   ├── server-health.sh    # Full VPS health snapshot
│   ├── disk-cleanup.sh     # Remove old workspace/output files
│   ├── backup-outputs.sh   # Archive output zips
│   ├── check-ssl.sh        # SSL cert expiry checker
│   └── update-system.sh    # apt update + upgrade
└── setup.sh                # One-shot VPS installer
```

---

## 🚀 Quick Start

### Prerequisites
- Ubuntu 22.04 or 24.04 VPS
- Root SSH access
- [Discord bot token](https://discord.com/developers/applications)
- [Groq API key](https://console.groq.com) — free tier is plenty

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/taimiyaamjad/Levesia
```

### Step 2 — Run the installer

```bash
sudo su
cd Levesia
chmod +x setup.sh
bash setup.sh
```

The installer will:
- Install Python, Node.js, Go, Rust, GCC, Java, Ruby, PHP
- Create a dedicated unprivileged `levesia` system user
- Set up a Python virtualenv with all dependencies
- Copy all files to `/home/levesia/`
- Register and enable a `systemd` service

### Step 3 — Fill in config

```bash
nano /home/levesia/config/config.yaml
```

The three required fields:

```yaml
bot:
  token: "YOUR_DISCORD_BOT_TOKEN"
  owner_id: 123456789012345678   # Right-click yourself in Discord → Copy User ID

groq:
  api_key: "YOUR_GROQ_API_KEY"   # free at console.groq.com
```

### Step 4 — Start Levesia

```bash
systemctl start levesia
systemctl status levesia
```

### Step 5 — Test on Discord

```
!help
```

---

## 🧠 Code Generation — `!code`

Levesia asks Groq to generate structured multi-file code, runs it on the VPS,
and sends back a `.zip` with all source files + `run.log`.

```
!code build a FastAPI REST API with /health and /echo endpoints
!code write a Go CLI that fetches a URL and prints response time
!code create a Node.js script that reads a CSV and outputs JSON
!codefile build a Python web scraper for Hacker News top stories
!run python print(sum(range(1, 101)))
!run bash echo "uptime: $(uptime -p)"
```

### The pipeline

```
!code <prompt>
    │
    ▼
Groq API → JSON { language, files: {...}, description }
    │
    ▼
executor.py writes files to /home/levesia/workspace/<task_id>/
    │
    ▼
Install deps (requirements.txt / package.json / go.mod if present)
    │
    ▼
Run entrypoint → capture stdout + stderr → run.log
    │
    ├─ SUCCESS → zip all files → upload to Discord ✅
    └─ FAILURE → send error excerpt inline ❌
```

### Supported Languages

| Language | Entrypoint | Dep File |
|---|---|---|
| Python | `main.py` | `requirements.txt` |
| JavaScript | `index.js` | `package.json` |
| TypeScript | `index.ts` | `package.json` |
| Go | `main.go` | `go.mod` |
| Rust | `src/main.rs` | `Cargo.toml` |
| C | `main.c` | — |
| C++ | `main.cpp` | — |
| Java | `Main.java` | — |
| Bash | `main.sh` | — |
| Ruby | `main.rb` | `Gemfile` |
| PHP | `main.php` | — |

---

## 🔍 Web Search — `!search` and `!ask`

No extra API key required. Levesia scrapes DuckDuckGo and uses Groq to
summarize results into a clean Discord embed with cited sources.

```
!search latest Ubuntu 24.04 LTS features
!search nginx vs caddy performance 2024
!ask how do I set up a systemd timer on Ubuntu?
!ask what is the difference between TCP and UDP?
!ask how does Groq LPU inference work?
```

### The pipeline

```
!search <query>
    │
    ▼
DuckDuckGo HTML scrape → up to 8 results {title, url, snippet}
    │
    ▼
Groq summarizes results with source citations [1][2][3]
    │
    ▼
Discord embed: Summary + Sources
```

---

## 🔧 Hermes-Style Skills — `!skill`

Skills are reusable bash scripts stored in `/home/levesia/skills/` with a
YAML front-matter header (same pattern as the Hermes Agent blueprint).

### Built-in skills

| Skill | Description |
|---|---|
| `server-health` | Full VPS snapshot — CPU, RAM, disk, ports |
| `disk-cleanup` | Remove workspace + output files older than 7 days |
| `backup-outputs` | Archive all output zips into a dated tarball |
| `check-ssl` | Check SSL cert expiry for a domain |
| `update-system` | Run apt update + upgrade |

### Using skills

```
!skill list                          — see all skills
!skill run server-health             — run a skill
!skill run check-ssl example.com     — run with arguments
!skill show disk-cleanup             — view source
```

### Creating new skills with AI

The most powerful feature — Levesia generates new skills on demand:

```
!skill create restart-nginx Restart nginx and tail the last 20 error log lines
!skill create port-scan Scan common open ports on the VPS using netstat
!skill create git-pull-all Pull latest changes in all git repos under /home/levesia
!skill create db-backup Dump PostgreSQL database to /home/levesia/backups
```

Groq generates the script with proper YAML front-matter, saves it to
`/home/levesia/skills/<name>.sh`, and it's immediately available via `!skill run`.

### Skill format (Hermes-style)

```bash
---
name: my-skill
description: What this skill does in one sentence
safe: true
tags: [tag1, tag2]
---
#!/bin/bash
set -euo pipefail

echo "Running my-skill..."
# ... your script
```

---

## 🖥️ System Monitoring

```
!status     — Uptime, load average, memory, disk, IP
!disk       — Disk usage for all filesystems
!mem        — Memory + swap breakdown
!ps         — Top 15 processes by CPU
!logs 50    — Last 50 lines of Levesia's log
!outputs    — List recent zip deliverables
```

---

## 🔒 Security Model

| Rule | Detail |
|---|---|
| Owner-only | All commands locked to your Discord user ID. Others get 🔒 |
| No root execution | Bot and all code runs as unprivileged `levesia` user |
| No raw shell passthrough | All execution goes through `executor.py` only |
| Workspace isolation | Each task gets its own temp directory, cleaned after |
| No secret exposure | `.env`, SSH keys, `/etc/passwd` never sent to Discord |
| Size limit | Zips over 24MB rejected before upload |
| Timeout | Execution killed after 120s (configurable) |
| Destructive confirmation | Skills marked `safe: false` require a `yes` reply |

---

## 📐 Prompt Layer Architecture (Hermes Blueprint)

Levesia follows the Hermes Agent layered prompt architecture:

```
1. SOUL.md          → Identity, personality, reasoning defaults
2. Tool behavior    → executor, search, skills
3. MEMORY.md        → Persistent facts (paths, limits, prefs)
4. USER.md          → Owner profile
5. Skills index     → Available skill scripts
6. AGENTS.md        → VPS environment, pipelines, conventions
7. system_message   → Absolute rules (config.yaml) — override everything
8. Platform hint    → Discord
```

---

## ⚙️ Configuration Reference

```yaml
# config/config.yaml

bot:
  token: "..."          # Discord bot token
  owner_id: 123...      # Your Discord user ID
  prefix: "!"           # Command prefix

groq:
  api_key: "..."        # Groq API key
  model: "llama3-70b-8192"
  max_tokens: 8000

search:
  engine: "duckduckgo"  # No API key needed
  max_results: 8

execution:
  timeout_seconds: 120
  max_output_size_mb: 24
```

---

## 🛠️ Maintenance

```bash
# Watch live logs
journalctl -u levesia -f

# Restart after config change
systemctl restart levesia

# Manually clean old files (or: !skill run disk-cleanup)
find /home/levesia/workspace -mtime +7 -exec rm -rf {} +
find /home/levesia/output -name "*.zip" -mtime +7 -delete

# Update bot files after changes
cp -r /tmp/levesia/bot /home/levesia/
systemctl restart levesia
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `discord.py` | Discord bot framework |
| `aiohttp` | Async HTTP (Groq API + DuckDuckGo) |
| `pyyaml` | Config + skill front-matter parsing |
| `groq` | Groq SDK (optional — also uses raw aiohttp) |
| `python-dotenv` | `.env` support in generated code |

---

*Levesia is built on the Hermes Agent System Prompt Blueprint.*
*Groq free tier: 30 req/min, 14,400 req/day — more than enough for personal use.*

---

*Built By ZenDevelopment - https://www.zendevelopment.in*
