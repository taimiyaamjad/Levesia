"""
cogs/skills.py — Hermes-style agentic skill runner.
Skills are .sh scripts with YAML front-matter in /home/levesia/skills/.
AI can generate new skills on demand via !skill create.
Commands: !skill list, !skill run, !skill show, !skill create, !skill delete
"""

import asyncio, logging, re
import discord
from discord.ext import commands
from pathlib import Path
import yaml, aiohttp

with open(Path(__file__).parent.parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

OWNER_ID   = int(CONFIG["bot"]["owner_id"])
SKILLS_DIR = Path(CONFIG["paths"]["skills"])
TIMEOUT    = CONFIG["execution"]["timeout_seconds"]
GROQ_KEY   = CONFIG["groq"]["api_key"]
MODEL      = CONFIG["groq"]["model"]
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
log        = logging.getLogger("levesia.skills")

SKILL_GEN_SYSTEM = """You are Levesia, a pragmatic senior Linux engineer.
Generate a bash skill script with YAML front-matter. Respond with ONLY the script — no markdown fences.

Format:
---
name: skill-name
description: What this skill does in one sentence
safe: true
tags: [tag1, tag2]
---
#!/bin/bash
set -euo pipefail
# ... rest of script

Rules:
- Script must be safe to run on Ubuntu 22/24
- set -euo pipefail at the top always
- Echo progress messages so the user knows what's happening
- Never delete system files or escalate privileges
- If the skill could be destructive, echo a clear WARNING first
- Use only standard Ubuntu packages (apt, curl, systemctl, etc.)"""


def owner_only():
    async def predicate(ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.message.add_reaction("🔒")
            return False
        return True
    return commands.check(predicate)


def load_skill(name: str) -> dict | None:
    """Load skill from .sh file. Returns {meta, script} or None."""
    path = SKILLS_DIR / f"{name}.sh"
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    meta = {"name": name, "description": "No description.", "safe": True, "tags": []}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta.update(yaml.safe_load(parts[1]) or {})
                content = parts[2].strip()
            except Exception:
                pass
    return {"meta": meta, "script": content}


def list_skills() -> list[dict]:
    """List all skill names + metadata."""
    results = []
    for path in sorted(SKILLS_DIR.glob("*.sh")):
        data = load_skill(path.stem)
        if data:
            results.append(data["meta"])
    return results


async def run_skill_script(script: str, args: str = "") -> tuple[int, str]:
    cmd = f"bash -c {repr(script + ' ' + args)}"
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        return proc.returncode, stdout.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, f"[TIMEOUT] Skill exceeded {TIMEOUT}s."


async def groq_generate_skill(name: str, description: str) -> str:
    """Ask Groq to generate a skill script."""
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 2048,
        "messages": [
            {"role": "system", "content": SKILL_GEN_SYSTEM},
            {"role": "user",   "content":
                f"Create a skill named '{name}' that does the following:\n{description}\n\n"
                f"Remember: YAML front-matter first, then #!/bin/bash. No markdown fences."},
        ],
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_URL, headers=headers, json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            data = await resp.json()

    if "error" in data:
        raise ValueError(f"Groq error: {data['error'].get('message', str(data['error']))}")

    raw = data["choices"][0]["message"]["content"].strip()
    # Strip markdown fences if Groq added them
    raw = re.sub(r"^```(?:bash|sh)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


class Skills(commands.Cog):
    """Hermes-style agentic skill runner."""

    def __init__(self, bot):
        self.bot = bot
        SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    # ── !skill (base) ──────────────────────────────────────────────────────────

    @commands.group(name="skill", invoke_without_command=True)
    @owner_only()
    async def skill(self, ctx):
        """Hermes-style skill system. Subcommands: list, run, show, create, delete"""
        embed = discord.Embed(
            title="🔧 Skill Commands",
            description=(
                "`!skill list` — List all skills\n"
                "`!skill run <name> [args]` — Execute a skill\n"
                "`!skill show <name>` — View a skill's source\n"
                "`!skill create <name> <description>` — AI-generate a new skill\n"
                "`!skill delete <name>` — Delete a skill\n"
            ),
            color=discord.Color.gold(),
        )
        await ctx.send(embed=embed)

    # ── !skill list ────────────────────────────────────────────────────────────

    @skill.command(name="list")
    @owner_only()
    async def skill_list(self, ctx):
        """List all available skills with descriptions and tags."""
        skills = list_skills()
        if not skills:
            await ctx.send(f"📭 No skills found in `{SKILLS_DIR}`. Use `!skill create` to make one.")
            return

        embed = discord.Embed(
            title=f"🔧 Skills ({len(skills)} total)",
            color=discord.Color.gold(),
        )
        for s in skills:
            tags  = ", ".join(s.get("tags", [])) or "none"
            safe  = "✅ safe" if s.get("safe") else "⚠️ destructive"
            embed.add_field(
                name=f"`{s['name']}`",
                value=f"{s['description']}\n`tags: {tags}` | `{safe}`",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── !skill run ─────────────────────────────────────────────────────────────

    @skill.command(name="run")
    @owner_only()
    async def skill_run(self, ctx, name: str, *, args: str = ""):
        """Run a skill by name.
        Usage: !skill run server-health
               !skill run disk-cleanup"""
        data = load_skill(name)
        if not data:
            await ctx.send(f"❌ Skill `{name}` not found. Use `!skill list` to see all skills.")
            return

        meta   = data["meta"]
        script = data["script"]

        # Warn on destructive skills
        if not meta.get("safe", True):
            confirm = await ctx.send(
                f"⚠️ Skill `{name}` is marked **destructive**. "
                f"Reply `yes` within 15s to confirm."
            )
            def check(m):
                return m.author.id == OWNER_ID and m.channel == ctx.channel
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=15)
                if msg.content.strip().lower() != "yes":
                    await confirm.edit(content="❌ Cancelled.")
                    return
            except asyncio.TimeoutError:
                await confirm.edit(content="❌ Timed out — skill not run.")
                return

        async with ctx.typing():
            status = await ctx.send(f"▶️ Running skill `{name}`...")
            rc, out = await run_skill_script(script, args)

        await status.delete()

        color  = discord.Color.green() if rc == 0 else discord.Color.red()
        icon   = "✅" if rc == 0 else "❌"
        chunks = [out[i:i+900] for i in range(0, min(len(out), 1800), 900)] or ["(no output)"]

        embed = discord.Embed(
            title=f"{icon} Skill: {name}",
            description=meta.get("description", ""),
            color=color,
        )
        embed.add_field(name="Exit Code", value=f"`{rc}`", inline=True)
        for j, chunk in enumerate(chunks[:2]):
            embed.add_field(
                name="Output" if j == 0 else "Output (cont.)",
                value=f"```\n{chunk}\n```",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── !skill show ────────────────────────────────────────────────────────────

    @skill.command(name="show")
    @owner_only()
    async def skill_show(self, ctx, name: str):
        """Show a skill's source script.
        Usage: !skill show server-health"""
        data = load_skill(name)
        if not data:
            await ctx.send(f"❌ Skill `{name}` not found.")
            return

        meta   = data["meta"]
        script = data["script"][:1700]

        embed = discord.Embed(
            title=f"📄 Skill: {name}",
            description=f"**{meta['description']}**",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Source", value=f"```bash\n{script}\n```", inline=False)
        tags = ", ".join(meta.get("tags", [])) or "none"
        embed.set_footer(text=f"tags: {tags} | safe: {meta.get('safe', True)}")
        await ctx.send(embed=embed)

    # ── !skill create ──────────────────────────────────────────────────────────

    @skill.command(name="create")
    @owner_only()
    async def skill_create(self, ctx, name: str, *, description: str):
        """AI-generate a new Hermes-style skill and save it.
        Usage: !skill create check-ssl Check SSL cert expiry for a domain
               !skill create restart-nginx Restart nginx and tail the error log"""
        # Sanitize name
        name = re.sub(r"[^a-z0-9\-]", "", name.lower())
        if not name:
            await ctx.send("❌ Invalid skill name. Use lowercase letters, numbers, and hyphens only.")
            return

        skill_path = SKILLS_DIR / f"{name}.sh"
        if skill_path.exists():
            await ctx.send(f"❌ Skill `{name}` already exists. Delete it first with `!skill delete {name}`.")
            return

        async with ctx.typing():
            status = await ctx.send(f"🧠 Generating skill `{name}` with Groq...")
            try:
                script_content = await groq_generate_skill(name, description)
            except Exception as e:
                await status.edit(content=f"❌ Groq error: `{e}`")
                return

        # Save to disk
        skill_path.write_text(script_content, encoding="utf-8")
        skill_path.chmod(0o755)
        await status.delete()

        # Verify it parsed correctly
        data = load_skill(name)
        meta = data["meta"] if data else {"name": name, "description": description}

        embed = discord.Embed(
            title=f"✅ Skill Created: `{name}`",
            description=meta.get("description", description),
            color=discord.Color.green(),
        )
        preview = script_content[:800]
        embed.add_field(name="Preview", value=f"```bash\n{preview}\n```", inline=False)
        embed.set_footer(text=f"Run with: !skill run {name}")
        await ctx.send(embed=embed)

    # ── !skill delete ──────────────────────────────────────────────────────────

    @skill.command(name="delete")
    @owner_only()
    async def skill_delete(self, ctx, name: str):
        """Delete a skill permanently.
        Usage: !skill delete old-skill-name"""
        skill_path = SKILLS_DIR / f"{name}.sh"
        if not skill_path.exists():
            await ctx.send(f"❌ Skill `{name}` not found.")
            return

        confirm = await ctx.send(f"⚠️ Delete skill `{name}` permanently? Reply `yes` within 15s.")
        def check(m):
            return m.author.id == OWNER_ID and m.channel == ctx.channel
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=15)
            if msg.content.strip().lower() != "yes":
                await confirm.edit(content="❌ Cancelled.")
                return
        except asyncio.TimeoutError:
            await confirm.edit(content="❌ Timed out.")
            return

        skill_path.unlink()
        await confirm.edit(content=f"🗑️ Skill `{name}` deleted.")


async def setup(bot):
    await bot.add_cog(Skills(bot))
