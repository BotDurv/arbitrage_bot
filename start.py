import os
import requests
import time
import pandas as pd

# Load from Render environment variables
API_KEY = os.getenv("c347451c4dcd5b8b0266f0cd462070b9")
DISCORD_WEBHOOK = os.getenv("https://discord.com/api/webhooks/1400306346456518796/IHHcwaeKzeHl9ZQyttQ2oyMCoRgHajLAvm-UG8mX3Fl_8ZDhOxso4fmk31_KzaSodyGR")

SPORT = "aussierules_afl"  
REGION = "au"
MARKETS = "h2h,totals"

# -------------------- Fetch Odds --------------------
def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS}
    response = requests.get(url, params=params)
    try:
        data = response.json()
    except Exception as e:
        print(f"Error decoding JSON: {e}")
        return []
    if isinstance(data, dict) and "message" in data:
        print(f"API Error: {data['message']}")
        return []
    return data

# -------------------- Discord Alert --------------------
def send_discord_alert(message):
    if DISCORD_WEBHOOK:
        requests.post(DISCORD_WEBHOOK, json={"content": message})

# -------------------- Arbitrage Calculation --------------------
def calc_arbitrage(odds):
    return sum([1/o for o in odds])  # <1 means profit

def calc_stakes(total_stake, odds):
    arb_percent = calc_arbitrage(odds)
    stakes = [(total_stake * (1/o) / arb_percent) for o in odds]
    profit = (total_stake / arb_percent) - total_stake
    return stakes, profit

def detect_surebets(data):
    surebets = []
    for event in data:
        if "bookmakers" not in event or not isinstance(event["bookmakers"], list) or len(event["bookmakers"]) == 0:
            continue
        odds_map = {}
        for book in event['bookmakers']:
            if "markets" not in book or len(book['markets']) == 0:
                continue
            for outcome in book['markets'][0].get('outcomes', []):
                odds_map.setdefault(outcome['name'], []).append((book['title'], outcome['price']))
        market_outcomes = list(odds_map.keys())
        if len(market_outcomes) >= 2:
            best_odds = [max(odds_map[o], key=lambda x: x[1]) for o in market_outcomes]
            arb_percent = calc_arbitrage([odd for _, odd in best_odds])
            if arb_percent < 1:
                stakes, profit = calc_stakes(100, [odd for _, odd in best_odds])
                surebets.append({
                    "event": f"{event.get('home_team', 'Unknown')} vs {event.get('away_team', 'Unknown')}",
                    "market": f"{len(market_outcomes)}-way",
                    "best_odds": best_odds,
                    "arb%": arb_percent,
                    "stakes": (stakes, profit)
                })
    return surebets

# -------------------- Middles --------------------
def calc_middle_stakes(over_odds, under_odds, base_stake=100):
    under_stake = (base_stake * over_odds) / under_odds
    return round(base_stake, 2), round(under_stake, 2)

def detect_middles(data):
    middles = []
    for event in data:
        spreads = []
        for book in event['bookmakers']:
            for market in book['markets']:
                if market['key'] == "totals":
                    odds = [(o['name'], o['price'], o['point']) for o in market['outcomes']]
                    spreads.append((book['title'], odds))
        if len(spreads) >= 2:
            for i in range(len(spreads)):
                for j in range(i+1, len(spreads)):
                    gap = abs(spreads[i][1][0][2] - spreads[j][1][0][2])
                    if gap >= 2:
                        over_odds = spreads[i][1][0][1]
                        under_odds = spreads[j][1][1][1]
                        over_stake, under_stake = calc_middle_stakes(over_odds, under_odds)
                        middles.append({
                            "event": f"{event['home_team']} vs {event['away_team']}",
                            "gap": gap,
                            "over_book": spreads[i][0],
                            "under_book": spreads[j][0],
                            "over": spreads[i][1],
                            "under": spreads[j][1],
                            "stakes": (over_stake, under_stake)
                        })
    return middles

# -------------------- AFK Loop --------------------
def run_afk_loop(interval=300):
    while True:
        print("🔄 Fetching live odds...")
        data = fetch_odds()

        # Surebets
        surebets = detect_surebets(data)
        for sb in surebets:
            msg = (f"💸 Surebet: {sb['event']} | Arb%: {round(sb['arb%']*100,2)}%\n"
                   f"Profit: ${round(sb['stakes'][1],2)} guaranteed")
            print(msg)
            send_discord_alert(msg)

        # Middles
        middles = detect_middles(data)
        for mid in middles:
            msg = (f"🔥 Middle Found: {mid['event']} | Gap: {mid['gap']} pts\n"
                   f"{mid['over_book']}: {mid['over']}\n"
                   f"{mid['under_book']}: {mid['under']}\n"
                   f"Stakes: Over ${mid['stakes'][0]} | Under ${mid['stakes'][1]}")
            print(msg)
            send_discord_alert(msg)

        print(f"Waiting {interval/60} min...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_afk_loop(interval=300)  # 5 min loop
