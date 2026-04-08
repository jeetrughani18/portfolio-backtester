import React, { useState } from 'react';
import { Upload, Activity, Loader2, Info, Download, TrendingUp, BarChart3, Grid3X3 } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const BENCHMARKS = [
  { id: "1", name: "Nifty 50 (^NSEI)" },
  { id: "2", name: "Nifty 100 (^CNX100)" },
  { id: "3", name: "Nifty 200 (^CNX200)" },
  { id: "4", name: "Nifty 500 (^CRSLDX)" },
  { id: "5", name: "BSE 500 (BSE-500.BO)" },
];

// Helper: format date as YYYY-MM-DD
function formatDate(d) {
  return d.toISOString().split('T')[0];
}

// Default dates: 1 year ago → today
function getDefaultStart() {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 1);
  return formatDate(d);
}

function getDefaultEnd() {
  return formatDate(new Date());
}

export default function App() {
  const [file, setFile] = useState(null);
  const [benchmarkId, setBenchmarkId] = useState("1");
  const [startDate, setStartDate] = useState(getDefaultStart());
  const [endDate, setEndDate] = useState(getDefaultEnd());
  const [riskFreeRate, setRiskFreeRate] = useState("7.0");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setError("");
    }
  };

  const runBacktest = async (e) => {
    e.preventDefault();
    if (!file) {
      setError("Please upload a CSV file first.");
      return;
    }
    
    setLoading(true);
    setError("");
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("benchmark_id", benchmarkId);
    formData.append("start_date", startDate);
    formData.append("end_date", endDate);
    formData.append("risk_free_rate", riskFreeRate);

    try {
      const response = await fetch("http://localhost:8000/api/backtest", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Backtest failed");
      }
      
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadResults = async () => {
    if (!results) return;
    try {
      const response = await fetch("http://localhost:8000/api/download/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ metrics: results.metrics })
      });
      if (!response.ok) throw new Error("Failed to download results");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "backtest_results.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const downloadNav = async () => {
    if (!results) return;
    try {
      const response = await fetch("http://localhost:8000/api/download/nav", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chart_data: results.chart_data })
      });
      if (!response.ok) throw new Error("Failed to download NAV series");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "nav_series.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const downloadCorrelation = () => {
    if (!results || !results.correlation_matrix) return;
    try {
      const corr = results.correlation_matrix;
      if (!corr.length) return;
      const headers = Object.keys(corr[0]);
      const csvRows = [headers.join(",")];
      corr.forEach(row => {
        csvRows.push(headers.map(h => row[h] ?? "").join(","));
      });
      const csvContent = csvRows.join("\n");
      const blob = new Blob([csvContent], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "correlation_matrix.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  // Helper to get color class for correlation value
  const getCorrColor = (val) => {
    if (typeof val !== 'number') return '';
    if (val >= 0.8) return 'bg-emerald-500/30 text-emerald-300';
    if (val >= 0.5) return 'bg-emerald-500/15 text-emerald-200';
    if (val >= 0.2) return 'bg-slate-500/15 text-slate-300';
    if (val >= -0.2) return 'bg-slate-600/20 text-slate-400';
    if (val >= -0.5) return 'bg-red-500/15 text-red-300';
    return 'bg-red-500/30 text-red-300';
  };

  return (
    <div className="min-h-screen p-4 md:p-8 max-w-7xl mx-auto space-y-6">
      
      {/* Header */}
      <header className="flex items-center space-x-3 pb-6 border-b border-white/10">
        <Activity className="w-8 h-8 text-blue-500" />
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-300">
          Portfolio Backtester
        </h1>
      </header>

      {/* Configuration Panel */}
      <section className="glass-panel p-6">
        <h2 className="text-xl font-semibold mb-6 flex items-center">
          <Upload className="w-5 h-5 mr-2 text-blue-400" />
          Configuration
        </h2>
        
        <form onSubmit={runBacktest} className="grid grid-cols-1 md:grid-cols-5 gap-6">
          
          <div className="col-span-1 md:col-span-5 lg:col-span-1">
            <label className="block text-sm font-medium text-slate-300 mb-2">Portfolio CSV</label>
            <div className="relative border-2 border-dashed border-slate-600 rounded-lg px-4 py-3 hover:border-blue-500 transition-colors cursor-pointer text-center h-[42px] flex items-center justify-center overflow-hidden">
              <input 
                type="file" 
                accept=".csv" 
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <span className="text-sm truncate w-full text-slate-400">
                {file ? file.name : "Select or drag CSV"}
              </span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Benchmark Index</label>
            <select 
              value={benchmarkId} 
              onChange={(e) => setBenchmarkId(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {BENCHMARKS.map(b => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Start Date</label>
            <input 
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">End Date</label>
            <input 
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Risk-Free Rate (%)</label>
            <input 
              type="number" 
              step="0.1"
              value={riskFreeRate} 
              onChange={(e) => setRiskFreeRate(e.target.value)}
              className="w-full bg-slate-800/50 border border-slate-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="col-span-1 md:col-span-5 mt-2">
            <button 
              type="submit" 
              disabled={loading}
              className="w-full md:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Running Backtest...</>
              ) : (
                "Run Backtest"
              )}
            </button>
            {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
          </div>

        </form>
      </section>

      {/* Results Section */}
      {results && (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          
          <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center">
            <div className="glass-panel p-4 flex items-center space-x-2 text-sm text-slate-300">
              <Info className="w-5 h-5 text-blue-400" />
              <span>
                Loaded <strong>{results.info.total_stocks_loaded}</strong> stocks. 
                {results.info.liquid_weight > 0 && ` Allocated ${(results.info.liquid_weight * 100).toFixed(2)}% to Liquid Fund.`}
                {' '} Period: <strong>{results.info.period_label}</strong>
              </span>
            </div>
            
            <div className="flex gap-3 w-full sm:w-auto">
              <button 
                onClick={downloadResults}
                className="flex-1 sm:flex-none flex items-center justify-center px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4 mr-2 text-blue-400" />
                Results CSV
              </button>
              <button 
                onClick={downloadNav}
                className="flex-1 sm:flex-none flex items-center justify-center px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4 mr-2 text-blue-400" />
                NAV CSV
              </button>
              <button 
                onClick={downloadCorrelation}
                className="flex-1 sm:flex-none flex items-center justify-center px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded-lg text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4 mr-2 text-blue-400" />
                Correlation CSV
              </button>
            </div>
          </div>

          {/* Metrics Grid */}
          <section>
            <h2 className="text-xl font-semibold mb-4 flex items-center">
              <TrendingUp className="w-5 h-5 mr-2 text-blue-400" />
              Performance Metrics
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              {results.metrics.map(metric => (
                <div key={metric.name} className="glass-panel p-5 relative overflow-hidden group hover:border-blue-500/30 transition-colors">
                  <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-blue-500/10 to-transparent rounded-bl-full pointer-events-none" />
                  <h3 className="text-sm font-medium text-slate-400 mb-3 truncate">{metric.name}</h3>
                  
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-slate-500 uppercase font-semibold">Portfolio</p>
                      <p className="text-2xl font-bold text-white shadow-sm">
                        {metric.portfolio}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 uppercase font-semibold">Benchmark</p>
                      <p className="text-lg text-slate-300">
                        {metric.benchmark}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Relative Metrics */}
          {results.relative_metrics && results.relative_metrics.length > 0 && (
            <section>
              <h2 className="text-xl font-semibold mb-4 flex items-center">
                <BarChart3 className="w-5 h-5 mr-2 text-indigo-400" />
                Relative Metrics <span className="text-sm font-normal text-slate-400 ml-2">(Portfolio vs {results.info.benchmark_name})</span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {results.relative_metrics.map(rm => (
                  <div key={rm.name} className="glass-panel p-5 relative overflow-hidden group hover:border-indigo-500/30 transition-colors">
                    <div className="absolute top-0 right-0 w-16 h-16 bg-gradient-to-br from-indigo-500/10 to-transparent rounded-bl-full pointer-events-none" />
                    <h3 className="text-sm font-medium text-slate-400 mb-2">{rm.name}</h3>
                    <p className="text-2xl font-bold text-white">{rm.value}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Chart Section */}
          <section className="glass-panel p-6">
            <h2 className="text-xl font-semibold mb-6 flex items-center">
              <Activity className="w-5 h-5 mr-2 text-blue-400" />
              NAV Performance (Base 100)
            </h2>
            <div className="h-[400px] w-full mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={results.chart_data} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis 
                    dataKey="Date" 
                    stroke="#94a3b8" 
                    tick={{fill: '#94a3b8'}} 
                    tickLine={false}
                    minTickGap={30}
                  />
                  <YAxis 
                    stroke="#94a3b8" 
                    tick={{fill: '#94a3b8'}}
                    tickLine={false}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Legend wrapperStyle={{ color: '#cbd5e1' }} />
                  <Line 
                    type="monotone" 
                    dataKey="Portfolio" 
                    stroke="#3b82f6" 
                    strokeWidth={3} 
                    dot={false}
                    activeDot={{ r: 8, fill: '#3b82f6' }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="Benchmark" 
                    stroke="#94a3b8" 
                    strokeWidth={2} 
                    dot={false} 
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          {/* Correlation Matrix */}
          {results.correlation_matrix && results.correlation_matrix.length > 0 && (
            <section className="glass-panel p-6">
              <h2 className="text-xl font-semibold mb-6 flex items-center">
                <Grid3X3 className="w-5 h-5 mr-2 text-emerald-400" />
                Correlation Matrix <span className="text-sm font-normal text-slate-400 ml-2">(Daily Returns)</span>
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr>
                      <th className="text-left text-slate-400 font-semibold p-3 bg-slate-800/50 rounded-tl-lg sticky left-0 z-10">Stock</th>
                      {results.correlation_columns.map(col => (
                        <th key={col} className="text-center text-slate-400 font-semibold p-3 bg-slate-800/50 min-w-[80px]">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.correlation_matrix.map((row, idx) => (
                      <tr key={idx} className="border-t border-slate-700/50 hover:bg-slate-700/20 transition-colors">
                        <td className="text-left font-semibold text-slate-300 p-3 bg-slate-800/30 sticky left-0 z-10">
                          {row.Stock}
                        </td>
                        {results.correlation_columns.map(col => {
                          const val = row[col];
                          const isIdentity = row.Stock === col;
                          return (
                            <td 
                              key={col} 
                              className={`text-center p-3 font-mono text-sm ${isIdentity ? 'bg-blue-500/10 text-blue-300 font-bold' : getCorrColor(val)}`}
                            >
                              {typeof val === 'number' ? val.toFixed(4) : val}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          
          {/* Logs */}
          {results.logs && results.logs.length > 0 && (
            <section className="glass-panel p-6">
              <h3 className="text-sm font-semibold text-slate-400 mb-4 uppercase">Event Logs</h3>
              <div className="max-h-40 overflow-y-auto space-y-2 font-mono text-xs text-slate-300">
                {results.logs.map((log, idx) => (
                  <div key={idx} className="bg-slate-800/50 p-2 rounded relative before:content-[''] before:absolute before:left-0 before:top-0 before:w-1 before:h-full before:bg-blue-500/50 overflow-hidden pl-3">
                    {log}
                  </div>
                ))}
              </div>
            </section>
          )}

        </div>
      )}

    </div>
  );
}
