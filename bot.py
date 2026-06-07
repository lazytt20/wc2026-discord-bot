"""
WC2026Bot — Discord bot for FIFA World Cup 2026 + International Football
- Rich embeds with flag emojis, goal scorers, cards, venue
- IST timestamps (Indian Standard Time)
- Star player highlights (Messi, Ronaldo, Haaland, Neymar, Salah…)
- Rivalry callouts & match tips
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import asyncio
import os
import random
from datetime import datetime, timezone, timedelta

# ─── CONFIG ────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
FOOTBALL_API_KEY   = os.getenv("FOOTBALL_API_KEY")
UPDATES_CHANNEL_ID = int(os.getenv("UPDATES_CHANNEL_ID", "0"))
ALERT_ROLE_NAME    = os.getenv("ALERT_ROLE_NAME", "WorldCup-Fan")
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL", "60"))
COMPETITION_IDS    = [c.strip() for c in os.getenv("COMPETITION_IDS", "WC,EC,UNL").split(",")]
SPORTSDB_LEAGUE    = os.getenv("SPORTSDB_LEAGUE", "4480")

BASE_URL      = "https://api.football-data.org/v4"
SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"

IST = timezone(timedelta(hours=5, minutes=30))


def fmt_ist(utc_str: str) -> str:
    """Convert UTC ISO string to '7 Jun, 10:30 PM IST'."""
    if not utc_str:
        return "TBD"
    try:
        dt  = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        ist = dt.astimezone(IST)
        return ist.strftime("%-d %b, %I:%M %p IST")
    except Exception:
        return utc_str[:16].replace("T", " ") + " UTC"


# ─── FLAG MAP ──────────────────────────────────────────────
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
    return "⚽"


# ─── STAR PLAYERS ───────────────────────────────────────────────
STARS = {
    "Argentina":   [("Lionel Messi",      "🐐 GOAT"),
                    ("Julián Álvarez",     "🌟")],
    "Portugal":    [("Cristiano Ronaldo", "👑 CR7"),
                    ("Rafael Leão",        "⚡")],
    "Norway":      [("Erling Haaland",    "🤖 Machine"),
                    ("Martin Ødegaard",   "🎯")],
    "Brazil":      [("Vinicius Jr",       "⚡ Vini Jr"),
                    ("Rodrygo",           "🌟"),
                    ("Neymar Jr",         "🎪 Ney")],
    "Egypt":       [("Mohamed Salah",     "🔴 The Egyptian King")],
    "France":      [("Kylian Mbappé",     "💨 Kylian"),
                    ("Antoine Griezmann", "🎯")],
    "England":     [("Harry Kane",        "👑 Kane"),
                    ("Jude Bellingham",   "🎸")],
    "Spain":       [("Lamine Yamal",      "✨ Wonder Kid"),
                    ("Pedri",             "🎩"),
                    ("Álvaro Morata",     "⚽")],
    "Germany":     [("Florian Wirtz",     "🎸"),
                    ("Jamal Musiala",     "🕺")],
    "Netherlands": [("Virgil van Dijk",   "🧱"),
                    ("Cody Gakpo",        "⚡")],
    "Belgium":     [("Kevin De Bruyne",   "🎯 KDB"),
                    ("Romelu Lukaku",     "💪")],
    "Croatia":     [("Luka Modrić",       "🪤 Maestro")],
    "Uruguay":     [("Darwin Núñez",      "💥")],
    "Colombia":    [("James Rodríguez",   "🌟"),
                    ("Luis Díaz",         "⚡")],
    "Japan":       [("Takumi Minamino",   "🌟"),
                    ("Ritsu Doan",        "⚡")],
    "Morocco":     [("Achraf Hakimi",     "🚀"),
                    ("Hakim Ziyech",      "🎩")],
    "Senegal":     [("Sadio Mané",        "⚡"),
                    ("Édouard Mendy",     "🧤")],
    "Saudi Arabia":[("Salem Al-Dawsari",  "⚡")],
    "South Korea": [("Son Heung-min",     "🌟 Sonny")],
    "Poland":      [("Robert Lewandowski","💥 Lewy")],
    "Serbia":      [("Aleksandar Mitrović","💥")],
    "Denmark":     [("Christian Eriksen", "❤️ Comeback King")],
    "Austria":     [("David Alaba",       "🎯")],
}

def get_stars(team: str) -> list:
    if team in STARS:
        return STARS[team]
    for k, v in STARS.items():
        if k.lower() in team.lower() or team.lower() in k.lower():
            return v
    return []

def stars_line(team: str) -> str | None:
    s = get_stars(team)
    if not s:
        return None
    return "  •  ".join(f"{tag} {name}" for name, tag in s)

# ─── RIVALRIES & TIPS ───────────────────────────────────────────
RIVALRIES = {
    frozenset(["Argentina", "Brazil"]):      ("🔥 EL CLÁSICO DEL SUR",
        "The greatest South American rivalry! These two have met 107 times. "
        "Argentina leads WC finals h2h 3-2. Messi vs Vinicius is the subplot. "
        "Expect drama, diving, and late heartbreak."),
    frozenset(["Argentina", "France"]):      ("👑 WORLD CUP FINAL REMATCH",
        "A replay of Qatar 2022 — one of the greatest WC finals in history! "
        "Argentina won on penalties after Mbappé's hat-trick levelled it at 3-3. "
        "France want revenge. This one will be ELECTRIC."),
    frozenset(["Portugal", "Argentina"]):    ("🐐 GOAT DERBY",
        "Messi vs Ronaldo — the eternal debate settles on the pitch! "
        "Both could be in their final World Cup. Messi has the WC trophy; "
        "Ronaldo is still chasing his ultimate dream."),
    frozenset(["Portugal", "France"]):       ("🌟 EURO RIVALS on the WORLD STAGE",
        "France leads h2h but Portugal shocked them in Euro 2016 final. "
        "Ronaldo vs Mbappé: two generational talents, one spotlight."),
    frozenset(["England", "Germany"]):       ("⚔️ OLD ENEMIES",
        "A rivalry spanning decades! Germany won the 1966 WC final on English soil. "
        "The 5-1 in Munich (2001), Euro 96 semis, countless knockout clashes. "
        "England are still waiting — Germany always seem to find a way."),
    frozenset(["England", "France"]):        ("🦁 vs 🐓 THE HUNDRED YEARS WAR CONTINUES",
        "Two historic nations, fierce adversaries. France knocked England out "
        "in Qatar 2022 QF with Giroud's header. Bellingham vs Mbappé is a "
        "generational clash within the grudge match."),
    frozenset(["Brazil", "Germany"]):        ("💀 THE 7-1 — MINEIRAZO",
        "Brazil 1–7 Germany. 2014 World Cup semi-final. On home soil. "
        "The darkest day in Brazilian football history. "
        "Brazil haven't forgotten. Every time these two meet, it matters more than football."),
    frozenset(["Spain", "Germany"]):         ("🏆 KINGS vs KAISERS",
        "Combined 7 World Cups between them. Tactical masterminds on both sides. "
        "Spain beat Germany in 2010 WC semi & 2024 Euros QF. "
        "This is a clash of philosophies: tiki-taka vs German efficiency."),
    frozenset(["Brazil", "France"]):         ("🕊️ FLAIR vs EFFICIENCY",
        "Brazil flair vs French efficiency. France beat Brazil in 1986 & 1998 QF. "
        "Zidane's 98 WC masterclass haunts Brazil. Vinicius vs Mbappé would be sensational."),
    frozenset(["Netherlands", "Germany"]):   ("🟠 DE KLASSIEKER",
        "One of football's oldest grudge matches. Netherlands vs Germany — "
        "the Dutch still talk about 1988 Euro redemption. "
        "Always fiery, always physical, never boring."),
    frozenset(["Mexico", "United States"]):  ("🌎 EL TRI vs USMNT — CONCACAF DERBY",
        "CONCACAF's fiercest derby, now at the World Cup! "
        "Mexico leads all-time h2h, but USA has rapidly closed the gap. "
        "With both nations hosting the tournament, this fixture is HUGE."),
    frozenset(["Italy", "France"]):          ("🍕 vs 🥐 SOUTHERN EUROPE SHOWDOWN",
        "Italy and France have met in multiple WC knockouts. "
        "Remember Zidane's headbutt on Materazzi in 2006 final? "
        "Passion, skill and tactical sophistication on both sides."),
    frozenset(["Spain", "Brazil"]):          ("🌍 LATIN KINGS",
        "Two of football's most stylish nations. Spain's 2010 WC win "
        "interrupted Brazilian dominance. Lamine Yamal vs Vinicius Jr — a baller battle."),
}

GENERAL_TIPS = [
    "💡 Watch the first 15 mins — most shock goals happen early in tournaments.",
    "💡 Set piece specialists like Messi & De Bruyne decide tight knockout games.",
    "💡 Look out for underdog upsets — WC 2022 had Morocco in the semi-finals!",
    "💡 Fatigue is real — teams playing extra time in R16 often struggle in QF.",
    "💡 The goalkeeper is the X-factor. Tournament runs often start with a heroic GK.",
    "💡 Home continent teams historically over-perform at World Cups.",
    "💡 The first goal in a knockout match wins the tie ~65% of the time.",
    "💡 Penalty shootouts are won in training. Expect Germany to be lethal from the spot.",
    "💡 Watch for late substitutions — some of the biggest WC goals come from subs.",
    "💡 Tournament football is about momentum — the team peaking at the right time wins.",
]

def get_rivalry(home: str, away: str):
    for k, v in RIVALRIES.items():
        teams = list(k)
        h_match = any(t.lower() in home.lower() or home.lower() in t.lower() for t in teams)
        a_match = any(t.lower() in away.lower() or away.lower() in t.lower() for t in teams)
        if h_match and a_match:
            return v
    return None

def get_tip() -> str:
    return random.choice(GENERAL_TIPS)


# ─── BOT SETUP ───────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
seen_events: dict = {}


# ─── FETCH HELPERS ──────────────────────────────────────────────

async def fetch_fd(session, endpoint):
    url = f"{BASE_URL}{endpoint}"
    headers = {"X-Auth-Token": FOOTBALL_API_KEY}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            print(f"[FD {resp.status}] {endpoint}")
    except Exception as e:
        print(f"[FD ERROR] {e}")
    return None

async def fetch_sportsdb(session, endpoint):
    try:
        async with session.get(f"{SPORTSDB_BASE}/{endpoint}", timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception as e:
        print(f"[SDB ERROR] {e}")
    return None

def get_alert_role(guild):
    return discord.utils.get(guild.roles, name=ALERT_ROLE_NAME)


# ─── EMBED BUILDERS ─────────────────────────────────────────────

def match_embed(match, title, color, show_tips=False):
    home   = match["homeTeam"]["name"]
    away   = match["awayTeam"]["name"]
    hf, af = get_flag(home), get_flag(away)
    ft     = match.get("score", {}).get("fullTime", {})
    ht     = match.get("score", {}).get("halfTime", {})
    h_g    = ft.get("home")
    a_g    = ft.get("away")
    hs     = str(h_g) if h_g is not None else "–"
    as_    = str(a_g) if a_g is not None else "–"
    status = match.get("status", "")
    minute = match.get("minute")
    comp   = match.get("competition", {}).get("name", "")
    utc_d  = match.get("utcDate", "")
    venue  = match.get("venue", "")

    if status in ("TIMED", "SCHEDULED"):
        score_line = f"**{hf} {home}**  ⚔️  **{away} {af}**"
    else:
        score_line = f"**{hf} {home}**   `{hs} — {as_}`   **{away} {af}**"

    embed = discord.Embed(title=title, description=score_line, color=color)
    if comp:
        embed.set_author(name=f"🏆 {comp}")

    if status == "IN_PLAY" and minute:
        embed.add_field(name="⏱️ Time", value=f"**{minute}'**", inline=True)
    if ht.get("home") is not None:
        embed.add_field(name="🔔 HT Score", value=f"**{ht['home']} – {ht['away']}**", inline=True)
    if venue:
        embed.add_field(name="🏙️ Venue", value=venue, inline=True)

    goals = match.get("goals", [])
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

    bookings = match.get("bookings", [])
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

    subs = match.get("substitutions", [])
    if subs and status == "IN_PLAY":
        h_s = sum(1 for s in subs if (s.get("team") or {}).get("name") == home)
        a_s = sum(1 for s in subs if (s.get("team") or {}).get("name") != home)
        embed.add_field(name="🔄 Subs", value=f"🏠 {h_s}  •  ✈️ {a_s}", inline=True)

    h_stars = stars_line(home)
    a_stars = stars_line(away)
    if h_stars or a_stars:
        star_text = ""
        if h_stars:
            star_text += f"🏠 **{home}:** {h_stars}\n"
        if a_stars:
            star_text += f"✈️ **{away}:** {a_stars}"
        embed.add_field(name="🌟 Stars to Watch", value=star_text.strip(), inline=False)

    rivalry = get_rivalry(home, away)
    if rivalry:
        rtitle, rdesc = rivalry
        embed.add_field(name=f"🔥 {rtitle}", value=rdesc, inline=False)

    if show_tips:
        embed.add_field(name="💡 Match Tip", value=get_tip(), inline=False)

    if utc_d:
        embed.set_footer(text=f"⏰ Kick-off: {fmt_ist(utc_d)}")
    return embed


def friendly_embed(event, title, color, show_tips=False):
    home   = event.get("strHomeTeam", "?")
    away   = event.get("strAwayTeam", "?")
    hf, af = get_flag(home), get_flag(away)
    hs     = event.get("intHomeScore")
    as_    = event.get("intAwayScore")
    date   = event.get("dateEvent", "")
    time_s = event.get("strTime", "")
    league = event.get("strLeague", "International Friendly")

    if hs is not None and as_ is not None:
        score_line = f"**{hf} {home}**   `{hs} — {as_}`   **{away} {af}**"
    else:
        score_line = f"**{hf} {home}**  ⚔️  **{away} {af}**"

    embed = discord.Embed(title=title, description=score_line, color=color)
    embed.set_author(name=f"🌍 {league}")

    h_stars = stars_line(home)
    a_stars = stars_line(away)
    if h_stars or a_stars:
        star_text = ""
        if h_stars:
            star_text += f"🏠 **{home}:** {h_stars}\n"
        if a_stars:
            star_text += f"✈️ **{away}:** {a_stars}"
        embed.add_field(name="🌟 Stars to Watch", value=star_text.strip(), inline=False)

    rivalry = get_rivalry(home, away)
    if rivalry:
        rtitle, rdesc = rivalry
        embed.add_field(name=f"🔥 {rtitle}", value=rdesc, inline=False)

    if show_tips:
        embed.add_field(name="💡 Match Tip", value=get_tip(), inline=False)

    if date and time_s:
        embed.set_footer(text=f"⏰ Kick-off: {fmt_ist(date + 'T' + time_s + '+00:00')}")
    elif date:
        embed.set_footer(text=f"📅 {date}")
    return embed

# ─── LIVE MATCH POLLING ────────────────────────────────────────

@tasks.loop(seconds=POLL_INTERVAL)
async def poll_live_matches():
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel is None:
        return
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            live = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
            if live:
                for match in live.get("matches", []):
                    await handle_live_match(channel, match, session)
            sched = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=SCHEDULED")
            if sched:
                for match in sched.get("matches", []):
                    await handle_reminder(channel, match)


async def handle_live_match(channel, match, session):
    mid    = match["id"]
    status = match.get("status", "")
    ft     = match.get("score", {}).get("fullTime", {})
    h, a   = (ft.get("home") or 0), (ft.get("away") or 0)
    if mid not in seen_events:
        seen_events[mid] = set()

    async def rich():
        full = await fetch_fd(session, f"/matches/{mid}")
        return full if full else match

    if status == "IN_PLAY" and "started" not in seen_events[mid]:
        seen_events[mid].add("started")
        full = await rich()
        await channel.send(embed=match_embed(full, "⚽ Match Kicked Off!", discord.Color.green()))

    score_key = f"score_{h}_{a}"
    if score_key not in seen_events[mid] and (h + a) > 0:
        seen_events[mid].add(score_key)
        full = await rich()
        hn = full["homeTeam"]["name"]
        an = full["awayTeam"]["name"]
        await channel.send(
            f"**GOAAAAL!**  {get_flag(hn)} **{hn}** `{h} – {a}` **{an}** {get_flag(an)}",
            embed=match_embed(full, "🚨 GOAL!", discord.Color.gold()))

    if status == "PAUSED" and "halftime" not in seen_events[mid]:
        seen_events[mid].add("halftime")
        full = await rich()
        await channel.send(embed=match_embed(full, "⏸️ Half-Time", discord.Color.blue()))

    for st, ttl, clr in [
        ("FINISHED",         "🏁 Full-Time",           discord.Color.red()),
        ("EXTRA_TIME",       "⏱️ Extra Time Begins",   discord.Color.orange()),
        ("PENALTY_SHOOTOUT", "🎯 Penalty Shootout!",   discord.Color.purple()),
    ]:
        if status == st and st not in seen_events[mid]:
            seen_events[mid].add(st)
            full = await rich()
            await channel.send(embed=match_embed(full, ttl, clr))


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
        await channel.send(
            embed=match_embed(match, "⏰ Kick-Off in 30 Minutes!", discord.Color.teal(), show_tips=True))


# ─── DAILY DIGEST ───────────────────────────────────────────────

@tasks.loop(hours=24)
async def daily_digest():
    """Posts today's matches every morning at 8:30 AM IST (3:00 AM UTC)."""
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel is None:
        return
    now_ist = datetime.now(IST)
    today   = now_ist.strftime("%Y-%m-%d")
    all_matches = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
            if data:
                all_matches.extend(data.get("matches", []))
    if not all_matches:
        return
    all_matches.sort(key=lambda m: m.get("utcDate", ""))
    embed = discord.Embed(
        title=f"📅 Today's Matches — {now_ist.strftime('%d %b %Y')}",
        color=discord.Color.gold()
    )
    for m in all_matches[:10]:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        hf, af = get_flag(home), get_flag(away)
        ko   = fmt_ist(m.get("utcDate", ""))
        comp = m.get("competition", {}).get("name", "")
        stars_h = stars_line(home)
        stars_a = stars_line(away)
        val = f"⏰ **{ko}**"
        if stars_h or stars_a:
            val += f"\n🌟 " + (stars_h or "") + (" | " + stars_a if stars_a else "")
        rv = get_rivalry(home, away)
        if rv:
            val += f"\n🔥 *{rv[0]}*"
        embed.add_field(
            name=f"{hf} {home}  vs  {away} {af}",
            value=val,
            inline=False
        )
    embed.set_footer(text="🌍 All times in IST  •  Use /live for live scores  •  /results for yesterday's results")
    await channel.send(embed=embed)


