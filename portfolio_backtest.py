"""
Portfolio Backtesting Script
============================
Reads stock weights from a CSV, downloads NSE price data via yfinance,
constructs a NAV series with dynamic weight redistribution for stocks
with partial data, and computes risk/return metrics vs a benchmark.
"""

import os
import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date
from dateutil.relativedelta import relativedelta

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(SCRIPT_DIR, "ivcapital pms.csv")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "backtest_results.csv")
NAV_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "nav_series.csv")
CORR_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "correlation_matrix.csv")
LIQUID_FUND_TICKER = "0P0001BB41.BO"
LIQUID_FUND_LABEL = "LIQUIDFUND"

BENCHMARKS = {
    "1": ("Nifty 50",  "^NSEI"),
    "2": ("Nifty 100", "^CNX100"),
    "3": ("Nifty 200", "^CNX200"),
    "4": ("Nifty 500", "^CRSLDX"),
    "5": ("BSE 500",   "BSE-500.BO"),
}

PERIODS = {
    "1": ("1 Month",  relativedelta(months=1)),
    "2": ("3 Months", relativedelta(months=3)),
    "3": ("6 Months", relativedelta(months=6)),
    "4": ("1 Year",   relativedelta(years=1)),
    "5": ("3 Years",  relativedelta(years=3)),
    "6": ("5 Years",  relativedelta(years=5)),
}


# ──────────────────────────────────────────────
# 1. Read & clean CSV
# ──────────────────────────────────────────────
def read_portfolio(csv_path: str) -> tuple[pd.DataFrame, float]:
    """Read the portfolio CSV. If weights sum to < 1, remainder goes to liquid fund."""
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df = df.dropna(subset=["Symbol", "Weight"])
    df = df[df["Symbol"] != ""]

    total = df["Weight"].sum()
    if total <= 0:
        sys.exit("ERROR: Portfolio weights sum to zero or negative.")
    if total > 1.0:
        print(f"\n⚠  Weights sum to {total:.4f} (> 1.0) — normalising to 1.0")
        df["Weight"] = df["Weight"] / total
        liquid_weight = 0.0
    else:
        liquid_weight = round(1.0 - total, 6)

    print(f"\n📄 Loaded {len(df)} stocks from {os.path.basename(csv_path)}")
    print(f"   Stock weights sum  = {total:.4f}")
    if liquid_weight > 0:
        print(f"   Liquid fund weight = {liquid_weight:.4f}  ({LIQUID_FUND_TICKER})")
    print()
    return df.reset_index(drop=True), liquid_weight


# ──────────────────────────────────────────────
# 2. User inputs
# ──────────────────────────────────────────────
def get_user_inputs():
    """Prompt for benchmark, period, and risk-free rate."""

    # Benchmark
    print("Select a benchmark index:")
    for key, (name, _) in BENCHMARKS.items():
        print(f"  {key}. {name}")
    bm_choice = input("Enter choice (1-5): ").strip()
    if bm_choice not in BENCHMARKS:
        sys.exit("Invalid benchmark selection.")
    bm_name, bm_ticker = BENCHMARKS[bm_choice]

    # Period
    print("\nSelect backtest period:")
    for key, (label, _) in PERIODS.items():
        print(f"  {key}. {label}")
    pd_choice = input("Enter choice (1-6): ").strip()
    if pd_choice not in PERIODS:
        sys.exit("Invalid period selection.")
    period_label, delta = PERIODS[pd_choice]
    end_date = date.today()
    start_date = end_date - delta

    # Risk-free rate
    rf_input = input("\nEnter risk-free rate (%, e.g. 7 for 7%): ").strip()
    try:
        risk_free_rate = float(rf_input) / 100.0
    except ValueError:
        sys.exit("Invalid risk-free rate.")

    print(f"\n── Settings ──────────────────────────────")
    print(f"   Benchmark   : {bm_name} ({bm_ticker})")
    print(f"   Period       : {period_label}  ({start_date} → {end_date})")
    print(f"   Risk-Free    : {risk_free_rate*100:.2f}%")
    print(f"──────────────────────────────────────────\n")

    return bm_ticker, bm_name, start_date, end_date, risk_free_rate, period_label


