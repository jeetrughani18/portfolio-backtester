import streamlit as st
import pandas as pd
from backend.backtest_engine import run_backtest, BacktestError, BENCHMARKS, PERIODS

st.set_page_config(page_title="Portfolio Backtester", layout="wide", page_icon="📈")

st.title("📈 Portfolio Backtester")
st.markdown("Upload your portfolio CSV to view performance metrics, NAV charts, and drawdowns against a benchmark.")

# Sidebar Configuration
with st.sidebar:
    st.header("Upload Portfolio")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    st.header("Configuration")
    
    # Extract keys and labels for the benchmark selectbox
    benchmark_options = {k: v[0] for k, v in BENCHMARKS.items()}
    selected_benchmark_key = st.selectbox(
        "Benchmark Index", 
        options=list(benchmark_options.keys()), 
        format_func=lambda x: benchmark_options[x]
    )
    
    # Extract keys and labels for the period selectbox
    period_options = {k: v[0] for k, v in PERIODS.items()}
    selected_period_key = st.selectbox(
        "Backtest Period", 
        options=list(period_options.keys()), 
        format_func=lambda x: period_options[x],
        index=3  # Default to 1 Year (which is the 4th item)
    )
    
    risk_free_rate = st.number_input("Risk-Free Rate (%)", value=7.0, step=0.1)
    
    run_button = st.button("Run Backtest", type="primary", use_container_width=True)

if run_button:
    if uploaded_file is None:
        st.error("Please upload a CSV file to run the backtest.")
    else:
        with st.spinner("Running Backtest and Fetching Data..."):
            try:
                # Read bytes from the uploaded file
                file_bytes = uploaded_file.getvalue()
                
                # Call the existing logic
                results = run_backtest(
                    file_bytes=file_bytes,
                    benchmark_id=selected_benchmark_key,
                    period_id=selected_period_key,
                    risk_free_rate_pct=risk_free_rate
                )
                
                info = results["info"]
                liquid_msg = f"Allocated **{info['liquid_weight']*100:.2f}%** to Liquid Fund." if info["liquid_weight"] > 0 else ""
                st.info(f"Loaded **{info['total_stocks_loaded']}** stocks. {liquid_msg}")
                
                # Render Metrics Dashboard
                cols = st.columns(len(results["metrics"]))
                for i, metric in enumerate(results["metrics"]):
                    with cols[i]:
                        st.metric(
                            label=metric["name"], 
                            value=metric["portfolio"], 
                            delta=f"Bench: {metric['benchmark']}",
                            delta_color="off" # Just displaying it as grey
                        )
                
                # Render Chart
                st.subheader("NAV Performance (Base 100)")
                df_chart = pd.DataFrame(results["chart_data"])
                df_chart["Date"] = pd.to_datetime(df_chart["Date"])
                df_chart.set_index("Date", inplace=True)
                st.line_chart(df_chart, use_container_width=True)
                
                # Render Logs
                if results["logs"]:
                    with st.expander("View Event Logs"):
                        for log in results["logs"]:
                            st.text(log)
                            
                # Expose CSV Downloads
                st.subheader("Download Data")
                dl_col1, dl_col2 = st.columns(2)
                
                # Results CSV
                df_metrics = pd.DataFrame(results["metrics"])
                df_metrics = df_metrics.rename(columns={"name": "Metric", "portfolio": "Portfolio", "benchmark": "Benchmark"})
                csv_metrics = df_metrics.to_csv(index=False).encode('utf-8')
                
                dl_col1.download_button(
                    label="📥 Download Results CSV",
                    data=csv_metrics,
                    file_name='backtest_results.csv',
                    mime='text/csv',
                    use_container_width=True
                )
                
                # NAV CSV
                df_nav = pd.DataFrame(results["chart_data"]).rename(columns={"Portfolio": "NAV_Portfolio", "Benchmark": "NAV_Benchmark"})
                df_nav = df_nav[["Date", "NAV_Portfolio", "NAV_Benchmark"]]
                csv_nav = df_nav.to_csv(index=False).encode('utf-8')
                
                dl_col2.download_button(
                    label="📥 Download NAV CSV",
                    data=csv_nav,
                    file_name='nav_series.csv',
                    mime='text/csv',
                    use_container_width=True
                )
                
            except BacktestError as e:
                st.error(f"Backtest Error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
