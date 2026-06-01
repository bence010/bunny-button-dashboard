#!/usr/bin/env python3
"""
🥕 Bunny Button Daily Report Generator + Presale Tracker
"""

import json
import datetime
import urllib.request
import urllib.error

BASE = "https://www.bunnybutton.xyz/api"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch(path: str) -> dict:
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": "BunnyDailyReport/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def fmt_carrots(n) -> str:
    if n is None:
        return "?"
    n = int(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def short_addr(addr: str) -> str:
    if not addr:
        return "?"
    if addr.startswith("0x"):
        return addr[:6] + "…" + addr[-4:]
    return addr


def display_name(player: dict) -> str:
    handle = player.get("xHandle") or player.get("x_handle")
    if handle:
        return "@" + handle.lstrip("@")
    return short_addr(player.get("walletAddress") or player.get("wallet_address") or "")


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

STATE_FILE = "bunny_report_state.json"


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Presale tracker
# ---------------------------------------------------------------------------

PRESALE_MILESTONES = [25, 50, 75, 100]


def check_presale_alerts(eth_raised: float, state: dict) -> str:
    """Returns an alert message if a milestone was just crossed, else empty string."""
    pct = (eth_raised / 100) * 100
    already_alerted = state.get("presale_alerted", [])
    new_alerts = []

    for milestone in PRESALE_MILESTONES:
        if pct >= milestone and milestone not in already_alerted:
            new_alerts.append(milestone)

    if not new_alerts:
        return ""

    state.setdefault("presale_alerted", []).extend(new_alerts)

    highest = max(new_alerts)
    eth_remaining = 100 - eth_raised

    if highest == 100:
        msg = "🎉 PRESALE SOLD OUT! 100/100 ETH raised — the farm is full!"
    else:
        bar_filled = int(pct / 10)
        bar = "🟧" * bar_filled + "⬜" * (10 - bar_filled)
        msg = (
            f"🚨 Presale milestone reached: {highest}%!\n"
            f"{bar} {eth_raised:.2f}/100 ETH\n"
            f"💎 Only {eth_remaining:.2f} ETH left until sold out!"
        )

    return msg


# ---------------------------------------------------------------------------
# Main report logic
# ---------------------------------------------------------------------------

def build_report() -> str:
    today = datetime.date.today().isoformat()
    state = load_state()
    yesterday_ranks: dict[str, int] = state.get("ranks", {})
    yesterday_eth: float = state.get("eth_usd", 0.0)

    # ── 1. Fetch data ────────────────────────────────────────────────────────
    try:
        lb_data = fetch("/leaderboard?limit=100")
        leaderboard: list[dict] = lb_data.get("leaderboard") or lb_data.get("players") or []
    except Exception as e:
        return f"❌ Could not fetch leaderboard: {e}"

    try:
        eth_data = fetch("/eth-price")
        eth_usd: float = float(eth_data.get("ethUsd") or eth_data.get("eth_usd") or 0)
    except Exception:
        eth_usd = 0.0

    try:
        party_data = fetch("/party/list")
        parties: list = party_data.get("parties") or party_data.get("party") or []
        party_count: int = len(parties)
    except Exception:
        party_count = 0

    try:
        presale_data = fetch("/presale/status")
        eth_usd_price = eth_usd if eth_usd else 2000
        usdt_balance = float(presale_data.get("fundsReceiverUsdtBalance") or 0)
        eth_balance = float(presale_data.get("fundsReceiverEthBalance") or 0)
        eth_raised: float = eth_balance + (usdt_balance / eth_usd_price)
    except Exception as e:
        print(f"Presale error: {e}", file=__import__('sys').stderr)
        eth_raised = 0.0

    # ── 2. Presale alerts ────────────────────────────────────────────────────
    presale_alert = check_presale_alerts(eth_raised, state)

    # ── 3. Compute movements ─────────────────────────────────────────────────
    current_ranks: dict[str, int] = {}
    for p in leaderboard:
        wallet = p.get("walletAddress") or p.get("wallet_address") or ""
        rank = int(p.get("rank") or leaderboard.index(p) + 1)
        current_ranks[wallet] = rank

    biggest_climber = None
    biggest_dropper = None
    new_top10: list[str] = []
    yesterday_top10 = set(w for w, r in yesterday_ranks.items() if r <= 10)

    for p in leaderboard:
        wallet = p.get("walletAddress") or p.get("wallet_address") or ""
        name = display_name(p)
        curr = current_ranks.get(wallet, 9999)
        prev = yesterday_ranks.get(wallet)

        if prev is not None:
            delta = prev - curr
            if delta > 0:
                if biggest_climber is None or delta > biggest_climber[1]:
                    biggest_climber = (name, delta)
            elif delta < 0:
                drop = abs(delta)
                if biggest_dropper is None or drop > biggest_dropper[1]:
                    biggest_dropper = (name, drop)

        if curr <= 10 and wallet not in yesterday_top10:
            new_top10.append(name)

    # ── 4. #1 change ─────────────────────────────────────────────────────────
    top_player = leaderboard[0] if leaderboard else {}
    top_name = display_name(top_player)
    top_wallet = top_player.get("walletAddress") or top_player.get("wallet_address") or ""
    prev_top = min(yesterday_ranks, key=yesterday_ranks.get) if yesterday_ranks else None
    top_unchanged = prev_top == top_wallet or not yesterday_ranks

    # ── 5. Top-2 gap insight ──────────────────────────────────────────────────
    gap_line = ""
    if len(leaderboard) >= 2:
        c1 = int(leaderboard[0].get("totalCarrotsEarned") or leaderboard[0].get("carrots") or 0)
        c2 = int(leaderboard[1].get("totalCarrotsEarned") or leaderboard[1].get("carrots") or 0)
        gap = c1 - c2
        pct = (gap / c1 * 100) if c1 > 0 else 0
        if pct < 1:
            gap_line = "⚔️  The race for the top spot is very tight — less than 1% separates the top two!"
        elif pct < 5:
            gap_line = f"⚔️  The gap between #1 and #2 is only {fmt_carrots(gap)} carrots ({pct:.1f}%) — anyone's game."
        else:
            gap_line = f"👑  {top_name} leads by {fmt_carrots(gap)} carrots ({pct:.1f}%) — a comfortable cushion."

    # ── 6. ETH change ─────────────────────────────────────────────────────────
    eth_change = ""
    if yesterday_eth and eth_usd:
        delta_pct = (eth_usd - yesterday_eth) / yesterday_eth * 100
        sign = "+" if delta_pct >= 0 else ""
        eth_change = f" ({sign}{delta_pct:.1f}%)"

    # ── 7. Presale bar ────────────────────────────────────────────────────────
    presale_line = ""
    if eth_raised > 0:
        pct_filled = eth_raised / 100 * 100
        bar_filled = int(pct_filled / 10)
        bar = "🟧" * bar_filled + "⬜" * (10 - bar_filled)
        presale_line = f"💎  Presale: {bar} {eth_raised:.2f}/100 ETH ({pct_filled:.1f}%)"

    # ── 8. Assemble report ────────────────────────────────────────────────────
    lines = [
        f"🥕 Bunny Button Report — {today}",
        "",
    ]

    if top_unchanged:
        lines.append(f"🏆  #1 remains unchanged: {top_name}  ({fmt_carrots(top_player.get('totalCarrotsEarned') or top_player.get('carrots'))} 🥕)")
    else:
        lines.append(f"👑  New #1: {top_name}!  ({fmt_carrots(top_player.get('totalCarrotsEarned') or top_player.get('carrots'))} 🥕)")

    if biggest_climber:
        lines.append(f"📈  Biggest climber: {biggest_climber[0]} (+{biggest_climber[1]} places)")
    if biggest_dropper:
        lines.append(f"📉  Biggest drop: {biggest_dropper[0]} (-{biggest_dropper[1]} places)")

    if new_top10:
        entrants = " • ".join(new_top10)
        lines.append(f"🎉  New Top 10 entrants: {entrants}")

    if eth_usd:
        lines.append(f"💰  ETH: ${eth_usd:,.0f}{eth_change}")

    if party_count:
        lines.append(f"🐰  Total active parties: {party_count}")

    if presale_line:
        lines.append(presale_line)

    if presale_alert:
        lines.append("")
        lines.append(presale_alert)

    if gap_line:
        lines.append("")
        lines.append(gap_line)

    lines += [
        "",
        "See you next time for the next Bunny Report. 🐇",
        "— BunnyButton.xyz",
        "Made by @bbence776",
    ]

    # ── 9. Save state ─────────────────────────────────────────────────────────
    new_state = {
        "date": today,
        "ranks": current_ranks,
        "eth_usd": eth_usd,
        "presale_alerted": state.get("presale_alerted", []),
    }
    save_state(new_state)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print("Fetching Bunny Button data…\n", file=sys.stderr)
    report = build_report()
    print(report)


# ---------------------------------------------------------------------------
# Send to Discord
# ---------------------------------------------------------------------------

def send_discord(text: str, webhook_url: str):
    payload = json.dumps({"content": text}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


# ---------------------------------------------------------------------------
# Send to Telegram (supports multiple chat IDs as comma-separated string)
# ---------------------------------------------------------------------------

def send_telegram(text: str, bot_token: str, chat_ids):
    if isinstance(chat_ids, str):
        chat_ids = chat_ids.split(",")

    results = []
    for chat_id in chat_ids:
        payload = json.dumps({
            "chat_id": chat_id.strip(),
            "text": text,
        }).encode()
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            results.append(json.loads(resp.read()))

    return results
