from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import pandas as pd
from contextlib import asynccontextmanager

from backtest_engine import run_backtest, BacktestError

app = FastAPI(title="Portfolio Backtest API")

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Portfolio Backtest API is running"}

@app.post("/api/backtest")
async def handle_backtest(
    file: UploadFile,
    benchmark_id: str = Form(...),
    period_id: str = Form(...),
    risk_free_rate: float = Form(...)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    content = await file.read()
    
    try:
        # Pass to out engine which handles the pandas logic
        result = run_backtest(
            file_bytes=content,
            benchmark_id=benchmark_id,
            period_id=period_id,
            risk_free_rate_pct=risk_free_rate
        )
        return result
    except BacktestError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error occurred during backtesting.")

class MetricsRequest(BaseModel):
    metrics: list

class NavRequest(BaseModel):
    chart_data: list

@app.post("/api/download/results")
async def download_results(request: MetricsRequest):
    try:
        metrics_data = request.metrics
        if not metrics_data:
            raise HTTPException(status_code=400, detail="No metrics provided")
        
        df = pd.DataFrame(metrics_data)
        # Rename columns to match CLI output
        df = df.rename(columns={"name": "Metric", "portfolio": "Portfolio", "benchmark": "Benchmark"})
        
        csv_content = df.to_csv(index=False)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=backtest_results.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/nav")
async def download_nav(request: NavRequest):
    try:
        data = request.chart_data
        if not data:
            raise HTTPException(status_code=400, detail="No chart data provided")
            
        df = pd.DataFrame(data)
        # Rename columns to match CLI output
        df = df.rename(columns={"Portfolio": "NAV_Portfolio", "Benchmark": "NAV_Benchmark"})
        # Reorder to ensure Date is first
        df = df[["Date", "NAV_Portfolio", "NAV_Benchmark"]]
        
        csv_content = df.to_csv(index=False)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=nav_series.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
