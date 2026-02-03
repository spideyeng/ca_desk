import argparse
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.style.use("seaborn-v0_8")

DEFAULT_TICKERS = {
    "JKM": "JKM=F",
    "TTF": "TTF=F",
    "NBP": "NBP=F",
    "Brent": "BZ=F",
}

def fetch_prices(tickers, period):
    frames = []
    for name, ticker in tickers.items():
        df = yf.Ticker(ticker).history(period=period)["Close"].rename(name)
        frames.append(df)
    return pd.concat(frames, axis=1).dropna()

def compute_spreads(prices):
    spreads = pd.DataFrame(index=prices.index)
    spreads["JKM - TTF"] = prices["JKM"] - prices["TTF"]
    spreads["JKM - NBP"] = prices["JKM"] - prices["NBP"]
    spreads["TTF - NBP"] = prices["TTF"] - prices["NBP"]
    spreads["JKM - Brent (slope)"] = prices["JKM"] - prices["Brent"]
    return spreads

def compute_vol(prices, window):
    returns = prices.pct_change()
    return returns.rolling(window).std() * np.sqrt(252)

def run_dashboard(period, window):
    prices = fetch_prices(DEFAULT_TICKERS, period)
    spreads = compute_spreads(prices)
    vol = compute_vol(prices, window)
    corr = prices.pct_change().corr()

    return prices, spreads, vol, corr

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LNG Analytics Dashboard")
    parser.add_argument("--period", type=str, default="24mo",
                        help="History period (e.g., 12mo, 24mo, 5y)")
    parser.add_argument("--window", type=int, default=30,
                        help="Rolling volatility window")
    args = parser.parse_args()

    prices, spreads, vol, corr = run_dashboard(args.period, args.window)

    print("\n=== LNG Dashboard Run Complete ===")
    print(f"Period: {args.period}")
    print(f"Rolling Vol Window: {args.window} days\n")