"""
FIFA World Cup 2026 Discord Bot
- Polls live match data from football-data.org (free tier)
- Posts updates to a configured channel
- Pings @WorldCup-Fan role for key events
- Slash commands: /schedule /live /standings /subscribe /unsubscribe
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import os
from datetime import datetime, timezone

DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
FOOTBALL_API_KEY   = os.getenv("FOOTBALL_API_KEY")
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", "0"))
ALERT_ROLE_NAME    = os.getenv("ALERT_ROLE_NAME", "WorldCup-Fan")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL", "60"))

WC_COMPETITION_ID  = "WC"
BASE_URL           = "https://api.football-data.org/v4"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
seen_events = {}


async def fetch(session, endpoint):
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[API] {resp.status} on {endpoint}")
            return None
    except Exception as e:
        print(f"[API ERROR] {e}")
        return None


def get_alert_role(guild):
    return discord.utils.get(guild.roles, name=ALERT_ROLE_NAME)


def match_embed(match, title, color):
    home = match["homeTeam"]["name"]
    away = match["awayTeam"]["name"]
    score = match.get("score", {})
    ft = score.get("fullTime", {})
    ht = score.get("halfTime", {})
    h_goals = ft.get("home", "?")
    a_goals = ft.get("away", "?")
    status = match.get("status", "")
    minute = match.get("minute", "")
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Match", value=f"**{home}** vs **{away}**", inline=False)
    embed.add_field(name="Score", value=f"{h_goals} - {a_goals}", inline=True)
    if ht.get("home") is not None:
        embed.add_field(name="Half-Time", value=f"{ht['home']} - {ht['away']}", inline=True)
    embed.add_field(name="Status", value=f"{status}" + (f" ({minute}')" if minute else ""), inline=True)
    utc_date = match.get("utcDate", "")
    if utc_date:
        embed.set_footer(text=f"Kick-off: {utc_date[:16].replace('T', ' ')} UTC")
    return embed


@tasks.loop(seconds=POLL_INTERVAL)
async def poll_live_matches():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel is None:
        return
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/matches?status=LIVE")
        if not data:
            return
        matches = data.get("matches", [])
        for match in matches:
            mid = match["id"]
            if mid not in seen_events:
                seen_events[mid] = set()
            home = match["homeTeam"]["name"]
            away = match["awayTeam"]["name"]
            score = match.get("score", {})
            ft = score.get("fullTime", {})
            h, a = ft.get("home", 0) or 0, ft.get("away", 0) or 0
            status = match.get("status", "")

            start_key = f"started_{mid}"
            if status == "IN_PLAY" and start_key not in seen_events[mid]:
                seen_events[mid].add(start_key)
                role = get_alert_role(channel.guild)
                ping = role.mention if role else ""
                embed = match_embed(match, "Match Started!", discord.Color.green())
                await channel.send(f"{ping} A World Cup 2026 match has kicked off!", embed=embed)

            score_key = f"score_{h}_{a}"
            if score_key not in seen_events[mid] and (h > 0 or a > 0):
                seen_events[mid].add(score_key)
                role = get_alert_role(channel.guild)
                ping = role.mention if role else ""
                embed = match_embed(match, "GOAL!", discord.Color.gold())
                await channel.send(f"{ping} **GOAL!** {home} {h}-{a} {away}", embed=embed)

            ht_key = f"halftime_{mid}"
            if status == "PAUSED" and ht_key not in seen_events[mid]:
                seen_events[mid].add(ht_key)
                embed = match_embed(match, "Half-Time", discord.Color.blue())
                await channel.send(embed=embed)

            for end_status, label in [
                ("FINISHED", "Full-Time"),
                ("EXTRA_TIME", "Extra Time"),
                ("PENALTY_SHOOTOUT", "Penalties!"),
            ]:
                key = f"{end_status}_{mid}"
                if status == end_status and key not in seen_events[mid]:
                    seen_events[mid].add(key)
                    role = get_alert_role(channel.guild)
                    ping = role.mention if role else ""
                    color = discord.Color.red() if end_status == "FINISHED" else discord.Color.orange()
                    embed = match_embed(match, label, color)
                    await channel.send(f"{ping}", embed=embed)

        upcoming = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/matches?status=SCHEDULED")
        if upcoming:
            now = datetime.now(timezone.utc)
            for match in upcoming.get("matches", []):
                mid = match["id"]
                utc_date = match.get("utcDate")
                if not utc_date:
                    continue
                kick_off = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
                delta_min = (kick_off - now).total_seconds() / 60
                reminder_key = f"reminder_30_{mid}"
                if 28 <= delta_min <= 32:
                    if mid not in seen_events:
                        seen_events[mid] = set()
                    if reminder_key not in seen_events[mid]:
                        seen_events[mid].add(reminder_key)
                        role = get_alert_role(channel.guild)
                        ping = role.mention if role else ""
                        embed = match_embed(match, "Match in 30 Minutes!", discord.Color.teal())
                        await channel.send(f"{ping} Heads-up! A match kicks off in ~30 minutes.", embed=embed)


@tree.command(name="live", description="Show currently live World Cup matches")
async def cmd_live(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/matches?status=LIVE")
    if not data or not data.get("matches"):
        await interaction.followup.send("No matches live right now.")
        return
    embeds = [match_embed(m, "LIVE", discord.Color.red()) for m in data["matches"][:5]]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="schedule", description="Show upcoming World Cup matches")
async def cmd_schedule(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/matches?status=SCHEDULED")
    if not data or not data.get("matches"):
        await interaction.followup.send("No upcoming matches found.")
        return
    matches = sorted(data["matches"], key=lambda m: m.get("utcDate", ""))[:5]
    embeds = [match_embed(m, "Upcoming", discord.Color.blue()) for m in matches]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="standings", description="Show World Cup group standings")
async def cmd_standings(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/standings")
    if not data:
        await interaction.followup.send("Standings not available yet.")
        return
    standings = data.get("standings", [])
    embed = discord.Embed(title="FIFA World Cup 2026 Standings", color=discord.Color.gold())
    for group in standings[:8]:
        group_name = group.get("group", group.get("stage", "Group"))
        rows = []
        for t in group.get("table", []):
            rows.append(f"{t['position']}. {t['team']['name'][:20]} - {t['points']}pts (GD {t['goalDifference']:+})")
        if rows:
            embed.add_field(name=group_name, value="\n".join(rows), inline=False)
    await interaction.followup.send(embed=embed)


@tree.command(name="results", description="Show most recent World Cup results")
async def cmd_results(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch(session, f"/competitions/{WC_COMPETITION_ID}/matches?status=FINISHED")
    if not data or not data.get("matches"):
        await interaction.followup.send("No finished matches yet.")
        return
    matches = sorted(data["matches"], key=lambda m: m.get("utcDate", ""), reverse=True)[:5]
    embeds = [match_embed(m, "Result", discord.Color.greyple()) for m in matches]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="subscribe", description="Get the WorldCup-Fan role for match alerts")
async def cmd_subscribe(interaction):
    role = get_alert_role(interaction.guild)
    if role is None:
        await interaction.response.send_message(f"Role {ALERT_ROLE_NAME} not found. Ask an admin to create it.", ephemeral=True)
        return
    member = interaction.guild.get_member(interaction.user.id)
    if role in member.roles:
        await interaction.response.send_message("You are already subscribed!", ephemeral=True)
    else:
        await member.add_roles(role)
        await interaction.response.send_message("Subscribed! You will get pinged for goals, penalties and more.", ephemeral=True)


@tree.command(name="unsubscribe", description="Remove the WorldCup-Fan role (stop alerts)")
async def cmd_unsubscribe(interaction):
    role = get_alert_role(interaction.guild)
    if role is None:
        await interaction.response.send_message(f"Role {ALERT_ROLE_NAME} not found.", ephemeral=True)
        return
    member = interaction.guild.get_member(interaction.user.id)
    if role not in member.roles:
        await interaction.response.send_message("You are not subscribed.", ephemeral=True)
    else:
        await member.remove_roles(role)
        await interaction.response.send_message("Unsubscribed. You will no longer get alerts.", ephemeral=True)


@bot.event
async def on_ready():
    await tree.sync()
    print(f"[Bot] Logged in as {bot.user}")
    if UPDATES_CHANNEL_ID and FOOTBALL_API_KEY:
        poll_live_matches.start()
        print(f"[Bot] Polling every {POLL_INTERVAL}s")
    else:
        print("[Bot] WARNING: env vars not set - polling disabled")


bot.run(DISCORD_TOKEN)
