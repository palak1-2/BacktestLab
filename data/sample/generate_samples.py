"""
Generate sample MT5 optimization report files for testing and demonstration.

Run from the backtest/backend directory:
    python ../data/sample/generate_samples.py

Produces:
    data/sample/sample_optimization_small.xlsx   (~100 rows)
    data/sample/sample_optimization_large.xlsx   (~2000 rows)
    data/sample/sample_optimization.xml         (~200 rows)
"""

import io
import os
import random
import sys

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))


def make_xlsx(output_path: str, num_rows: int, include_win_rate: bool = False):
    import openpyxl

    param_names = [
        "InpMaxSteps", "InpTakeProfitDist", "InpSlowdownMode",
        "InpOneTradePerBar", "Cycle1_Lot", "Cycle1_Step",
        "InpInitialLot", "InpLotStep", "InpGridStepPips", "InpGlobalTarget",
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Optimization Results"

    ws.append(["Expert: SampleGridEA.ex5"])
    ws.append(["Symbol: EURUSD"])
    ws.append(["Period: H1"])
    ws.append(["Server: ICMarkets-Demo01"])
    ws.append(["Deposit: 10000"])
    ws.append(["Leverage: 1:500"])
    ws.append(["From: 2024.01.01"])
    ws.append(["To: 2024.06.30"])
    ws.append([])

    headers = ["Pass"] + param_names + [
        "Profit", "Expected Payoff", "Profit Factor",
        "Recovery Factor", "Sharpe Ratio", "Equity DD %", "Trades",
    ]
    if include_win_rate:
        headers.append("Win Rate")
    ws.append(headers)

    rng = random.Random(12345)
    for i in range(num_rows):
        row = [i]
        for _ in param_names:
            row.append(rng.randint(1, 200))

        profit = round(rng.uniform(-2000, 15000), 2)
        ep = round(profit / max(1, rng.randint(20, 500)), 2)
        pf = round(rng.uniform(0.3, 4.0), 2)
        rf = round(rng.uniform(0.2, 8.0), 2)
        sr = round(rng.uniform(-2.0, 5.0), 2)
        dd = round(rng.uniform(0.5, 60.0), 2)
        trades = rng.randint(10, 1000)

        row.extend([profit, ep, pf, rf, sr, dd, trades])
        if include_win_rate:
            row.append(round(rng.uniform(20, 95), 2))
        ws.append(row)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    wb.save(output_path)
    print(f"Created: {output_path} ({num_rows} rows)")


def make_xml(output_path: str, num_rows: int):
    param_names = ["InpInitialLot", "InpGridStepPips", "InpMaxOrders", "InpGlobalTarget"]
    metric_names = ["Profit", "Expected Payoff", "Profit Factor",
                    "Recovery Factor", "Sharpe Ratio", "Equity DD %", "Trades"]

    ns_ss = 'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"'
    ns_o = 'xmlns:o="urn:schemas-microsoft-com:office:office"'

    def cell(val, dtype="String"):
        return f'<ss:Cell><ss:Data ss:Type="{dtype}">{val}</ss:Data></ss:Cell>'

    def row(*values):
        cells = "".join(
            cell(v, "Number") if isinstance(v, (int, float)) else cell(str(v))
            for v in values
        )
        return f"<ss:Row>{cells}</ss:Row>"

    rng = random.Random(99999)
    data_rows = []
    for i in range(num_rows):
        vals = [i]
        for _ in param_names:
            vals.append(rng.randint(1, 100))
        vals.extend([
            round(rng.uniform(-2000, 10000), 2),
            round(rng.uniform(-50, 200), 2),
            round(rng.uniform(0.3, 4.0), 2),
            round(rng.uniform(0.2, 8.0), 2),
            round(rng.uniform(-2.0, 5.0), 2),
            round(rng.uniform(0.5, 60.0), 2),
            rng.randint(10, 500),
        ])
        data_rows.append(row(*vals))

    header_row = row("Pass", *param_names, *metric_names)
    all_data = "\n      ".join(data_rows)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ss:Workbook {ns_ss} {ns_o}>
  <o:DocumentProperties>
    <o:Title>ReportOptimizer SampleGridEA EURUSD H1</o:Title>
    <o:Author>Researcher</o:Author>
  </o:DocumentProperties>
  <ss:Worksheet ss:Name="Optimization Results">
    <ss:Table>
      {row("Expert: SampleGridEA.ex5")}
      {row("Symbol: EURUSD")}
      {row("Period: H1")}
      {row("Server: ICMarkets-Demo01")}
      {row("Deposit: 10000")}
      {row("Leverage: 1:500")}
      {header_row}
      {all_data}
    </ss:Table>
  </ss:Worksheet>
</ss:Workbook>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"Created: {output_path} ({num_rows} rows)")


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__))
    make_xlsx(os.path.join(base, "sample_optimization_small.xlsx"), num_rows=100)
    make_xlsx(os.path.join(base, "sample_optimization_large.xlsx"), num_rows=2000)
    make_xml(os.path.join(base, "sample_optimization.xml"), num_rows=200)
    print("\nSample files generated in data/sample/")
    print("Import with:")
    print("  curl -X POST http://localhost:8000/experiments/import \\")
    print('       -F "file=@data/sample/sample_optimization_small.xlsx"')
