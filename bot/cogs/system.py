"""
cogs/system.py — VPS system monitoring (read-only).
Commands: !status, !disk, !mem, !ps, !logs, !outputs, !help
"""

import asyncio, logging
import discord
from discord.ext import commands
from pathlib import Path
import yaml

with open(Path(__file__).parent.parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

OWNER_ID = int(CONFIG["bot"]["owner_id"])
PATHS    = CONFIG["paths"]
log      = logging.getLogger("levesia.system")


def owner_only():
    async def predicate(ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.message.add_reaction("🔒")
            return False
        return True
    return commands.check(predicate)


async def shell(cmd: str, timeout: int = 10) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return out.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        proc.kill()
        return "[timeout]"


class System(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="status")
    @owner_only()
    async def status(self, ctx):
        """VPS snapshot — uptime, load, memory, disk."""
        uptime = await shell("uptime -p")
        load   = await shell("cat /proc/loadavg | awk '{print $1, $2, $3}'")
        mem    = await shell("free -h | awk '/^Mem:/ {print $3\"/\"$2\" used\"}'")
        disk   = await shell("df -h / | awk 'NR==2 {print $3\"/\"$2\" (\"$5\")'")
        ip     = await shell("hostname -I | awk '{print $1}'")
        embed  = discord.Embed(title="🖥️ VPS Status", color=discord.Color.green())
        embed.add_field(name="Uptime",  value=f"`{uptime}`", inline=False)
        embed.add_field(name="Load",    value=f"`{load}`",   inline=True)
        embed.add_field(name="Memory",  value=f"`{mem}`",    inline=True)
        embed.add_field(name="Disk /",  value=f"`{disk}`",   inline=True)
        embed.add_field(name="IP",      value=f"`{ip}`",     inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="disk")
    @owner_only()
    async def disk(self, ctx):
        """Disk usage for all filesystems."""
        out = await shell("df -h --output=target,used,avail,pcent | column -t")
        await ctx.send(f"```\n{out[:1900]}\n```")

    @commands.command(name="mem")
    @owner_only()
    async def mem(self, ctx):
        """Memory and swap usage."""
        out = await shell("free -h")
        await ctx.send(f"```\n{out}\n```")

    @commands.command(name="ps")
    @owner_only()
    async def ps(self, ctx):
        """Top 15 processes by CPU."""
        out = await shell(
            "ps aux --sort=-%cpu | head -16 | "
            "awk '{printf \"%-20s %5s %5s\\n\", $11, $3, $4}'"
        )
        await ctx.send(f"```\n{out[:1900]}\n```")

    @commands.command(name="logs")
    @owner_only()
    async def logs(self, ctx, lines: int = 30):
        """Last N lines of Levesia log. Usage: !logs [n]"""
        lines = min(lines, 100)
        out   = await shell(f"tail -n {lines} {PATHS['logs']}/levesia.log")
        if not out:
            await ctx.send("📭 Log is empty.")
            return
        for chunk in [out[i:i+1900] for i in range(0, len(out), 1900)]:
            await ctx.send(f"```\n{chunk}\n```")

    @commands.command(name="outputs")
    @owner_only()
    async def outputs(self, ctx):
        """List the 10 most recent zip outputs."""
        output_dir = Path(PATHS["output"])
        zips = sorted(output_dir.glob("*.zip"), key=lambda f: f.stat().st_mtime, reverse=True)[:10]
        if not zips:
            await ctx.send("📭 No output zips found.")
            return
        lines = [f"`{z.name}` — {z.stat().st_size // 1024}KB" for z in zips]
        embed = discord.Embed(title="📦 Recent Outputs", description="\n".join(lines), color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @commands.command(name="help")
    @owner_only()
    async def help_cmd(self, ctx):
        """Show all Levesia commands."""
        embed = discord.Embed(title="⚡ Levesia — Commands", color=discord.Color.gold())
        embed.add_field(name="🧠 Code Gen",
            value=("`!code <prompt>` — Generate + run + zip code\n"
                   "`!codefile <prompt>` — Same + file tree preview\n"
                   "`!run <lang> <code>` — Run inline snippet\n"
                   "`!langs` — Supported languages"), inline=False)
        embed.add_field(name="🔍 Search",
            value=("`!search <query>` — Web search + AI summary\n"
                   "`!ask <question>` — Q&A with web sources"), inline=False)
        embed.add_field(name="🔧 Skills",
            value=("`!skill list` — All skills\n"
                   "`!skill run <name>` — Execute a skill\n"
                   "`!skill show <name>` — View source\n"
                   "`!skill create <name> <desc>` — AI-generate skill\n"
                   "`!skill delete <name>` — Remove skill"), inline=False)
        embed.add_field(name="🖥️ System",
            value=("`!status` — VPS snapshot\n"
                   "`!disk` — Disk usage\n"
                   "`!mem` — Memory\n"
                   "`!ps` — Top processes\n"
                   "`!logs [n]` — Bot log\n"
                   "`!outputs` — Recent zips"), inline=False)
        embed.set_footer(text="All commands are owner-only 🔒")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(System(bot))