@daily_digest.before_loop
async def before_digest():
    """Wait until 3:00 AM UTC (8:30 AM IST) to start."""
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    await asyncio.sleep((target - now).total_seconds())


# ─── FRIENDLIES POLLING ─────────────────────────────────────────

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
                ds = event.get("dateEvent", "")
                ts = event.get("strTime", "")
                if ds and ts:
                    try:
                        ko = datetime.fromisoformat(f"{ds}T{ts}+00:00")
                        dm = (ko - now).total_seconds() / 60
                        if 28 <= dm <= 32 and "reminder_30" not in seen_events[eid]:
                            seen_events[eid].add("reminder_30")
                            await channel.send(
                                embed=friendly_embed(event, "⏰ Friendly in 30 Minutes!", discord.Color.teal(), show_tips=True))
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
                    await channel.send(embed=friendly_embed(event, "🏁 Friendly — Full Time", discord.Color.greyple()))


# ─── SLASH COMMANDS ─────────────────────────────────────────────

@tree.command(name="live", description="Show currently live matches")
async def cmd_live(interaction):
    await interaction.response.defer()
    embeds = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status=LIVE")
            if data:
                for m in data.get("matches", [])[:3]:
                    full = await fetch_fd(session, f"/matches/{m['id']}")
                    embeds.append(match_embed(full or m, "🔴 LIVE", discord.Color.red()))
    if not embeds:
        await interaction.followup.send("📫 No matches live right now. Try `/schedule` for upcoming fixtures.")
    else:
        await interaction.followup.send(embeds=embeds[:10])


