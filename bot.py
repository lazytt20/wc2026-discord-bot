"""
WC2026Bot — Discord bot for FIFA World Cup 2026 + International Football
- Rich embeds with flag emojis, goal scorers, cards, venue
- IST timestamps, star player highlights, rivalry callouts, match tips
- Auto daily digest at 8:30 AM IST, no subscribe required
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import os
import random
from typing import Optional, List
from datetime import datetime, timezone, timedelta

# ─── CONFIG ─────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
FOOTBALL_API_KEY   = os.getenv("FOOTBALL_API_KEY")
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", "0"))
ALERT_ROLE_NAME    = os.getenv("ALERT_ROLE_NAME", "WorldCup-Fan")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL", "60"))
COMPETITION_IDS    = [c.strip() for c in os.getenv("COMPETITION_IDS", "WC,EC,UNL").split(",")]
SPORTSDB_LEAGUE    = os.getenv("SPORTSDB_LEAGUE", "4480")

BASE_URL      = "https://api.football-data.org/v4"
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"
IST           = timezone(timedelta(hours=5, minutes=30))


def fmt_ist(utc_str: str) -> str:
    if not utc_str:
        return "TBD"
    try:
        dt  = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        ist = dt.astimezone(IST)
        day = str(ist.day)
        return ist.strftime(f"{day} %b, %I:%M %p IST")
    except Exception:
        return utc_str[:16].replace("T", " ") + " UTC"


# ─── FLAG MAP ───────────────────────────────────────────────
FLAGS = {
    "Mexico": "🇲🇽", "United States": "🇺🇸", "USA": "🇺🇸",
    "Canada": "🇨🇦", "Jamaica": "🇯🇲", "Costa Rica": "🇨🇷",
    "Panama": "🇵🇦", "Honduras": "🇭🇳", "El Salvador": "🇸🇻",
    "Guatemala": "🇬🇹", "Trinidad and Tobago": "🇹🇹", "Cuba": "🇨🇺",
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "Colombia": "🇨🇴",
    "Uruguay": "🇺🇾", "Chile": "🇨🇱", "Ecuador": "🇪🇨",
    "Paraguay": "🇵🇾", "Peru": "🇵🇪", "Venezuela": "🇻🇪", "Bolivia": "🇧🇴",
    "Germany": "🇩🇪", "France": "🇫🇷", "Spain": "🇪🇸",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Italy": "🇮🇹", "Portugal": "🇵🇹",
    "Netherlands": "🇳🇱", "Belgium": "🇧🇪", "Croatia": "🇭🇷",
    "Denmark": "🇩🇰", "Switzerland": "🇨🇭", "Sweden": "🇸🇪",
    "Poland": "🇵🇱", "Austria": "🇦🇹", "Serbia": "🇷🇸",
    "Ukraine": "🇺🇦", "Turkey": "🇹🇷", "Czech Republic": "🇨🇿",
    "Czechia": "🇨🇿", "Hungary": "🇭🇺", "Romania": "🇷🇴",
    "Slovakia": "🇸🇰", "Slovenia": "🇸🇮", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Norway": "🇳🇴", "Finland": "🇫🇮",
    "Greece": "🇬🇷", "Iceland": "🇮🇸", "Albania": "🇦🇱",
    "Bosnia and Herzegovina": "🇧🇦", "Bosnia-Herzegovina": "🇧🇦",
    "North Macedonia": "🇲🇰", "Georgia": "🇬🇪",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Australia": "🇦🇺",
    "Saudi Arabia": "🇸🇦", "Qatar": "🇶🇦", "Iran": "🇮🇷",
    "Indonesia": "🇮🇩", "United Arab Emirates": "🇦🇪",
    "Morocco": "🇲🇦", "Senegal": "🇸🇳", "Egypt": "🇪🇬",
    "Nigeria": "🇳🇬", "South Africa": "🇿🇦", "Ghana": "🇬🇭",
    "Cameroon": "🇨🇲", "Ivory Coast": "🇨🇮", "Algeria": "🇩🇿",
    "Tunisia": "🇹🇳", "New Zealand": "🇳🇿",
}

def get_flag(team: str) -> str:
    if team in FLAGS:
        return FLAGS[team]
    for k, v in FLAGS.items():
        if k.lower() in team.lower() or team.lower() in k.lower():
            return v
    return "🏳️"


# ─── STAR PLAYERS ───────────────────────────────────────────────
STARS = {
    "Argentina":   [("Lionel Messi",       "🐐 GOAT"),
                    ("Julián Álvarez",      "🌟")],
    "Portugal":    [("Cristiano Ronaldo",  "👑 CR7"),
                    ("Rafael Leão",         "⚡")],
    "Norway":      [("Erling Haaland",     "🤖 Machine"),
                    ("Martin Ødegaard",    "🎯")],
    "Brazil":      [("Vinicius Jr",        "⚡ Vini Jr"),
                    ("Rodrygo",            "🌟"),
                    ("Neymar Jr",          "🎠")],
    "Egypt":       [("Mohamed Salah",      "🔴 The King")],
    "France":      [("Kylian Mbappé",      "💨"),
                    ("Antoine Griezmann",  "🎯")],
    "England":     [("Harry Kane",         "👑"),
                    ("Jude Bellingham",    "🎸")],
    "Spain":       [("Lamine Yamal",       "✨ Wonder Kid"),
                    ("Pedri",              "🎩")],
    "Germany":     [("Florian Wirtz",      "🎸"),
                    ("Jamal Musiala",      "🕺")],
    "Netherlands": [("Virgil van Dijk",    "🧱"),
                    ("Cody Gakpo",         "⚡")],
    "Belgium":     [("Kevin De Bruyne",    "🎯 KDB"),
                    ("Romelu Lukaku",      "💪")],
    "Croatia":     [("Luka Modrić",        "🪄 Maestro")],
    "Uruguay":     [("Darwin Núñez",       "💥")],
    "Colombia":    [("James Rodríguez",    "🌟"),
                    ("Luis Díaz",          "⚡")],
    "Japan":       [("Takumi Minamino",    "🌟")],
    "Morocco":     [("Achraf Hakimi",      "🚀"),
                    ("Hakim Ziyech",       "🎩")],
    "Senegal":     [("Sadio Mané",         "⚡")],
    "Saudi Arabia":[("Salem Al-Dawsari",   "⚡")],
    "South Korea": [("Son Heung-min",      "🌟 Sonny")],
    "Poland":      [("Robert Lewandowski", "💥 Lewy")],
    "Denmark":     [("Christian Eriksen",  "❤️")],
}

def get_stars(team: str) -> list:
    if team in STARS:
        return STARS[team]
    for k, v in STARS.items():
        if k.lower() in team.lower() or team.lower() in k.lower():
            return v
    return []

def stars_line(team: str) -> Optional[str]:
    s = get_stars(team)
    if not s:
        return None
    return "  •  ".join(f"{tag} {name}" for name, tag in s)


# ─── RIVALRIES ───────────────────────────────────────────────
RIVALRIES = {
    frozenset(["Argentina", "Brazil"]):      ("🔥 EL CLÁSICO DEL SUR",
        "The greatest South American rivalry! 107 meetings. "
        "Argentina leads WC finals h2h 3-2. Messi vs Vinicius — expect fireworks."),
    frozenset(["Argentina", "France"]):      ("👑 WC FINAL REMATCH",
        "Qatar 2022 final replay! Argentina won on penalties after Mbappé's hat-trick. "
        "France want revenge. This will be ELECTRIC."),
    frozenset(["Portugal", "Argentina"]):    ("🐐 GOAT DERBY",
        "Messi vs Ronaldo on the world stage! Both in possibly their last WC. "
        "Messi has the trophy; Ronaldo is still chasing his ultimate dream."),
    frozenset(["Portugal", "France"]):       ("🌟 EURO RIVALS",
        "France leads h2h but Portugal shocked them in Euro 2016 final. "
        "Ronaldo vs Mbappé: two legends, one spotlight."),
    frozenset(["England", "Germany"]):       ("⚔️ OLD ENEMIES",
        "Germany won the 1966 WC final on English soil. "
        "England are still waiting — Germany always find a way."),
    frozenset(["England", "France"]):        ("🦁 100 YEARS WAR CONTINUES",
        "France knocked England out in Qatar 2022 QF. "
        "Bellingham vs Mbappé — a generational subplot."),
    frozenset(["Brazil", "Germany"]):        ("💀 THE 7-1 — MINEIRAZO",
        "Brazil 1-7 Germany. 2014 WC semi. On home soil. "
        "The darkest day in Brazilian football. Brazil haven't forgotten."),
    frozenset(["Spain", "Germany"]):         ("🏆 KINGS vs KAISERS",
        "7 World Cups combined. Spain beat Germany 2010 WC & 2024 Euros. "
        "Tiki-taka vs German efficiency."),
    frozenset(["Brazil", "France"]):         ("🕊️ FLAIR vs EFFICIENCY",
        "France beat Brazil in 1986 & 1998 QF. Zidane's 98 masterclass haunts Brazil. "
        "Vinicius vs Mbappé would be sensational."),
    frozenset(["Netherlands", "Germany"]):   ("🟠 DE KLASSIEKER",
        "One of football's oldest grudge matches. "
        "The Dutch still talk about 1988 Euro redemption."),
    frozenset(["Mexico", "United States"]):  ("🌎 CONCACAF DERBY",
        "CONCACAF's fiercest derby at the World Cup! "
        "Both nations are co-hosts — this fixture is MASSIVE."),
    frozenset(["Italy", "France"]):          ("🍕 vs 🐓",
        "Remember Zidane's headbutt on Materazzi in 2006 final? "
        "Passion, skill and tactical masterclass from both sides."),
}

TIPS = [
    "💡 Watch the first 15 mins — shock goals often happen early in tournaments.",
    "💡 Set piece specialists like Messi & De Bruyne decide tight knockout games.",
    "💡 Look out for underdog upsets — Morocco reached the 2022 WC semi-finals!",
    "💡 Fatigue is real — teams in extra time in R16 often struggle in QF.",
    "💡 The goalkeeper is the X-factor. Tournament runs often start with a heroic GK.",
    "💡 Home continent teams historically over-perform at World Cups.",
    "💡 The first goal in a knockout match wins the tie ~65% of the time.",
    "💡 Watch for late substitutions — some of the biggest WC goals come from subs.",
    "💡 Tournament football is about momentum — the team peaking at the right time wins.",
    "💡 Penalty shootouts are won in training. Germany are historically ice-cold from the spot.",
]

def get_rivalry(home: str, away: str) -> Optional[tuple]:
    for k, v in RIVALRIES.items():
        teams = list(k)
        h_ok = any(t.lower() in home.lower() or home.lower() in t.lower() for t in teams)
        a_ok = any(t.lower() in away.lower() or away.lower() in t.lower() for t in teams)
        if h_ok and a_ok:
            return v
    return None

def get_tip() -> str:
    return random.choice(TIPS)


# ─── BOT SETUP ───────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
seen_events: dict = {}


# ─── FETCH HELPERS ───────────────────────────────────────────────

async def fetch_fd(session: aiohttp.ClientSession, endpoint: str) -> Optional[dict]:
    try:
        url = f"{BASE_URL}{endpoint}"
        headers = {"X-Auth-Token": FOOTBALL_API_KEY}
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                return await r.json()
            print(f"[FD {r.status}] {endpoint}")
    except Exception as e:
        print(f"[FD ERROR] {endpoint}: {e}")
    return None

async def fetch_sportsdb(session: aiohttp.ClientSession, endpoint: str) -> Optional[dict]:
    try:
        async with session.get(
            f"{SPORTSDB_BASE}/{endpoint}",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[SDB ERROR] {e}")
    return None

def get_alert_role(guild):
    return discord.utils.get(guild.roles, name=ALERT_ROLE_NAME)

async def safe_followup(interaction, **kwargs):
    try:
        await interaction.followup.send(**kwargs)
    except Exception as e:
        print(f"[followup error] {e}")
        try:
            await interaction.followup.send("⚠️ Something went wrong. Please try again.")
        except Exception:
            pass
# ─── EMBED BUILDERS ───────────────────────────────────────────

def match_embed(match: dict, title: str, color, show_tips: bool = False) -> discord.Embed:
    home   = (match.get("homeTeam") or {}).get("name", "Home")
    away   = (match.get("awayTeam") or {}).get("name", "Away")
    hf, af = get_flag(home), get_flag(away)
    ft     = match.get("score", {}).get("fullTime", {}) or {}
    ht     = match.get("score", {}).get("halfTime", {}) or {}
    h_g    = ft.get("home")
    a_g    = ft.get("away")
    hs     = str(h_g) if h_g is not None else "–"
    as_    = str(a_g) if a_g is not None else "–"
    status = match.get("status", "")
    minute = match.get("minute")
    comp   = (match.get("competition") or {}).get("name", "")
    utc_d  = match.get("utcDate", "")
    venue  = match.get("venue", "")

    if status in ("TIMED", "SCHEDULED"):
        desc = f"**{hf} {home}**  ⚔️  **{away} {af}**"
    else:
        desc = f"**{hf} {home}**   `{hs} — {as_}`   **{away} {af}**"

    embed = discord.Embed(title=title, description=desc, color=color)
    if comp:
        embed.set_author(name=f"🏆 {comp}")

    if status == "IN_PLAY" and minute:
        embed.add_field(name="⏱️ Time", value=f"**{minute}'**", inline=True)
    if ht.get("home") is not None:
        embed.add_field(name="🔔 HT", value=f"**{ht['home']} – {ht['away']}**", inline=True)
    if venue:
        embed.add_field(name="🏙️ Venue", value=venue, inline=True)

    goals = match.get("goals") or []
    if goals:
        lines = []
        for g in goals:
            m      = g.get("minute", "?")
            scorer = (g.get("scorer") or {}).get("name", "Unknown")
            team   = (g.get("team")   or {}).get("name", "")
            gtype  = g.get("type", "REGULAR")
            side   = "🏠" if team == home else "✈️"
            extra  = " *(pen)*" if gtype == "PENALTY" else " *(og)*" if gtype == "OWN_GOAL" else ""
            lines.append(f"{side} `{m}'`  {scorer}{extra}")
        embed.add_field(name="⚽ Scorers", value="\n".join(lines[:10]), inline=False)

    bookings = match.get("bookings") or []
    if bookings:
        lines = []
        for b in bookings:
            m      = b.get("minute", "?")
            player = (b.get("player") or {}).get("name", "Unknown")
            card   = b.get("card", "YELLOW_CARD")
            team   = (b.get("team")  or {}).get("name", "")
            side   = "🏠" if team == home else "✈️"
            emoji  = "🟥" if "RED" in card else "🟨"
            lines.append(f"{side} {emoji} `{m}'`  {player}")
        embed.add_field(name="📋 Cards", value="\n".join(lines[:8]), inline=False)

    h_stars = stars_line(home)
    a_stars = stars_line(away)
    if h_stars or a_stars:
        parts = []
        if h_stars:
            parts.append(f"🏠 **{home}:** {h_stars}")
        if a_stars:
            parts.append(f"✈️ **{away}:** {a_stars}")
        embed.add_field(name="🌟 Stars to Watch", value="\n".join(parts), inline=False)

    rv = get_rivalry(home, away)
    if rv:
        embed.add_field(name=f"🔥 {rv[0]}", value=rv[1], inline=False)

    if show_tips:
        embed.add_field(name="💡 Match Tip", value=get_tip(), inline=False)

    if utc_d:
        embed.set_footer(text=f"⏰ Kick-off: {fmt_ist(utc_d)}")
    return embed


def friendly_embed(event: dict, title: str, color, show_tips: bool = False) -> discord.Embed:
    home   = event.get("strHomeTeam", "Home")
    away   = event.get("strAwayTeam", "Away")
    hf, af = get_flag(home), get_flag(away)
    hs     = event.get("intHomeScore")
    as_    = event.get("intAwayScore")
    date   = event.get("dateEvent", "")
    time_s = event.get("strTime", "")
    league = event.get("strLeague", "International Friendly")

    if hs is not None and as_ is not None:
        desc = f"**{hf} {home}**   `{hs} — {as_}`   **{away} {af}**"
    else:
        desc = f"**{hf} {home}**  ⚔️  **{away} {af}**"

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_author(name=f"🌍 {league}")

    h_stars = stars_line(home)
    a_stars = stars_line(away)
    if h_stars or a_stars:
        parts = []
        if h_stars:
            parts.append(f"🏠 **{home}:** {h_stars}")
        if a_stars:
            parts.append(f"✈️ **{away}:** {a_stars}")
        embed.add_field(name="🌟 Stars to Watch", value="\n".join(parts), inline=False)

    rv = get_rivalry(home, away)
    if rv:
        embed.add_field(name=f"🔥 {rv[0]}", value=rv[1], inline=False)

    if show_tips:
        embed.add_field(name="💡 Match Tip", value=get_tip(), inline=False)

    if date and time_s:
        embed.set_footer(text=f"⏰ Kick-off: {fmt_ist(date + 'T' + time_s + '+00:00')}")
    elif date:
        embed.set_footer(text=f"📅 {date}")
    return embed


def today_digest_embed(matches: list, label: str) -> discord.Embed:
    now_ist = datetime.now(IST)
    embed   = discord.Embed(
        title=f"📅 {label} — {now_ist.strftime('%d %b %Y')}",
        color=discord.Color.gold()
    )
    for m in matches[:12]:
        home = (m.get("homeTeam") or {}).get("name", "?")
        away = (m.get("awayTeam") or {}).get("name", "?")
        hf, af = get_flag(home), get_flag(away)
        ko  = fmt_ist(m.get("utcDate", ""))
        val = f"⏰ **{ko}**"
        sh, sa = stars_line(home), stars_line(away)
        if sh or sa:
            val += "\n🌟 " + (sh or "") + (" | " + sa if sa else "")
        rv = get_rivalry(home, away)
        if rv:
            val += f"\n🔥 *{rv[0]}*"
        embed.add_field(name=f"{hf} {home}  vs  {away} {af}", value=val, inline=False)
    embed.set_footer(text="⏰ All times in IST  •  /live for scores  •  /results for yesterday")
    return embed


# ─── POLLING TASKS ───────────────────────────────────────────────

@tasks.loop(seconds=POLL_INTERVAL)
async def poll_live_matches():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if not channel:
        return
    try:
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                live = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
                if live:
                    for m in live.get("matches", []):
                        await handle_live_match(channel, m, session)
                sched = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=SCHEDULED")
                if sched:
                    for m in sched.get("matches", []):
                        await handle_reminder(channel, m)
    except Exception as e:
        print(f"[poll error] {e}")


async def handle_live_match(channel, match, session):
    mid    = match["id"]
    status = match.get("status", "")
    ft     = match.get("score", {}).get("fullTime", {}) or {}
    h, a   = (ft.get("home") or 0), (ft.get("away") or 0)
    seen_events.setdefault(mid, set())

    async def rich():
        full = await fetch_fd(session, f"/matches/{mid}")
        return full if full else match

    try:
        if status == "IN_PLAY" and "started" not in seen_events[mid]:
            seen_events[mid].add("started")
            full = await rich()
            await channel.send(embed=match_embed(full, "⚽ Match Kicked Off!", discord.Color.green()))

        score_key = f"score_{h}_{a}"
        if score_key not in seen_events[mid] and (h + a) > 0:
            seen_events[mid].add(score_key)
            full = await rich()
            hn = (full.get("homeTeam") or {}).get("name", "Home")
            an = (full.get("awayTeam") or {}).get("name", "Away")
            await channel.send(
                f"**GOAAAAL!**  {get_flag(hn)} **{hn}** `{h} – {a}` **{an}** {get_flag(an)}",
                embed=match_embed(full, "🚨 GOAL!", discord.Color.gold()))

        if status == "PAUSED" and "halftime" not in seen_events[mid]:
            seen_events[mid].add("halftime")
            full = await rich()
            await channel.send(embed=match_embed(full, "⏸️ Half-Time", discord.Color.blue()))

        for st, ttl, clr in [
            ("FINISHED",         "🏁 Full-Time",          discord.Color.red()),
            ("EXTRA_TIME",       "⏱️ Extra Time Begins",   discord.Color.orange()),
            ("PENALTY_SHOOTOUT", "🎯 Penalty Shootout!",  discord.Color.purple()),
        ]:
            if status == st and st not in seen_events[mid]:
                seen_events[mid].add(st)
                full = await rich()
                await channel.send(embed=match_embed(full, ttl, clr))
    except Exception as e:
        print(f"[live match error] mid={mid}: {e}")


async def handle_reminder(channel, match):
    try:
        mid      = match["id"]
        utc_date = match.get("utcDate")
        if not utc_date:
            return
        seen_events.setdefault(mid, set())
        kick_off  = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
        delta_min = (kick_off - datetime.now(timezone.utc)).total_seconds() / 60
        if 28 <= delta_min <= 32 and "reminder_30" not in seen_events[mid]:
            seen_events[mid].add("reminder_30")
            await channel.send(
                embed=match_embed(match, "⏰ Kick-Off in 30 Minutes!", discord.Color.teal(), show_tips=True))
    except Exception as e:
        print(f"[reminder error] {e}")


@tasks.loop(hours=24)
async def daily_digest():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if not channel:
        return
    try:
        now_ist = datetime.now(IST)
        today   = now_ist.strftime("%Y-%m-%d")
        matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
                if data:
                    matches.extend(data.get("matches", []))
        if matches:
            matches.sort(key=lambda m: m.get("utcDate", ""))
            await channel.send(embed=today_digest_embed(matches, "Today's Matches"))
    except Exception as e:
        print(f"[digest error] {e}")


@daily_digest.before_loop
async def before_digest():
    await bot.wait_until_ready()
    now    = datetime.now(timezone.utc)
    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    await asyncio.sleep((target - now).total_seconds())


@tasks.loop(seconds=POLL_INTERVAL * 5)
async def poll_friendlies():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if not channel:
        return
    try:
        async with aiohttp.ClientSession() as session:
            now = datetime.now(timezone.utc)
            upcoming = await fetch_sportsdb(session, f"eventsnextleague.php?id={SPORTSDB_LEAGUE}")
            if upcoming and upcoming.get("events"):
                for ev in upcoming["events"]:
                    eid = ev.get("idEvent", "")
                    if not eid:
                        continue
                    seen_events.setdefault(eid, set())
                    ds, ts = ev.get("dateEvent", ""), ev.get("strTime", "")
                    if ds and ts:
                        try:
                            ko = datetime.fromisoformat(f"{ds}T{ts}+00:00")
                            if 28 <= (ko - now).total_seconds() / 60 <= 32 and "reminder_30" not in seen_events[eid]:
                                seen_events[eid].add("reminder_30")
                                await channel.send(
                                    embed=friendly_embed(ev, "⏰ Friendly in 30 Minutes!", discord.Color.teal(), True))
                        except Exception:
                            pass
            past = await fetch_sportsdb(session, f"eventslastleague.php?id={SPORTSDB_LEAGUE}")
            if past and past.get("events"):
                for ev in past["events"]:
                    eid = ev.get("idEvent", "")
                    if not eid:
                        continue
                    seen_events.setdefault(eid, set())
                    if ev.get("strStatus") == "Match Finished" and "finished" not in seen_events[eid]:
                        seen_events[eid].add("finished")
                        await channel.send(embed=friendly_embed(ev, "🏁 Friendly Full Time", discord.Color.greyple()))
    except Exception as e:
        print(f"[friendlies error] {e}")

# ─── SLASH COMMANDS ───────────────────────────────────────────

@tree.command(name="today", description="Show today's match schedule")
async def cmd_today(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        now_ist = datetime.now(IST)
        today   = now_ist.strftime("%Y-%m-%d")
        matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
                if data:
                    matches.extend(data.get("matches", []))
        if not matches:
            await interaction.followup.send(f"No matches today ({now_ist.strftime('%d %b')}). Try `/schedule`.")
            return
        matches.sort(key=lambda m: m.get("utcDate", ""))
        await interaction.followup.send(embed=today_digest_embed(matches, "Today's Matches"))
    except Exception as e:
        print(f"[/today error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch today's matches. Try again.")


@tree.command(name="schedule", description="Show upcoming matches with IST kick-off times")
async def cmd_schedule(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=SCHEDULED")
                if data:
                    matches.extend(data.get("matches", []))
        if not matches:
            await interaction.followup.send("No upcoming matches found. Tournament starts **June 11, 2026**!")
            return
        matches.sort(key=lambda m: m.get("utcDate", ""))
        star_first = sorted(matches, key=lambda m: (
            0 if (get_stars((m.get("homeTeam") or {}).get("name", "")) or
                  get_stars((m.get("awayTeam") or {}).get("name", ""))) else 1,
            m.get("utcDate", "")
        ))
        embeds = [
            match_embed(
                m,
                "📅 Upcoming ⭐" if (
                    get_stars((m.get("homeTeam") or {}).get("name", "")) or
                    get_stars((m.get("awayTeam") or {}).get("name", ""))
                ) else "📅 Upcoming",
                discord.Color.blue(),
                show_tips=True
            )
            for m in star_first[:5]
        ]
        await interaction.followup.send(embeds=embeds)
    except Exception as e:
        print(f"[/schedule error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch schedule. Try again.")


@tree.command(name="live", description="Show live match scores")
async def cmd_live(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        embeds = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
                if data:
                    for m in data.get("matches", [])[:3]:
                        full = await fetch_fd(session, f"/matches/{m['id']}")
                        embeds.append(match_embed(full or m, "🔴 LIVE", discord.Color.red()))
        if not embeds:
            await interaction.followup.send("No live matches right now. Try `/today` for today's schedule.")
        else:
            await interaction.followup.send(embeds=embeds[:10])
    except Exception as e:
        print(f"[/live error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch live scores.")


@tree.command(name="results", description="Show recent match results")
async def cmd_results(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=FINISHED")
                if data:
                    matches.extend(data.get("matches", []))
        if not matches:
            await interaction.followup.send("No finished matches yet. Tournament starts **June 11, 2026**!")
            return
        matches.sort(key=lambda m: m.get("utcDate", ""), reverse=True)
        embeds = []
        async with aiohttp.ClientSession() as session:
            for m in matches[:5]:
                full = await fetch_fd(session, f"/matches/{m['id']}")
                embeds.append(match_embed(full or m, "✅ Result", discord.Color.greyple()))
        await interaction.followup.send(embeds=embeds)
    except Exception as e:
        print(f"[/results error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch results.")


@tree.command(name="standings", description="Show World Cup 2026 standings")
async def cmd_standings(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            data = await fetch_fd(session, "/competitions/WC/standings")
        if not data or not data.get("standings"):
            await interaction.followup.send("🏆 Standings not available yet — tournament kicks off **June 11, 2026**!")
            return
        embed = discord.Embed(title="🏆 FIFA World Cup 2026 — Standings", color=discord.Color.gold())
        for group in data["standings"][:12]:
            name = group.get("group") or group.get("stage", "Group")
            rows = []
            for t in group.get("table", []):
                tf = get_flag(t["team"]["name"])
                rows.append(f"`{t['position']}` {tf} {t['team']['name'][:18]}  **{t['points']}pt**  GD{t['goalDifference']:+}")
            if rows:
                embed.add_field(name=name, value="\n".join(rows), inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"[/standings error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch standings.")


@tree.command(name="stars", description="Matches featuring Messi, Ronaldo, Haaland, Salah...")
async def cmd_stars(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                for st in ("SCHEDULED", "LIVE"):
                    data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status={st}")
                    if data:
                        matches.extend(data.get("matches", []))
        matches.sort(key=lambda m: m.get("utcDate", ""))
        star_matches = [m for m in matches if
                        get_stars((m.get("homeTeam") or {}).get("name", "")) or
                        get_stars((m.get("awayTeam") or {}).get("name", ""))]
        if not star_matches:
            await interaction.followup.send("⭐ No star-player matches right now. Check back closer to June 11!")
            return
        embeds = [match_embed(m, "⭐ Star Match", discord.Color.gold(), show_tips=True)
                  for m in star_matches[:5]]
        await interaction.followup.send(content="🌟 **Matches featuring football legends!**", embeds=embeds)
    except Exception as e:
        print(f"[/stars error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch star matches.")


@tree.command(name="friendlies", description="Show upcoming international friendlies")
async def cmd_friendlies(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            data = await fetch_sportsdb(session, f"eventsnextleague.php?id={SPORTSDB_LEAGUE}")
        if not data or not data.get("events"):
            await interaction.followup.send("No upcoming international friendlies found right now.")
            return
        embeds = [friendly_embed(e, "🌍 Upcoming Friendly", discord.Color.purple(), True)
                  for e in data["events"][:5]]
        await interaction.followup.send(embeds=embeds)
    except Exception as e:
        print(f"[/friendlies error] {e}")
        await safe_followup(interaction, content="⚠️ Could not fetch friendlies.")


@tree.command(name="rivalry", description="Rivalry history & tips between two national teams")
async def cmd_rivalry(interaction: discord.Interaction, team1: str, team2: str):
    try:
        rv    = get_rivalry(team1, team2)
        f1, f2 = get_flag(team1), get_flag(team2)
        if rv:
            embed = discord.Embed(title=f"🔥 {rv[0]}", description=rv[1], color=discord.Color.red())
        else:
            embed = discord.Embed(
                title=f"{f1} {team1}  vs  {f2} {team2}",
                description="No rivalry data yet — but every World Cup match writes history!",
                color=discord.Color.blue())
        embed.set_author(name=f"{f1} {team1}  ⚔️  {team2} {f2}")
        sh, sa = stars_line(team1), stars_line(team2)
        if sh:
            embed.add_field(name=f"🌟 {team1}", value=sh, inline=True)
        if sa:
            embed.add_field(name=f"🌟 {team2}", value=sa, inline=True)
        embed.add_field(name="💡 Tip", value=get_tip(), inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"[/rivalry error] {e}")
        await interaction.response.send_message("⚠️ Could not fetch rivalry info.", ephemeral=True)


# ─── STARTUP ─────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")
    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
            print(f"[Sync] {guild.name} ok")
        except Exception as e:
            print(f"[Sync] {guild.name}: {e}")
    try:
        await tree.sync()
    except Exception as e:
        print(f"[Global sync] {e}")

    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="⚽ WC2026Bot is Live!",
            description=(
                f"Tracking: **{' · '.join(COMPETITION_IDS)}** + Friendlies\n"
                f"🗓️ **FIFA World Cup kicks off June 11, 2026!**\n\n"
                f"**Auto-posted here (no action needed):**\n"
                f"• ⚽ Goals & scorers — live every 60s\n"
                f"• ⏸️ Half-time  •  🏁 Full-time results\n"
                f"• ⏰ 30-min kick-off reminders\n"
                f"• 📅 Daily match digest at **8:30 AM IST**\n\n"
                f"**Slash Commands:**\n"
                f"`/today` `/schedule` `/live` `/results` `/standings`\n"
                f"`/stars` — Messi, Ronaldo, Haaland, Salah matches ⭐\n"
                f"`/rivalry <team1> <team2>` — history & tips 🔥\n"
                f"`/friendlies` — international friendlies"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="⚽ Goals • 🟨🟥 Cards • 🌟 Stars • 🔥 Rivalries • ⏰ IST")
        await channel.send(embed=embed)
        try:
            now_ist = datetime.now(IST)
            today   = now_ist.strftime("%Y-%m-%d")
            matches = []
            async with aiohttp.ClientSession() as session:
                for comp_id in COMPETITION_IDS:
                    data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
                    if data:
                        matches.extend(data.get("matches", []))
            if matches:
                matches.sort(key=lambda m: m.get("utcDate", ""))
                await channel.send(embed=today_digest_embed(matches, "Today's Matches"))
        except Exception as e:
            print(f"[startup today error] {e}")

    if UPDATES_CHANNEL_ID and FOOTBALL_API_KEY:
        poll_live_matches.start()
        poll_friendlies.start()
        daily_digest.start()
        print(f"[Bot] All tasks started")
    else:
        print("[Bot] WARNING: missing env vars")


bot.run(DISCORD_TOKEN)
