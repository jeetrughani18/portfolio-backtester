import io
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date, datetime

LIQUID_FUND_TICKER = "0P0001BB41.BO"
LIQUID_FUND_LABEL = "LIQUIDFUND"

BENCHMARKS = {
    "1": ("Nifty 50",  "^NSEI"),
    "2": ("Nifty 100", "^CNX100"),
    "3": ("Nifty 200", "^CNX200"),
    "4": ("Nifty 500", "^CRSLDX"),
    "5": ("BSE 500",   "BSE-500.BO"),
}

class BacktestError(Exception):
    pass

def read_portfolio(file_bytes: bytes) -> tuple[pd.DataFrame, float]:
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise BacktestError(f"Failed to read CSV: {str(e)}")

    df.columns = df.columns.str.strip()
    if "Symbol" not in df.columns or "Weight" not in df.columns:
        raise BacktestError("CSV must contain 'Symbol' and 'Weight' columns.")

    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df = df.dropna(subset=["Symbol", "Weight"])
    df = df[df["Symbol"] != ""]

    total = df["Weight"].sum()
    if total <= 0:
        raise BacktestError("Portfolio weights sum to zero or negative.")

    if total > 1.0:
        df["Weight"] = df["Weight"] / total
        liquid_weight = 0.0
    else:
        liquid_weight = round(1.0 - total, 6)

    return df.reset_index(drop=True), liquid_weight