@tree.command(name="schedule", description="Show upcoming matches with kick-off times in IST")
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
    def has_stars(m):
        return bool(get_stars(m["homeTeam"]["name"]) or get_stars(m["awayTeam"]["name"]))
    star_matches  = [m for m in all_matches if has_stars(m)][:3]
    other_matches = [m for m in all_matches if not has_stars(m)][:2]
    combined = (star_matches + other_matches)[:5]
    embeds = [
        match_embed(m, "📅 Upcoming ⭐" if has_stars(m) else "📅 Upcoming",
                    discord.Color.blue(), show_tips=True)
        for m in combined
    ]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="stars", description="Matches featuring Messi, Ronaldo, Haaland, Salah and more")
async def cmd_stars(interaction):
    await interaction.response.defer()
    all_matches = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            for status in ("SCHEDULED", "LIVE"):
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?status={status}")
                if data:
                    all_matches.extend(data.get("matches", []))
    all_matches.sort(key=lambda m: m.get("utcDate", ""))
    star_matches = [m for m in all_matches
                    if get_stars(m["homeTeam"]["name"]) or get_stars(m["awayTeam"]["name"])]
    if not star_matches:
        await interaction.followup.send("⭐ No star-player matches found right now. Check back closer to the tournament!")
        return
    embeds = [match_embed(m, "⭐ Star Match", discord.Color.gold(), show_tips=True) for m in star_matches[:5]]
    await interaction.followup.send(content="🌟 **Matches featuring football legends!**", embeds=embeds)


