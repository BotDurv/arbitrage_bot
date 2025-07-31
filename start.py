import requests
import pandas as pd

API_KEY = "c347451c4dcd5b8b0266f0cd462070b9"  # Get from https://theoddsapi.com/
SPORT = "aussierules_afl"       # Change to soccer_epl, tennis_atp, etc.
REGION = "au"                  # 'au' (Australia), 'uk', 'eu', 'us'
MARKETS = "h2h,totals"         # h2h = moneyline, totals = over/under


def fetch_odds():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds/"
    params = {"apiKey": API_KEY, "regions": REGION, "markets": MARKETS}
    response = requests.get(url, params=params)

    try:
        data = response.json()
    except Exception as e:
        print(f"❌ Error decoding JSON: {e}")
        return []

    if isinstance(data, dict) and "message" in data:
        print(f"❌ API Error: {data['message']}")
        return []

    return data


def list_sports():
    url = f"https://api.the-odds-api.com/v4/sports/"
    params = {"apiKey": API_KEY}
    response = requests.get(url, params=params)
    print(response.json())

list_sports()


def calc_arbitrage(odds):
    inv_sum = sum([1/o for o in odds])
    return inv_sum  # <1 means profit


def calc_stakes(total_stake, odds):
    arb_percent = calc_arbitrage(odds)
    stakes = [(total_stake * (1/o) / arb_percent) for o in odds]
    profit = (total_stake / arb_percent) - total_stake
    return stakes, profit


def detect_surebets(data):
    surebets = []
    for event in data:
        # ✅ Skip invalid events
        if "bookmakers" not in event or not isinstance(event["bookmakers"], list) or len(event["bookmakers"]) == 0:
            continue

        odds_map = {}
        for book in event['bookmakers']:
            if "markets" not in book or len(book['markets']) == 0:
                continue

            for outcome in book['markets'][0].get('outcomes', []):
                odds_map.setdefault(outcome['name'], []).append((book['title'], outcome['price']))

        # ✅ Check if at least 2 outcomes exist
        market_outcomes = list(odds_map.keys())
        if len(market_outcomes) >= 2:
            best_odds = [max(odds_map[o], key=lambda x: x[1]) for o in market_outcomes]
            arb_percent = calc_arbitrage([odd for _, odd in best_odds])

            if arb_percent < 1:
                stakes, profit = calc_stakes(100, [odd for _, odd in best_odds])
                surebets.append({
                    "event": event.get('home_team', 'Unknown') + " vs " + event.get('away_team', 'Unknown'),
                    "market": f"{len(market_outcomes)}-way",
                    "best_odds": best_odds,
                    "arb%": arb_percent,
                    "stakes": (stakes, profit)
                })

    return surebets


def calc_middle_stakes(over_odds, under_odds, base_stake=100):
    # Stake to equalize potential payouts
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
                            "event": event['home_team'] + " vs " + event['away_team'],
                            "gap": gap,
                            "over_book": spreads[i][0],
                            "under_book": spreads[j][0],
                            "over": spreads[i][1],
                            "under": spreads[j][1],
                            "stakes": (over_stake, under_stake)
                        })
    return middles


def main():
    print("Fetching live odds...")
    data = fetch_odds()

    print("\n📊 Raw API Response:")
    print(data)
    
    print("\n🔎 Surebets Found:")
    surebets = detect_surebets(data)
    for sb in surebets:
        print(f"\n{sb['event']} | {sb['market']} | Arb%: {round(sb['arb%']*100,2)}%")
        for (book, odd), stake in zip(sb['best_odds'], sb['stakes'][0]):
            print(f"- Bet {round(stake,2)} on {book} @ {odd}")
        print(f"💰 Profit: ${round(sb['stakes'][1],2)} guaranteed")

    print("\n🔎 Middles Found:")
    middles = detect_middles(data)
    for mid in middles:
        print(f"{mid['over_book']}: {mid['over']}")
    print(f"{mid['under_book']}: {mid['under']}")
    print(f"Recommended Stakes: Over ${mid['stakes'][0]} | Under ${mid['stakes'][1]}")


if __name__ == "__main__":
    main()
