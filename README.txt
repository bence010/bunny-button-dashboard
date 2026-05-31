# 🥕 Bunny Button Daily Report

Generates a daily digest from the public [BunnyButton.xyz](https://bunnybutton.xyz) API and posts it wherever you want.

## What it reports

```
🥕 Daily Bunny Report — 2026-05-31

🏆  #1 remains unchanged: @PlayerX  (128K 🥕)
📈  Biggest climber: @RabbitKing (+14 places)
📉  Biggest drop: @CarrotFarmer (-8 places)
🎉  New Top 10 entrants: @BunnyLord • @HopMaster
💰  ETH: $3,842 (+2.7%)
🐰  Total active parties: 127
💎  Presale: 🟧🟧🟧⬜⬜⬜⬜⬜⬜⬜ 31.00/100 ETH (31.0%)

⚔️  The gap between #1 and #2 is only 4.2K carrots (3.2%) — anyone's game.

See you tomorrow for the next Bunny Report. 🐇
— BunnyButton.xyz
```

## Setup

No dependencies beyond Python 3.6+. Just clone or copy `bunny_report.py`.

```bash
python3 bunny_report.py          # print to stdout
```

State (yesterday's ranks + ETH price) is saved to `bunny_report_state.json`
in the working directory so movement deltas work across days.

## Post to Discord

Add to the bottom of your run script or edit `__main__`:

```python
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
report = build_report()
send_discord(report, DISCORD_WEBHOOK)
```

## Post to Telegram

```python
BOT_TOKEN = "123456:ABC-your-token"
CHAT_ID   = "@your_channel"   # or a numeric chat id
report = build_report()
send_telegram(report, BOT_TOKEN, CHAT_ID)
```

## Run daily with cron

```cron
# Every day at 08:00
0 8 * * * cd /path/to/bunny_report && python3 bunny_report.py
```

Or with a one-liner that also posts to Discord:

```cron
0 8 * * * cd /path/to/bunny_report && python3 -c "
import bunny_report as b
report = b.build_report()
b.send_discord(report, 'https://discord.com/api/webhooks/YOUR/WEBHOOK')
"
```

## Run daily with GitHub Actions

```yaml
# .github/workflows/bunny-report.yml
name: Daily Bunny Report
on:
  schedule:
    - cron: '0 8 * * *'
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run report
        env:
          DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}
        run: |
          python3 -c "
          import bunny_report as b, os
          report = b.build_report()
          print(report)
          wh = os.getenv('DISCORD_WEBHOOK')
          if wh: b.send_discord(report, wh)
          "
      - name: Commit state
        run: |
          git config user.name 'bunny-bot'
          git config user.email 'bot@bunnybutton.xyz'
          git add bunny_report_state.json
          git commit -m '📊 daily state update' || true
          git push
```

## API endpoints used

| Endpoint | Data |
|---|---|
| `/api/leaderboard?limit=100` | ranks, wallets, X handles, carrot totals |
| `/api/eth-price` | ETH/USD spot (cached 5 min) |
| `/api/party/list` | active party count |
| `/api/presale/status` | ETH raised toward 100 ETH cap |

All public, no auth required. Rate limit: 30 req/min per IP.