# ──────────────────────────────────────────────
# 3. Download price data
# ──────────────────────────────────────────────
def download_data(symbols: list[str], benchmark_ticker: str,
                  start_date: date, end_date: date,
                  liquid_weight: float = 0.0):
    """Download adjusted close prices for all stocks, liquid fund, and benchmark."""

    nse_tickers = [s + ".NS" for s in symbols]

    print("⬇  Downloading stock data …")
    stock_data = yf.download(
        nse_tickers,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    # yf.download returns multi-level columns when multiple tickers
    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_prices = stock_data["Close"]
    else:
        # single ticker edge case
        stock_prices = stock_data[["Close"]].copy()
        stock_prices.columns = [nse_tickers[0]]

    # Rename columns back to base symbols for convenience
    stock_prices.columns = [c.replace(".NS", "") for c in stock_prices.columns]

    # Download liquid fund data if needed
    if liquid_weight > 0:
        print(f"⬇  Downloading liquid fund data ({LIQUID_FUND_TICKER}) …")
        lf_data = yf.download(
            LIQUID_FUND_TICKER,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=True,
            progress=False,
        )
        if isinstance(lf_data.columns, pd.MultiIndex):
            lf_prices = lf_data["Close"].squeeze()
        else:
            lf_prices = lf_data["Close"].squeeze()
        lf_prices.name = LIQUID_FUND_LABEL
        stock_prices = stock_prices.join(lf_prices, how="outer")

    print("⬇  Downloading benchmark data …")
    bm_data = yf.download(
        benchmark_ticker,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    if isinstance(bm_data.columns, pd.MultiIndex):
        bm_prices = bm_data["Close"].squeeze()
    else:
        bm_prices = bm_data["Close"].squeeze()

    # Align on common dates
    common_dates = stock_prices.index.intersection(bm_prices.index)
    stock_prices = stock_prices.loc[common_dates]
    bm_prices = bm_prices.loc[common_dates]

    # Forward-fill small gaps, then drop rows that are entirely NaN
    stock_prices = stock_prices.ffill()
    stock_prices = stock_prices.dropna(how="all")
    bm_prices = bm_prices.loc[stock_prices.index].ffill().dropna()

    # Re-align after drops
    common = stock_prices.index.intersection(bm_prices.index)
    stock_prices = stock_prices.loc[common]
    bm_prices = bm_prices.loc[common]

    print(f"   {len(stock_prices)} trading days loaded.\n")
    return stock_prices, bm_prices


# ──────────────────────────────────────────────
# 4. Portfolio NAV with dynamic weight handling
# ──────────────────────────────────────────────
def build_portfolio_nav(stock_prices: pd.DataFrame,
                        weight_map: dict[str, float]) -> pd.Series:
    """
    Build a NAV series starting at 100.

    Rules:
    - Stocks without data at the start are excluded; their weight is
      redistributed equally among available stocks.
    - When an excluded stock's data appears, it enters at its original
      weight and the other weights are scaled down proportionally.
    """
    daily_returns = stock_prices.pct_change()
    nav = [100.0]
    dates = stock_prices.index

    # Track which stocks have "entered" the portfolio
    entered = set()
    first_available = {}

    # Determine the first available date for each stock
    for sym in stock_prices.columns:
        valid = stock_prices[sym].dropna()
        if len(valid) >= 2:
            # Need at least 2 data points to compute a return
            first_available[sym] = valid.index[1]  # first return date

    print("📊 Stock data availability:")
    for sym in sorted(weight_map.keys()):
        if sym in first_available:
            print(f"   {sym:>15s}  →  available from {first_available[sym].date()}"
                  f"  (original wt: {weight_map[sym]*100:.2f}%)")
        else:
            print(f"   {sym:>15s}  →  ❌ NO usable data")
    print()

    for i in range(1, len(dates)):
        today = dates[i]

        # Determine which stocks are available today
        available_today = set()
        for sym, dt in first_available.items():
            if today >= dt:
                available_today.add(sym)

        # Detect newly entering stocks
        new_entries = available_today - entered

        if new_entries:
            for s in sorted(new_entries):
                print(f"   ➕ {s} enters portfolio on {today.date()}")
            entered = entered | new_entries

        # Build effective weights for today
        if not available_today:
            # No stocks available yet, NAV stays flat
            nav.append(nav[-1])
            continue

        # Start with original weights for available stocks
        active_weights = {s: weight_map[s] for s in available_today if s in weight_map}

        # Stocks that are NOT yet available
        unavailable = set(weight_map.keys()) - available_today
        extra_weight = sum(weight_map[s] for s in unavailable)

        if extra_weight > 0 and active_weights:
            # Redistribute the unavailable weight equally among active stocks
            redistribution = extra_weight / len(active_weights)
            for s in active_weights:
                active_weights[s] += redistribution

        # Normalise to 1.0 (safety)
        w_sum = sum(active_weights.values())
        if w_sum > 0:
            active_weights = {s: w / w_sum for s, w in active_weights.items()}

        # Compute weighted return
        day_ret = 0.0
        for sym, w in active_weights.items():
            r = daily_returns.loc[today, sym]
            if pd.notna(r):
                day_ret += w * r

        nav.append(nav[-1] * (1 + day_ret))

    nav_series = pd.Series(nav, index=dates, name="Portfolio_NAV")
    return nav_series


def build_benchmark_nav(bm_prices: pd.Series) -> pd.Series:
    """Simple NAV series starting at 100 from benchmark prices."""
    returns = bm_prices.pct_change().fillna(0)
    nav = 100.0 * (1 + returns).cumprod()
    nav.name = "Benchmark_NAV"
    return nav


# ──────────────────────────────────────────────
# 5. Performance metrics
# ──────────────────────────────────────────────
def compute_metrics(nav_series: pd.Series, risk_free_rate: float) -> dict:
    """Compute CAGR, Sharpe, Sortino, Max Drawdown from a NAV series."""

    daily_returns = nav_series.pct_change().dropna()
    n_days = (nav_series.index[-1] - nav_series.index[0]).days

    # CAGR
    total_return = nav_series.iloc[-1] / nav_series.iloc[0]
    if n_days > 0:
        cagr = total_return ** (365.0 / n_days) - 1
    else:
        cagr = 0.0

    # Absolute Return (%)
    absolute_return = ((nav_series.iloc[-1] - nav_series.iloc[0]) / nav_series.iloc[0]) * 100

    # Annualised volatility (from daily returns) — expressed in % for consistency
    ann_vol = daily_returns.std() * np.sqrt(252) * 100

    # Use annualised excess return in numerator
    sharpe = (cagr * 100 - risk_free_rate * 100) / ann_vol if ann_vol != 0 else 0.0

    # Sortino Ratio
    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std() * np.sqrt(252) * 100 if len(downside) > 0 else 0.0
    sortino = (cagr * 100 - risk_free_rate * 100) / downside_std if downside_std != 0 else 0.0

    # Maximum Drawdown
    cumulative_max = nav_series.cummax()
    drawdown = (nav_series - cumulative_max) / cumulative_max
    max_dd = drawdown.min()

    return {
        "Absolute Return (%)": round(absolute_return, 2),
        "CAGR (%)":            round(cagr * 100, 2),
        "Sharpe Ratio":        round(sharpe, 4),
        "Sortino Ratio":       round(sortino, 4),
        "Max Drawdown (%)":    round(max_dd * 100, 2),
    }


def compute_relative_metrics(portfolio_nav: pd.Series,
                             benchmark_nav: pd.Series) -> dict:
    """
    Compute metrics that require both portfolio and benchmark NAV:
      - Tracking Error = std(excess)
      - Information Ratio = mean(excess) / std(excess)
      - Beta = Cov(Rp, Rb) / Var(Rb)
    """
    port_ret = portfolio_nav.pct_change().dropna()
    bm_ret = benchmark_nav.pct_change().dropna()

    # Align on common dates
    common = port_ret.index.intersection(bm_ret.index)
    port_ret = port_ret.loc[common]
    bm_ret = bm_ret.loc[common]

    # Excess returns (daily)
    excess = port_ret - bm_ret

    # Tracking Error
    tracking_error = excess.std()

    # Information Ratio
    if tracking_error != 0:
        ir = excess.mean() / tracking_error
    else:
        ir = 0.0

    # Beta = Cov(Rp, Rm) / Var(Rm)
    cov = np.cov(port_ret, bm_ret)[0, 1]
    var_bm = np.var(bm_ret, ddof=1)
    beta = cov / var_bm if var_bm != 0 else 0.0

    return {
        "Tracking Error":      round(tracking_error * 100, 4),   # in %
        "Information Ratio":   round(ir, 4),
        "Beta":                round(beta, 4),
    }


def compute_correlation_matrix(stock_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the correlation matrix of daily returns across all stocks
    in the portfolio.
    """
    daily_returns = stock_prices.pct_change().dropna()
    return daily_returns.corr().round(4)


# ──────────────────────────────────────────────
# 6. Display & save results
# ──────────────────────────────────────────────
def display_results(portfolio_metrics: dict, benchmark_metrics: dict,
                    relative_metrics: dict, corr_matrix: pd.DataFrame,
                    bm_name: str, period_label: str, risk_free_rate: float):
    """Print a formatted table and save to CSV."""

    print("=" * 60)
    print(f"  BACKTEST RESULTS  —  {period_label}")
    print(f"  Benchmark: {bm_name}  |  Risk-Free Rate: {risk_free_rate*100:.2f}%")
    print("=" * 60)
    print(f"  {'Metric':<22s} {'Portfolio':>14s} {'Benchmark':>14s}")
    print("-" * 60)

    all_keys = list(portfolio_metrics.keys())
    for key in all_keys:
        pval = portfolio_metrics[key]
        bval = benchmark_metrics[key]
        print(f"  {key:<22s} {pval:>14} {bval:>14}")
    print("=" * 60)

    # Print relative metrics (portfolio vs benchmark)
    print(f"\n{'='*60}")
    print(f"  RELATIVE METRICS  (Portfolio vs {bm_name})")
    print(f"{'='*60}")
    print(f"  {'Metric':<22s} {'Value':>14s}")
    print("-" * 60)
    for key, val in relative_metrics.items():
        print(f"  {key:<22s} {val:>14}")
    print("=" * 60)

    # Print correlation matrix
    print(f"\n{'='*60}")
    print(f"  CORRELATION MATRIX  (Daily Returns)")
    print(f"{'='*60}")
    print(corr_matrix.to_string())
    print("=" * 60)

    # Save results to CSV (including relative metrics)
    results_rows = []
    for key in all_keys:
        results_rows.append({
            "Metric": key,
            "Portfolio": portfolio_metrics[key],
            "Benchmark": benchmark_metrics[key],
        })
    for key, val in relative_metrics.items():
        results_rows.append({
            "Metric": key,
            "Portfolio": val,
            "Benchmark": "—",
        })
    results_df = pd.DataFrame(results_rows)
    results_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n💾 Results saved to {OUTPUT_FILE}")

    # Save correlation matrix
    corr_matrix.to_csv(CORR_OUTPUT_FILE)
    print(f"💾 Correlation matrix saved to {CORR_OUTPUT_FILE}\n")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    # 1. Read portfolio
    portfolio, liquid_weight = read_portfolio(CSV_FILE)
    symbols = portfolio["Symbol"].tolist()
    weight_map = dict(zip(portfolio["Symbol"], portfolio["Weight"]))

    # Add liquid fund to weight map if applicable
    if liquid_weight > 0:
        weight_map[LIQUID_FUND_LABEL] = liquid_weight

    # 2. User inputs
    bm_ticker, bm_name, start_date, end_date, risk_free_rate, period_label = (
        get_user_inputs()
    )

    # 3. Download data
    stock_prices, bm_prices = download_data(
        symbols, bm_ticker, start_date, end_date, liquid_weight
    )

    # Check that we have at least some stock data
    all_syms = symbols + ([LIQUID_FUND_LABEL] if liquid_weight > 0 else [])
    available_syms = [s for s in all_syms if s in stock_prices.columns]
    if not available_syms:
        sys.exit("ERROR: No stock data available for the selected period.")

    missing = set(all_syms) - set(available_syms)
    if missing:
        print(f"⚠  No data at all for: {', '.join(sorted(missing))}\n")

    # 4. Build NAV series
    portfolio_nav = build_portfolio_nav(stock_prices, weight_map)
    benchmark_nav = build_benchmark_nav(bm_prices)

    # Save NAV series to CSV
    nav_df = pd.DataFrame({
        "Date": portfolio_nav.index.strftime("%Y-%m-%d"),
        "NAV_Portfolio": portfolio_nav.values.round(4),
        "NAV_Benchmark": benchmark_nav.values.round(4),
    })
    nav_df.to_csv(NAV_OUTPUT_FILE, index=False)
    print(f"📈 NAV series saved to {NAV_OUTPUT_FILE}")

    # 5. Compute metrics
    port_metrics = compute_metrics(portfolio_nav, risk_free_rate)
    bm_metrics = compute_metrics(benchmark_nav, risk_free_rate)

    # 5b. Compute relative metrics (IR, Tracking Error, Beta)
    rel_metrics = compute_relative_metrics(portfolio_nav, benchmark_nav)

    # 5c. Compute correlation matrix of daily stock returns
    corr_matrix = compute_correlation_matrix(stock_prices)

    # 6. Display & save
    display_results(port_metrics, bm_metrics, rel_metrics, corr_matrix,
                    bm_name, period_label, risk_free_rate)


if __name__ == "__main__":
    main()
