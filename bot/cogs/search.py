"""
cogs/search.py — Web search via DuckDuckGo + Groq summarization.
No API key required for search. Groq summarizes results.
Commands: !search, !ask
"""

import asyncio, logging, re
import discord
from discord.ext import commands
from pathlib import Path
import yaml, aiohttp
from urllib.parse import quote_plus

with open(Path(__file__).parent.parent.parent / "config" / "config.yaml") as f:
    CONFIG = yaml.safe_load(f)

OWNER_ID    = int(CONFIG["bot"]["owner_id"])
GROQ_KEY    = CONFIG["groq"]["api_key"]
MODEL       = CONFIG["groq"]["model"]
MAX_RESULTS = CONFIG["search"]["max_results"]
GROQ_URL    = "https://api.groq.com/openai/v1/chat/completions"
log         = logging.getLogger("levesia.search")

DDG_URL  = "https://html.duckduckgo.com/html/"
DDG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def owner_only():
    async def predicate(ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.message.add_reaction("🔒")
            return False
        return True
    return commands.check(predicate)


async def duckduckgo_search(query: str, max_results: int = MAX_RESULTS) -> list[dict]:
    """
    Scrape DuckDuckGo HTML search results.
    Returns list of {title, url, snippet} dicts.
    """
    results = []
    params  = {"q": query, "kl": "us-en", "kp": "-1"}

    async with aiohttp.ClientSession(headers=DDG_HEADERS) as session:
        async with session.post(
            DDG_URL, data=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            html = await resp.text()

    # Parse result blocks from DDG HTML
    # Each result: <a class="result__a" href="...">title</a>
    #              <a class="result__snippet">snippet</a>
    title_pattern   = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
    snippet_pattern = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)

    titles   = title_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    def clean(text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;',  '<', text)
        text = re.sub(r'&gt;',  '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#x27;', "'", text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    for i, (url, title) in enumerate(titles[:max_results]):
        snippet = snippets[i][0] if i < len(snippets) else ""
        results.append({
            "title":   clean(title),
            "url":     url,
            "snippet": clean(snippet),
        })

    return results


async def groq_summarize(query: str, results: list[dict], mode: str = "search") -> str:
    """Use Groq to summarize search results into a coherent answer."""
    if not results:
        return "No results found for that query."

    context = "\n\n".join(
        f"[{i+1}] {r['title']}\nURL: {r['url']}\n{r['snippet']}"
        for i, r in enumerate(results)
    )

    if mode == "ask":
        system = (
            "You are Levesia, a precise engineering assistant. "
            "Answer the user's question using the search results provided. "
            "Be concise and technical. Cite sources as [1], [2] etc. "
            "If results don't answer the question, say so directly."
        )
        user_prompt = f"Question: {query}\n\nSearch results:\n{context}"
    else:
        system = (
            "You are Levesia, a precise engineering assistant. "
            "Summarize these web search results clearly and concisely. "
            "Extract the most useful information. Cite sources as [1], [2] etc. "
            "Be direct — no filler."
        )
        user_prompt = f"Query: {query}\n\nResults:\n{context}"

    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_prompt},
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

    return data["choices"][0]["message"]["content"].strip()


def build_search_embed(query: str, summary: str, results: list[dict], mode: str) -> discord.Embed:
    icon  = "🔍" if mode == "search" else "💬"
    title = f"{icon} {'Search' if mode == 'search' else 'Answer'}: {query[:80]}"

    embed = discord.Embed(title=title, color=discord.Color.blurple())

    # Summary (main body — split if too long)
    summary_chunks = [summary[i:i+1020] for i in range(0, min(len(summary), 2040), 1020)]
    for j, chunk in enumerate(summary_chunks[:2]):
        embed.add_field(
            name="📝 Summary" if j == 0 else "📝 (continued)",
            value=chunk,
            inline=False,
        )

    # Sources
    sources = "\n".join(
        f"[{i+1}] [{r['title'][:60]}]({r['url']})"
        for i, r in enumerate(results[:5])
    )
    if sources:
        embed.add_field(name="🔗 Sources", value=sources, inline=False)

    embed.set_footer(text=f"Powered by DuckDuckGo + Groq ({MODEL})")
    return embed


class Search(commands.Cog):
    """Web search + AI summarization."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="search")
    @owner_only()
    async def search(self, ctx, *, query: str):
        """Search the web and get an AI-summarized answer.
        Usage: !search latest Python 3.13 features
               !search nginx reverse proxy setup ubuntu"""
        async with ctx.typing():
            status = await ctx.send(f"🔍 Searching: `{query[:80]}`...")

            try:
                results = await duckduckgo_search(query)
                if not results:
                    await status.edit(content="❌ No results found. Try rephrasing your query.")
                    return

                await status.edit(content=f"🧠 Found {len(results)} results — summarizing with Groq...")
                summary = await groq_summarize(query, results, mode="search")

            except Exception as e:
                log.exception("Search error")
                await status.edit(content=f"❌ Search failed: `{e}`")
                return

            await status.delete()
            embed = build_search_embed(query, summary, results, mode="search")
            await ctx.send(embed=embed)

    @commands.command(name="ask")
    @owner_only()
    async def ask(self, ctx, *, question: str):
        """Ask a question — searches the web and answers with sources.
        Usage: !ask how do I set up a systemd service on Ubuntu?
               !ask what is the difference between TCP and UDP?"""
        async with ctx.typing():
            status = await ctx.send(f"💬 Looking up: `{question[:80]}`...")

            try:
                results = await duckduckgo_search(question)
                if not results:
                    await status.edit(content="❌ Couldn't find relevant results.")
                    return

                await status.edit(content=f"🧠 Found {len(results)} sources — composing answer...")
                answer = await groq_summarize(question, results, mode="ask")

            except Exception as e:
                log.exception("Ask error")
                await status.edit(content=f"❌ Failed: `{e}`")
                return

            await status.delete()
            embed = build_search_embed(question, answer, results, mode="ask")
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Search(bot))
