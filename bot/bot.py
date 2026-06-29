"""
Levesia Discord Bot — Main Entry Point
Owner-only, powered by Groq API + DuckDuckGo search + Hermes-style skills.
"""

import discord
from discord.ext import commands
import yaml
import logging
from pathlib import Path

with open(Path(__file__).parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

OWNER_ID = int(CONFIG["bot"]["owner_id"])
PREFIX   = CONFIG["bot"]["prefix"]
PATHS    = CONFIG["paths"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(f"{PATHS['logs']}/levesia.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("levesia")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    log.info(f"Levesia online as {bot.user} (id={bot.user.id})")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=CONFIG["bot"]["status"],
        )
    )
    for p in PATHS.values():
        Path(p).mkdir(parents=True, exist_ok=True)
    log.info("All directories verified.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return
    if isinstance(error, commands.CommandNotFound):
        return
    log.error(f"Command error [{ctx.command}]: {error}", exc_info=True)
    await ctx.send(f"❌ `{type(error).__name__}: {error}`")


async def main():
    async with bot:
        await bot.load_extension("cogs.codegen")
        await bot.load_extension("cogs.search")
        await bot.load_extension("cogs.skills")
        await bot.load_extension("cogs.system")
        await bot.start(CONFIG["bot"]["token"])


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
