"""
cogs/codegen.py — Code generation via Groq API + execution pipeline.
Commands: !code, !codefile, !run, !langs
"""

import asyncio, json, re, logging
import discord
from discord.ext import commands
from pathlib import Path
import yaml, aiohttp

from executor import generate_and_run, TaskResult

with open(Path(__file__).parent.parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

OWNER_ID   = int(CONFIG["bot"]["owner_id"])
GROQ_KEY   = CONFIG["groq"]["api_key"]
MODEL      = CONFIG["groq"]["model"]
MAX_TOKENS = CONFIG["groq"]["max_tokens"]
LANGS      = list(CONFIG["languages"].keys())
log        = logging.getLogger("levesia.codegen")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are Levesia, a pragmatic senior engineering assistant.
When asked to write code, respond ONLY with a valid JSON object — no markdown fences, no preamble:

{
  "language": "python",
  "files": {
    "main.py": "...full file content...",
    "utils.py": "...full file content...",
    "requirements.txt": "requests"
  },
  "description": "One-sentence summary of what this code does."
}

Rules:
- Always include a runnable entrypoint (main.py, index.js, main.go, etc.)
- Include dependency files if needed (requirements.txt, package.json, go.mod, Cargo.toml)
- Code must run cleanly with zero modification
- No placeholder comments like "# add logic here"
- language must be one of: python, javascript, typescript, go, rust, c, cpp, java, bash, ruby, php
- Raw JSON only — no markdown fences"""


def owner_only():
    async def predicate(ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.message.add_reaction("🔒")
            return False
        return True
    return commands.check(predicate)


async def call_groq(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """Call Groq API and return raw text response."""
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            GROQ_URL, headers=headers, json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            data = await resp.json()

    if "error" in data:
        raise ValueError(f"Groq API error: {data['error'].get('message', data['error'])}")

    return data["choices"][0]["message"]["content"].strip()


async def call_groq_json(prompt: str) -> dict:
    """Call Groq expecting JSON back. Strips any accidental fences."""
    raw = await call_groq(prompt, SYSTEM_PROMPT)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


async def send_result(ctx, result: TaskResult):
    if result.success:
        preview = result.log_text[-1500:].strip() or "(no output)"
        embed = discord.Embed(
            title="✅ Task Complete",
            description=f"**ID:** `{result.task_id}`\n**Files:** `{', '.join(result.files)}`",
            color=discord.Color.green(),
        )
        embed.add_field(name="Output Preview", value=f"```\n{preview}\n```", inline=False)
        await ctx.send(embed=embed, file=discord.File(result.zip_path))
    else:
        excerpt = (result.log_text or result.error)[-1500:].strip()
        embed = discord.Embed(
            title="❌ Task Failed",
            description=f"**ID:** `{result.task_id}`",
            color=discord.Color.red(),
        )
        embed.add_field(name="Error",    value=f"```\n{result.error}\n```",  inline=False)
        embed.add_field(name="Log tail", value=f"```\n{excerpt[-800:]}\n```", inline=False)
        await ctx.send(embed=embed)


class CodeGen(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="code")
    @owner_only()
    async def code(self, ctx, *, prompt: str):
        """Generate multi-file code, run it, zip it, send it.
        Usage: !code build a FastAPI REST API with /health and /echo"""
        async with ctx.typing():
            status = await ctx.send("🧠 Thinking with Groq...")
            try:
                parsed = await call_groq_json(prompt)
            except json.JSONDecodeError as e:
                await status.edit(content=f"❌ JSON parse error: `{e}`")
                return
            except Exception as e:
                await status.edit(content=f"❌ Groq error: `{e}`")
                return

            files    = parsed.get("files", {})
            lang     = parsed.get("language", "python")
            desc     = parsed.get("description", "")

            if not files:
                await status.edit(content="❌ No files returned by Groq.")
                return

            await status.edit(content=f"📦 Generated **{len(files)} file(s)** in `{lang}` — running...\n> {desc}")
            result = await generate_and_run(files, language=lang)
            await status.delete()
            await send_result(ctx, result)

    @commands.command(name="codefile")
    @owner_only()
    async def codefile(self, ctx, *, prompt: str):
        """Like !code but shows file tree before running.
        Usage: !codefile <prompt>"""
        async with ctx.typing():
            status = await ctx.send("🧠 Thinking with Groq...")
            try:
                parsed = await call_groq_json(prompt)
            except Exception as e:
                await status.edit(content=f"❌ Error: `{e}`")
                return

            files = parsed.get("files", {})
            lang  = parsed.get("language", "python")
            desc  = parsed.get("description", "")

            if not files:
                await status.edit(content="❌ No files returned.")
                return

            tree = "\n".join(f"  📄 {f}" for f in sorted(files.keys()))
            await status.edit(content=(
                f"📦 **{len(files)} file(s)** | `{lang}`\n> {desc}\n"
                f"```\n{tree}\n```\nExecuting..."
            ))
            result = await generate_and_run(files, language=lang)
            await status.delete()
            await send_result(ctx, result)

    @commands.command(name="run")
    @owner_only()
    async def run(self, ctx, language: str, *, code: str):
        """Run an inline code snippet directly.
        Usage: !run python print("hello")
               !run bash echo $(uptime)"""
        if language not in LANGS:
            await ctx.send(f"❌ Unknown language `{language}`. Supported: `{', '.join(LANGS)}`")
            return
        entrypoint = CONFIG["languages"][language]["entrypoint"]
        async with ctx.typing():
            status = await ctx.send(f"▶️ Running `{language}` snippet...")
            result = await generate_and_run({entrypoint: code}, language=language)
            await status.delete()
            await send_result(ctx, result)

    @commands.command(name="langs")
    @owner_only()
    async def langs(self, ctx):
        """List all supported languages."""
        embed = discord.Embed(
            title="🗣️ Supported Languages",
            description="\n".join(f"• `{l}`" for l in LANGS),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CodeGen(bot))