def download_data(symbols: list[str], benchmark_ticker: str, start_date: date, end_date: date, liquid_weight: float = 0.0):
    nse_tickers = [s + ".NS" for s in symbols]

    stock_data = yf.download(
        nse_tickers,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    if isinstance(stock_data.columns, pd.MultiIndex):
        stock_prices = stock_data["Close"]
    else:
        stock_prices = stock_data[["Close"]].copy()
        stock_prices.columns = [nse_tickers[0]]

    stock_prices.columns = [c.replace(".NS", "") for c in stock_prices.columns]

    if liquid_weight > 0:
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

    common_dates = stock_prices.index.intersection(bm_prices.index)
    stock_prices = stock_prices.loc[common_dates]
    bm_prices = bm_prices.loc[common_dates]

    stock_prices = stock_prices.ffill().dropna(how="all")
    bm_prices = bm_prices.loc[stock_prices.index].ffill().dropna()

    common = stock_prices.index.intersection(bm_prices.index)
    stock_prices = stock_prices.loc[common]
    bm_prices = bm_prices.loc[common]

    return stock_prices, bm_prices

def build_portfolio_nav(stock_prices: pd.DataFrame, weight_map: dict[str, float]) -> tuple[pd.Series, list[str]]:
    daily_returns = stock_prices.pct_change()
    nav = [100.0]
    dates = stock_prices.index
    entered = set()
    first_available = {}
    logs = []

    for sym in stock_prices.columns:
        valid = stock_prices[sym].dropna()
        if len(valid) >= 2:
            first_available[sym] = valid.index[1]

    for i in range(1, len(dates)):
        today = dates[i]
        available_today = set()
        for sym, dt in first_available.items():
            if today >= dt:
                available_today.add(sym)

        new_entries = available_today - entered
        if new_entries:
            for s in sorted(new_entries):
                logs.append(f"➕ {s} enters portfolio on {today.date().isoformat()}")
            entered = entered | new_entries

        if not available_today:
            nav.append(nav[-1])
            continue

        active_weights = {s: weight_map[s] for s in available_today if s in weight_map}
        unavailable = set(weight_map.keys()) - available_today
        extra_weight = sum(weight_map[s] for s in unavailable)

        if extra_weight > 0 and active_weights:
            redistribution = extra_weight / len(active_weights)
            for s in active_weights:
                active_weights[s] += redistribution

        w_sum = sum(active_weights.values())
        if w_sum > 0:
            active_weights = {s: w / w_sum for s, w in active_weights.items()}

        day_ret = 0.0
        for sym, w in active_weights.items():
            r = daily_returns.loc[today, sym]
            if pd.notna(r):
                day_ret += w * r

        nav.append(nav[-1] * (1 + day_ret))

    nav_series = pd.Series(nav, index=dates, name="Portfolio_NAV")
    return nav_series, logs

def build_benchmark_nav(bm_prices: pd.Series) -> pd.Series:
    returns = bm_prices.pct_change().fillna(0)
    nav = 100.0 * (1 + returns).cumprod()
    nav.name = "Benchmark_NAV"
    return nav

def compute_metrics(nav_series: pd.Series, risk_free_rate: float) -> dict:
    daily_returns = nav_series.pct_change().dropna()
    if len(daily_returns) == 0:
        return {"Absolute Return (%)": 0, "CAGR (%)": 0, "Sharpe Ratio": 0, "Sortino Ratio": 0, "Max Drawdown (%)": 0}

    n_days = (nav_series.index[-1] - nav_series.index[0]).days

    total_return = nav_series.iloc[-1] / nav_series.iloc[0]
    if n_days > 0:
        cagr = total_return ** (365.0 / n_days) - 1
    else:
        cagr = 0.0

    absolute_return = ((nav_series.iloc[-1] - nav_series.iloc[0]) / nav_series.iloc[0]) * 100
    ann_vol = daily_returns.std() * np.sqrt(252) * 100

    sharpe = (cagr * 100 - risk_free_rate * 100) / ann_vol if ann_vol != 0 else 0.0

    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std() * np.sqrt(252) * 100 if len(downside) > 0 else 0.0
    sortino = (cagr * 100 - risk_free_rate * 100) / downside_std if downside_std != 0 else 0.0

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

    common = port_ret.index.intersection(bm_ret.index)
    port_ret = port_ret.loc[common]
    bm_ret = bm_ret.loc[common]

    excess = port_ret - bm_ret

    tracking_error = excess.std()

    if tracking_error != 0:
        ir = excess.mean() / tracking_error
    else:
        ir = 0.0

    cov = np.cov(port_ret, bm_ret)[0, 1]
    var_bm = np.var(bm_ret, ddof=1)
    beta = cov / var_bm if var_bm != 0 else 0.0

    return {
        "Tracking Error":      round(tracking_error * 100, 4),
        "Information Ratio":   round(ir, 4),
        "Beta":                round(beta, 4),
    }

def compute_correlation_matrix(stock_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute the correlation matrix of daily returns across all stocks."""
    daily_returns = stock_prices.pct_change().dropna(how="all")
    return daily_returns.corr().round(4)

def run_backtest(file_bytes: bytes, benchmark_id: str, start_date_str: str, end_date_str: str, risk_free_rate_pct: float):
    if benchmark_id not in BENCHMARKS:
        raise BacktestError("Invalid benchmark selection.")

    bm_name, bm_ticker = BENCHMARKS[benchmark_id]

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise BacktestError("Invalid start date format. Use YYYY-MM-DD.")

    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise BacktestError("Invalid end date format. Use YYYY-MM-DD.")

    if start_date >= end_date:
        raise BacktestError("Start date must be before end date.")

    if end_date > date.today():
        raise BacktestError("End date cannot be in the future.")

    period_label = f"{start_date} → {end_date}"
    risk_free_rate = risk_free_rate_pct / 100.0

    portfolio, liquid_weight = read_portfolio(file_bytes)
    symbols = portfolio["Symbol"].tolist()
    weight_map = dict(zip(portfolio["Symbol"], portfolio["Weight"]))

    if liquid_weight > 0:
        weight_map[LIQUID_FUND_LABEL] = liquid_weight

    stock_prices, bm_prices = download_data(symbols, bm_ticker, start_date, end_date, liquid_weight)

    all_syms = symbols + ([LIQUID_FUND_LABEL] if liquid_weight > 0 else [])
    available_syms = [s for s in all_syms if s in stock_prices.columns]
    if not available_syms:
        raise BacktestError("No stock data available for the selected period.")

    portfolio_nav, logs = build_portfolio_nav(stock_prices, weight_map)
    benchmark_nav = build_benchmark_nav(bm_prices)

    port_metrics = compute_metrics(portfolio_nav, risk_free_rate)
    bm_metrics = compute_metrics(benchmark_nav, risk_free_rate)
    rel_metrics = compute_relative_metrics(portfolio_nav, benchmark_nav)
    corr_matrix = compute_correlation_matrix(stock_prices)

    # Format chart data for Recharts
    df_chart = pd.DataFrame({
        "Date": portfolio_nav.index.strftime("%Y-%m-%d"),
        "Portfolio": portfolio_nav.values.round(4),
        "Benchmark": benchmark_nav.values.round(4)
    })
    chart_data = df_chart.to_dict(orient="records")

    # Combine metrics into a frontend-friendly format
    metrics = []
    for key in port_metrics.keys():
        metrics.append({
            "name": key,
            "portfolio": port_metrics[key],
            "benchmark": bm_metrics[key]
        })

    # Relative metrics (portfolio-only values)
    relative_metrics = []
    for key in rel_metrics.keys():
        relative_metrics.append({
            "name": key,
            "value": rel_metrics[key]
        })

    # Correlation matrix as list of dicts for frontend
    corr_data = corr_matrix.reset_index()
    corr_data = corr_data.rename(columns={corr_data.columns[0]: "Stock"})
    corr_records = corr_data.to_dict(orient="records")

    return {
        "metrics": metrics,
        "relative_metrics": relative_metrics,
        "correlation_matrix": corr_records,
        "correlation_columns": list(corr_matrix.columns),
        "chart_data": chart_data,
        "logs": logs,
        "info": {
            "benchmark_name": bm_name,
            "period_label": period_label,
            "risk_free_rate": risk_free_rate_pct,
            "liquid_weight": liquid_weight,
            "total_stocks_loaded": len(portfolio)
        }
    }
