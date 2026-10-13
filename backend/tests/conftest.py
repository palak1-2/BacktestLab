"""
Shared pytest fixtures and conftest configuration.
"""

import io
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app


# ---------------------------------------------------------------------------
# In-memory SQLite for tests
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database for each test."""
    from app.models import experiment  # noqa: F401 - register models
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client wired to the in-memory test database."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Ensure tables exist
    from app.models import experiment  # noqa: F401
    Base.metadata.create_all(bind=test_engine)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture file builders
# ---------------------------------------------------------------------------

def make_xlsx_bytes(
    num_rows: int = 5,
    include_win_rate: bool = False,
    param_names: list[str] | None = None,
) -> bytes:
    """
    Build a minimal MT5-style XLSX optimization report in memory.
    """
    import openpyxl

    if param_names is None:
        param_names = ["InpMaxSteps", "InpTakeProfitDist", "InpLotStep"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Optimization Results"

    # Metadata header rows (key: value style)
    ws.append(["Expert: TestEA.ex5"])
    ws.append(["Symbol: EURUSD"])
    ws.append(["Period: H1"])
    ws.append(["Server: Demo-Server"])
    ws.append(["Deposit: 10000"])
    ws.append(["Leverage: 1:100"])
    ws.append([])  # blank row

    # Column header row
    headers = ["Pass"] + param_names + ["Profit", "Expected Payoff", "Profit Factor",
                                          "Recovery Factor", "Sharpe Ratio", "Equity DD %", "Trades"]
    if include_win_rate:
        headers.append("Win Rate")
    ws.append(headers)

    # Data rows
    import random
    random.seed(42)
    for i in range(num_rows):
        row = [i]  # Pass number
        for _ in param_names:
            row.append(random.randint(1, 100))
        # Metrics
        profit = round(random.uniform(-500, 5000), 2)
        ep = round(profit / max(1, random.randint(10, 200)), 2)
        pf = round(random.uniform(0.5, 3.5), 2)
        rf = round(random.uniform(0.5, 5.0), 2)
        sr = round(random.uniform(-1, 3), 2)
        dd = round(random.uniform(1, 40), 2)
        trades = random.randint(5, 500)
        row.extend([profit, ep, pf, rf, sr, dd, trades])
        if include_win_rate:
            row.append(round(random.uniform(30, 90), 2))
        ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def make_xml_bytes(
    num_rows: int = 5,
    include_win_rate: bool = False,
) -> bytes:
    """
    Build a minimal MT5-style SpreadsheetML XML optimization report.
    """
    ns_ss = 'xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"'
    ns_o = 'xmlns:o="urn:schemas-microsoft-com:office:office"'
    ns_x = 'xmlns:x="urn:schemas-microsoft-com:office:excel"'

    param_names = ["InpInitialLot", "InpGridStepPips"]

    metric_names = ["Profit", "Expected Payoff", "Profit Factor",
                    "Recovery Factor", "Sharpe Ratio", "Equity DD %", "Trades"]
    if include_win_rate:
        metric_names.append("Win Rate")

    def cell(val: object, dtype: str = "String") -> str:
        return f'<ss:Cell><ss:Data ss:Type="{dtype}">{val}</ss:Data></ss:Cell>'

    def row(*values) -> str:
        cells = "".join(
            cell(v, "Number") if isinstance(v, (int, float)) else cell(v)
            for v in values
        )
        return f"<ss:Row>{cells}</ss:Row>"

    import random
    random.seed(99)

    data_rows = []
    for i in range(num_rows):
        vals = [i]  # Pass
        for _ in param_names:
            vals.append(random.randint(1, 50))
        # Metrics
        vals.extend([
            round(random.uniform(-500, 5000), 2),
            round(random.uniform(-10, 100), 2),
            round(random.uniform(0.5, 3.5), 2),
            round(random.uniform(0.5, 5.0), 2),
            round(random.uniform(-1, 3), 2),
            round(random.uniform(1, 40), 2),
            random.randint(5, 500),
        ])
        if include_win_rate:
            vals.append(round(random.uniform(30, 90), 2))
        data_rows.append(row(*vals))

    all_data_rows = "\n".join(data_rows)
    header_row = row("Pass", *param_names, *metric_names)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ss:Workbook {ns_ss} {ns_o} {ns_x}>
  <o:DocumentProperties>
    <o:Title>ReportOptimizer TestEA EURUSD H1</o:Title>
    <o:Author>Tester</o:Author>
  </o:DocumentProperties>
  <ss:Worksheet ss:Name="Optimization Results">
    <ss:Table>
      {row("Expert: TestEA.ex5")}
      {row("Symbol: EURUSD")}
      {row("Period: H1")}
      {row("Server: Demo-Server")}
      {row("Deposit: 10000")}
      {row("Leverage: 1:100")}
      {header_row}
      {all_data_rows}
    </ss:Table>
  </ss:Worksheet>
</ss:Workbook>
"""
    return xml.encode("utf-8")
