"""
WC2026Bot — Discord bot for FIFA World Cup 2026 + International Friendlies
- Polls live match data from football-data.org (free tier)
- Tracks international friendlies via TheSportsDB (free, no extra key needed)
- Posts updates to a configured channel with @WorldCup-Fan pings
- Slash commands: /live /schedule /standings /results /friendlies /subscribe /unsubscribe
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import os
from datetime import datetime, timezone, timedelta

# ─── CONFIG ─────────────────────────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
FOOTBALL_API_KEY   = os.getenv("FOOTBALL_API_KEY")
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", "0"))
ALERT_ROLE_NAME    = os.getenv("ALERT_ROLE_NAME", "WorldCup-Fan")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL", "60"))

# Comma-separated list of football-data.org competition IDs to track
# WC=World Cup, EC=European Championship, UNL=UEFA Nations League
COMPETITION_IDS    = [c.strip() for c in os.getenv("COMPETITION_IDS", "WC,EC,UNL").split(",")]

# TheSportsDB league ID for international soccer/friendlies (free, no key)
SPORTSDB_LEAGUE    = os.getenv("SPORTSDB_LEAGUE", "4480")

BASE_URL           = "https://api.football-data.org/v4"
SPORTSDB_BASE      = "https://www.thesportsdb.com/api/v1/json/3"

# ─── BOT SETUP ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

seen_events: dict[int | str, set[str]] = {}


# ─── FETCH HELPERS ──────────────────────────────────────────────────────────

async def fetch_fd(session, endpoint):
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[FD API {resp.status}] {endpoint}")
    except Exception as e:
        print(f"[FD ERROR] {e}")
    return None


async def fetch_sportsdb(session, endpoint):
    url = f"{SPORTSDB_BASE}/{endpoint}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        print(f"[SportsDB ERROR] {e}")
    return None


def get_alert_role(guild):
    return discord.utils.get(guild.roles, name=ALERT_ROLE_NAME)


# ─── EMBED BUILDERS ─────────────────────────────────────────────────────────

def match_embed(match, title, color):
    home  = match["homeTeam"]["name"]
    away  = match["awayTeam"]["name"]
    score = match.get("score", {})
    ft    = score.get("fullTime", {})
    ht    = score.get("halfTime", {})
    h_g   = ft.get("home", "?")
    a_g   = ft.get("away", "?")
    status  = match.get("status", "")
    minute  = match.get("minute", "")
    comp    = match.get("competition", {}).get("name", "")
    utc_d   = match.get("utcDate", "")
    embed = discord.Embed(title=title, color=color)
    if comp:
        embed.description = f"*{comp}*"
    embed.add_field(name="Match",  value=f"**{home}** vs **{away}**", inline=False)
    embed.add_field(name="Score",  value=f"{h_g} - {a_g}", inline=True)
    if ht.get("home") is not None:
        embed.add_field(name="HT Score", value=f"{ht['home']} - {ht['away']}", inline=True)
    status_txt = status + (f" {minute}'" if minute else "")
    embed.add_field(name="Status", value=status_txt, inline=True)
    if utc_d:
        embed.set_footer(text=f"Kick-off: {utc_d[:16].replace('T',' ')} UTC")
    return embed


def friendly_embed(event, title, color):
    home    = event.get("strHomeTeam", "?")
    away    = event.get("strAwayTeam", "?")
    h_score = event.get("intHomeScore")
    a_score = event.get("intAwayScore")
    date    = event.get("dateEvent", "")
    time_s  = event.get("strTime", "")
    league  = event.get("strLeague", "International Friendly")
    embed = discord.Embed(title=title, color=color)
    embed.description = f"*{league}*"
    embed.add_field(name="Match", value=f"**{home}** vs **{away}**", inline=False)
    if h_score is not None and a_score is not None:
        embed.add_field(name="Score", value=f"{h_score} - {a_score}", inline=True)
    footer = f"{date}  {time_s} UTC".strip() if date else ""
    if footer:
        embed.set_footer(text=footer)
    return embed


# ─── LIVE MATCH POLLING (football-data.org) ─────────────────────────────────

@tasks.loop(seconds=POLL_INTERVAL)
async def poll_live_matches():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel is None:
        return
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
            if data:
                for match in data.get("matches", []):
                    await handle_live_match(channel, match)
            upcoming = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=SCHEDULED")
            if upcoming:
                for match in upcoming.get("matches", []):
                    await handle_reminder(channel, match)


async def handle_live_match(channel, match):
    mid = match["id"]
    if mid not in seen_events:
        seen_events[mid] = set()
    home   = match["homeTeam"]["name"]
    away   = match["awayTeam"]["name"]
    score  = match.get("score", {})
    ft     = score.get("fullTime", {})
    h, a   = (ft.get("home") or 0), (ft.get("away") or 0)
    status = match.get("status", "")
    role = get_alert_role(channel.guild)
    ping = role.mention if role else ""
    if status == "IN_PLAY" and "started" not in seen_events[mid]:
        seen_events[mid].add("started")
        await channel.send(f"{ping} Match just kicked off!",
                           embed=match_embed(match, "Match Started!", discord.Color.green()))
    score_key = f"score_{h}_{a}"
    if score_key not in seen_events[mid] and (h + a) > 0:
        seen_events[mid].add(score_key)
        await channel.send(f"{ping} **GOAL!** {home} {h}-{a} {away}",
                           embed=match_embed(match, "GOAL!", discord.Color.gold()))
    if status == "PAUSED" and "halftime" not in seen_events[mid]:
        seen_events[mid].add("halftime")
        await channel.send(embed=match_embed(match, "Half-Time", discord.Color.blue()))
    for st, label, color in [
        ("FINISHED",         "Full-Time",         discord.Color.red()),
        ("EXTRA_TIME",       "Extra Time",         discord.Color.orange()),
        ("PENALTY_SHOOTOUT", "Penalty Shootout!",  discord.Color.purple()),
    ]:
        if status == st and st not in seen_events[mid]:
            seen_events[mid].add(st)
            await channel.send(f"{ping}", embed=match_embed(match, label, color))


async def handle_reminder(channel, match):
    mid      = match["id"]
    utc_date = match.get("utcDate")
    if not utc_date:
        return
    if mid not in seen_events:
        seen_events[mid] = set()
    kick_off  = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
    delta_min = (kick_off - datetime.now(timezone.utc)).total_seconds() / 60
    if 28 <= delta_min <= 32 and "reminder_30" not in seen_events[mid]:
        seen_events[mid].add("reminder_30")
        role = get_alert_role(channel.guild)
        ping = role.mention if role else ""
        await channel.send(f"{ping} A match kicks off in ~30 minutes!",
                           embed=match_embed(match, "Match in 30 Minutes!", discord.Color.teal()))


# ─── INTERNATIONAL FRIENDLIES POLLING (TheSportsDB) ─────────────────────────

@tasks.loop(seconds=POLL_INTERVAL * 5)
async def poll_friendlies():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel is None:
        return
    async with aiohttp.ClientSession() as session:
        now = datetime.now(timezone.utc)
        upcoming = await fetch_sportsdb(session, f"eventsnextleague.php?id={SPORTSDB_LEAGUE}")
        if upcoming and upcoming.get("events"):
            for event in upcoming["events"]:
                eid = event.get("idEvent", "")
                if not eid:
                    continue
                if eid not in seen_events:
                    seen_events[eid] = set()
                date_str = event.get("dateEvent", "")
                time_str = event.get("strTime", "")
                if date_str and time_str:
                    try:
                        kick_off  = datetime.fromisoformat(f"{date_str}T{time_str}+00:00")
                        delta_min = (kick_off - now).total_seconds() / 60
                        if 28 <= delta_min <= 32 and "reminder_30" not in seen_events[eid]:
                            seen_events[eid].add("reminder_30")
                            role = get_alert_role(channel.guild)
                            ping = role.mention if role else ""
                            await channel.send(
                                f"{ping} International friendly kicks off in ~30 minutes!",
                                embed=friendly_embed(event, "Friendly in 30 Minutes!", discord.Color.teal()))
                    except Exception:
                        pass
        past = await fetch_sportsdb(session, f"eventslastleague.php?id={SPORTSDB_LEAGUE}")
        if past and past.get("events"):
            for event in past["events"]:
                eid = event.get("idEvent", "")
                if not eid:
                    continue
                if eid not in seen_events:
                    seen_events[eid] = set()
                if event.get("strStatus") == "Match Finished" and "finished" not in seen_events[eid]:
                    seen_events[eid].add("finished")
                    await channel.send(
                        embed=friendly_embed(event, "Friendly - Full Time", discord.Color.greyple()))


# ─── SLASH COMMANDS ─────────────────────────────────────────────────────────

@tree.command(name="live", description="Show currently live international matches")
async def cmd_live(interaction):
    await interaction.response.defer()
    embeds = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
            if data:
                for m in data.get("matches", [])[:3]:
                    embeds.append(match_embed(m, "LIVE", discord.Color.red()))
    if not embeds:
        await interaction.followup.send("No matches live right now. Check /schedule for upcoming matches.")
    else:
        await interaction.followup.send(embeds=embeds[:10])


@tree.command(name="schedule", description="Show upcoming matches (World Cup, Euros, Nations League)")
async def cmd_schedule(interaction):
    await interaction.response.defer()
    all_matches = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=SCHEDULED")
            if data:
                all_matches.extend(data.get("matches", []))
    if not all_matches:
        await interaction.followup.send("No upcoming matches found.")
        return
    all_matches.sort(key=lambda m: m.get("utcDate", ""))
    embeds = [match_embed(m, "Upcoming", discord.Color.blue()) for m in all_matches[:5]]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="friendlies", description="Show upcoming international friendlies")
async def cmd_friendlies(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch_sportsdb(session, f"eventsnextleague.php?id={SPORTSDB_LEAGUE}")
    if not data or not data.get("events"):
        await interaction.followup.send("No upcoming international friendlies found right now.")
        return
    embeds = [friendly_embed(e, "Upcoming Friendly", discord.Color.purple())
              for e in data["events"][:5]]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="standings", description="Show World Cup 2026 group standings")
async def cmd_standings(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch_fd(session, "/competitions/WC/standings")
    if not data or not data.get("standings"):
        await interaction.followup.send("Standings not available yet - tournament hasn't started!")
        return
    embed = discord.Embed(title="FIFA World Cup 2026 - Standings", color=discord.Color.gold())
    for group in data["standings"][:8]:
        name = group.get("group") or group.get("stage", "Group")
        rows = [
            f"{t['position']}. {t['team']['name'][:20]}  {t['points']}pts  GD{t['goalDifference']:+}"
            for t in group.get("table", [])
        ]
        if rows:
            embed.add_field(name=name, value="\n".join(rows), inline=False)
    await interaction.followup.send(embed=embed)


@tree.command(name="results", description="Show most recent match results")
async def cmd_results(interaction):
    await interaction.response.defer()
    all_matches = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=FINISHED")
            if data:
                all_matches.extend(data.get("matches", []))
    if not all_matches:
        await interaction.followup.send("No finished matches yet.")
        return
    all_matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
    embeds = [match_embed(m, "Result", discord.Color.greyple()) for m in all_matches[:5]]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="subscribe", description="Get the WorldCup-Fan role to receive match alerts")
async def cmd_subscribe(interaction):
    role = get_alert_role(interaction.guild)
    if role is None:
        await interaction.response.send_message(
            f"Role {ALERT_ROLE_NAME} not found in this server.", ephemeral=True)
        return
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        await interaction.response.send_message("Could not find your member record.", ephemeral=True)
        return
    if role in member.roles:
        await interaction.response.send_message("You are already subscribed!", ephemeral=True)
    else:
        await member.add_roles(role, reason="WC2026Bot /subscribe")
        await interaction.response.send_message(
            "Subscribed! You will be pinged for goals, half-time, full-time and more.", ephemeral=True)


@tree.command(name="unsubscribe", description="Remove the WorldCup-Fan role (stop alerts)")
async def cmd_unsubscribe(interaction):
    role = get_alert_role(interaction.guild)
    if role is None:
        await interaction.response.send_message(
            f"Role {ALERT_ROLE_NAME} not found.", ephemeral=True)
        return
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        await interaction.response.send_message("Could not find your member record.", ephemeral=True)
        return
    if role not in member.roles:
        await interaction.response.send_message("You don't have the role - nothing to remove.", ephemeral=True)
    else:
        await member.remove_roles(role, reason="WC2026Bot /unsubscribe")
        await interaction.response.send_message("Unsubscribed. You won't get pinged anymore.", ephemeral=True)


# ─── PREFIX COMMAND FALLBACK ─────────────────────────────────────────────────

@bot.command(name="subscribe")
async def prefix_subscribe(ctx):
    role = get_alert_role(ctx.guild)
    if role is None:
        await ctx.reply(f"Role {ALERT_ROLE_NAME} not found.")
        return
    if role in ctx.author.roles:
        await ctx.reply("You are already subscribed!")
    else:
        await ctx.author.add_roles(role)
        await ctx.reply("Subscribed! You will be pinged for goals and match updates.")


@bot.command(name="unsubscribe")
async def prefix_unsubscribe(ctx):
    role = get_alert_role(ctx.guild)
    if role is None:
        await ctx.reply(f"Role {ALERT_ROLE_NAME} not found.")
        return
    if role not in ctx.author.roles:
        await ctx.reply("You don't have the role.")
    else:
        await ctx.author.remove_roles(role)
        await ctx.reply("Unsubscribed.")


# ─── STARTUP ─────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")
    synced_guilds = []
    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            synced_guilds.append(guild.name)
        except Exception as e:
            print(f"[Sync ERROR] {guild.name}: {e}")
    print(f"[Bot] Guild-synced to: {', '.join(synced_guilds)}")
    try:
        await tree.sync()
        print("[Bot] Global sync done.")
    except Exception as e:
        print(f"[Bot] Global sync error: {e}")
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel:
        comps = " + ".join(COMPETITION_IDS)
        await channel.send(
            f"**WC2026Bot is online!**\n"
            f"Tracking: **{comps}** + International Friendlies\n"
            f"World Cup kicks off **June 11, 2026**\n\n"
            f"Commands: /schedule - /live - /friendlies - /standings - /results - /subscribe - /unsubscribe\n"
            f"*(Slash commands not showing yet? Type* **!subscribe** *instead)*"
        )
    if UPDATES_CHANNEL_ID and FOOTBALL_API_KEY:
        poll_live_matches.start()
        poll_friendlies.start()
        print(f"[Bot] Polling started - interval: {POLL_INTERVAL}s")
    else:
        print("[Bot] WARNING: env vars not set - polling disabled")


bot.run(DISCORD_TOKEN)
