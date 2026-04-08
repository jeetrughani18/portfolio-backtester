import streamlit as st
import pandas as pd
from datetime import date, timedelta
from backend.backtest_engine import run_backtest, BacktestError, BENCHMARKS

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
    
    # Manual date inputs
    st.subheader("Backtest Period")
    default_start = date.today() - timedelta(days=365)
    start_date = st.date_input("Start Date", value=default_start)
    end_date = st.date_input("End Date", value=date.today())
    
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
                    start_date_str=start_date.strftime("%Y-%m-%d"),
                    end_date_str=end_date.strftime("%Y-%m-%d"),
                    risk_free_rate_pct=risk_free_rate
                )
                
                info = results["info"]
                liquid_msg = f"Allocated **{info['liquid_weight']*100:.2f}%** to Liquid Fund." if info["liquid_weight"] > 0 else ""
                st.info(f"Loaded **{info['total_stocks_loaded']}** stocks. {liquid_msg} Period: **{info['period_label']}**")
                
                # Render Metrics Dashboard
                st.subheader("Performance Metrics")
                cols = st.columns(len(results["metrics"]))
                for i, metric in enumerate(results["metrics"]):
                    with cols[i]:
                        st.metric(
                            label=metric["name"], 
                            value=metric["portfolio"], 
                            delta=f"Bench: {metric['benchmark']}",
                            delta_color="off"
                        )
                
                # Render Relative Metrics (IR, Tracking Error, Beta)
                st.subheader(f"Relative Metrics (Portfolio vs {info['benchmark_name']})")
                rel_cols = st.columns(len(results["relative_metrics"]))
                for i, rm in enumerate(results["relative_metrics"]):
                    with rel_cols[i]:
                        st.metric(label=rm["name"], value=rm["value"])
                
                # Render Chart
                st.subheader("NAV Performance (Base 100)")
                df_chart = pd.DataFrame(results["chart_data"])
                df_chart["Date"] = pd.to_datetime(df_chart["Date"])
                df_chart.set_index("Date", inplace=True)
                st.line_chart(df_chart, use_container_width=True)
                
                # Render Correlation Matrix
                st.subheader("Correlation Matrix (Daily Returns)")
                df_corr = pd.DataFrame(results["correlation_matrix"])
                df_corr = df_corr.set_index("Stock")
                st.dataframe(df_corr, use_container_width=True)
                
                # Render Logs
                if results["logs"]:
                    with st.expander("View Event Logs"):
                        for log in results["logs"]:
                            st.text(log)
                            
                # Expose CSV Downloads
                st.subheader("Download Data")
                dl_col1, dl_col2, dl_col3 = st.columns(3)
                
                # Results CSV (including relative metrics)
                df_metrics = pd.DataFrame(results["metrics"])
                df_metrics = df_metrics.rename(columns={"name": "Metric", "portfolio": "Portfolio", "benchmark": "Benchmark"})
                df_rel = pd.DataFrame(results["relative_metrics"])
                df_rel = df_rel.rename(columns={"name": "Metric", "value": "Portfolio"})
                df_rel["Benchmark"] = "—"
                df_all_metrics = pd.concat([df_metrics, df_rel], ignore_index=True)
                csv_metrics = df_all_metrics.to_csv(index=False).encode('utf-8')
                
                dl_col1.download_button(
                    label="📥 Results CSV",
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
                    label="📥 NAV CSV",
                    data=csv_nav,
                    file_name='nav_series.csv',
                    mime='text/csv',
                    use_container_width=True
                )
                
                # Correlation Matrix CSV
                csv_corr = df_corr.to_csv().encode('utf-8')
                dl_col3.download_button(
                    label="📥 Correlation CSV",
                    data=csv_corr,
                    file_name='correlation_matrix.csv',
                    mime='text/csv',
                    use_container_width=True
                )
                
            except BacktestError as e:
                st.error(f"Backtest Error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