@tree.command(name="friendlies", description="Show upcoming international friendlies")
async def cmd_friendlies(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch_sportsdb(session, f"eventsnextleague.php?id={SPORTSDB_LEAGUE}")
    if not data or not data.get("events"):
        await interaction.followup.send("No upcoming friendlies found right now.")
        return
    embeds = [friendly_embed(e, "🌍 Upcoming Friendly", discord.Color.purple(), show_tips=True) for e in data["events"][:5]]
    await interaction.followup.send(embeds=embeds)


@tree.command(name="standings", description="Show World Cup 2026 group standings")
async def cmd_standings(interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        data = await fetch_fd(session, "/competitions/WC/standings")
    if not data or not data.get("standings"):
        await interaction.followup.send("🏆 Standings not available yet — tournament starts **June 11, 2026**!")
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


@tree.command(name="results", description="Show recent match results")
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
        embeds = []
        for m in all_matches[:5]:
            full = await fetch_fd(session, f"/matches/{m['id']}")
            embeds.append(match_embed(full or m, "✅ Result", discord.Color.greyple()))
    await interaction.followup.send(embeds=embeds)


@tree.command(name="rivalry", description="Get rivalry history & tips for two national teams")
async def cmd_rivalry(interaction, team1: str, team2: str):
    rv = get_rivalry(team1, team2)
    f1, f2 = get_flag(team1), get_flag(team2)
    if rv:
        rtitle, rdesc = rv
        embed = discord.Embed(title=f"🔥 {rtitle}", description=rdesc, color=discord.Color.red())
    else:
        embed = discord.Embed(
            title=f"{f1} {team1}  vs  {f2} {team2}",
            description="No specific rivalry data — but every World Cup match is its own story!",
            color=discord.Color.blue())
    embed.set_author(name=f"{f1} {team1}  ⚔️  {team2} {f2}")
    h_stars = stars_line(team1)
    a_stars = stars_line(team2)
    if h_stars:
        embed.add_field(name=f"🌟 {team1} Stars", value=h_stars, inline=True)
    if a_stars:
        embed.add_field(name=f"🌟 {team2} Stars", value=a_stars, inline=True)
    embed.add_field(name="💡 Match Tip", value=get_tip(), inline=False)
    await interaction.response.send_message(embed=embed)


@tree.command(name="today", description="Post today's match schedule right now")
async def cmd_today(interaction):
    await interaction.response.defer()
    now_ist = datetime.now(IST)
    today   = now_ist.strftime("%Y-%m-%d")
    all_matches = []
    async with aiohttp.ClientSession() as session:
        for comp_id in COMPETITION_IDS:
            data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
            if data:
                all_matches.extend(data.get("matches", []))
    if not all_matches:
        await interaction.followup.send(f"No matches scheduled for today ({today}). Use `/schedule` to see all upcoming.")
        return
    all_matches.sort(key=lambda m: m.get("utcDate", ""))
    embed = discord.Embed(
        title=f"📅 Today's Matches — {now_ist.strftime('%d %b %Y')}",
        color=discord.Color.gold()
    )
    for m in all_matches[:10]:
        home = m["homeTeam"]["name"]
        away = m["awayTeam"]["name"]
        hf, af = get_flag(home), get_flag(away)
        ko   = fmt_ist(m.get("utcDate", ""))
        val  = f"⏰ **{ko}**"
        stars_h = stars_line(home)
        stars_a = stars_line(away)
        if stars_h or stars_a:
            val += f"\n🌟 " + (stars_h or "") + (" | " + stars_a if stars_a else "")
        rv = get_rivalry(home, away)
        if rv:
            val += f"\n🔥 *{rv[0]}*"
        embed.add_field(name=f"{hf} {home}  vs  {away} {af}", value=val, inline=False)
    embed.set_footer(text="⏰ All times in IST")
    await interaction.followup.send(embed=embed)


# ─── STARTUP ────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[Bot] Logged in as {bot.user}")
    for guild in bot.guilds:
        try:
            await tree.sync(guild=guild)
        except Exception as e:
            print(f"[Sync] {guild.name}: {e}")
    try:
        await tree.sync()
    except Exception as e:
        print(f"[Global sync] {e}")
    channel = bot.get_channel(UPDATES_CHANNEL_ID)
    if channel:
        comps = " · ".join(COMPETITION_IDS)
        embed = discord.Embed(
            title="⚽ WC2026Bot is Live!",
            description=(
                f"Tracking: **{comps}** + International Friendlies\n"
                f"🗓️ **FIFA World Cup kicks off June 11, 2026!**\n\n"
                f"**Auto-updates posted here:**\n"
                f"• ⚽ Goals & scorers (live, every 60s)\n"
                f"• ⏸️ Half-time & 🏁 Full-time results\n"
                f"• ⏰ 30-min kick-off reminders\n"
                f"• 📅 Daily match digest at **8:30 AM IST**\n\n"
                f"**Slash Commands:**\n"
                f"`/today` — today's schedule\n"
                f"`/schedule` — all upcoming fixtures\n"
                f"`/live` — live scores & scorers\n"
                f"`/results` — recent results\n"
                f"`/standings` — group table\n"
                f"`/stars` — matches with Messi, Ronaldo, Haaland ⭐\n"
                f"`/rivalry <team1> <team2>` — history & tips 🔥"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="⚽ Goals • 🟨🟥 Cards • 🌟 Stars • 🔥 Rivalries • ⏰ Times in IST")
        await channel.send(embed=embed)
        # Post today's matches immediately on startup
        now_ist = datetime.now(IST)
        today   = now_ist.strftime("%Y-%m-%d")
        today_matches = []
        async with aiohttp.ClientSession() as session:
            for comp_id in COMPETITION_IDS:
                data = await fetch_fd(session, f"/competitions/{comp_id}/matches?dateFrom={today}&dateTo={today}")
                if data:
                    today_matches.extend(data.get("matches", []))
        if today_matches:
            today_matches.sort(key=lambda m: m.get("utcDate", ""))
            today_embed = discord.Embed(
                title=f"📅 Today's Matches — {now_ist.strftime('%d %b %Y')}",
                color=discord.Color.blue()
            )
            for m in today_matches[:10]:
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                hf, af = get_flag(home), get_flag(away)
                ko   = fmt_ist(m.get("utcDate", ""))
                val  = f"⏰ **{ko}**"
                stars_h = stars_line(home)
                stars_a = stars_line(away)
                if stars_h or stars_a:
                    val += f"\n🌟 " + (stars_h or "") + (" | " + stars_a if stars_a else "")
                rv = get_rivalry(home, away)
                if rv:
                    val += f"\n🔥 *{rv[0]}*"
                today_embed.add_field(name=f"{hf} {home}  vs  {away} {af}", value=val, inline=False)
            today_embed.set_footer(text="⏰ All times in IST  •  Updates auto-post here")
            await channel.send(embed=today_embed)
    if UPDATES_CHANNEL_ID and FOOTBALL_API_KEY:
        poll_live_matches.start()
        poll_friendlies.start()
        daily_digest.start()
        print(f"[Bot] All tasks started — poll: {POLL_INTERVAL}s, daily digest: 8:30 AM IST")
    else:
        print("[Bot] WARNING: missing env vars")


bot.run(DISCORD_TOKEN)
