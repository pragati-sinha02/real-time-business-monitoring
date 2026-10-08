"""FastAPI backend.  Start:  uvicorn api.main:app --port 8000"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src import config, database, forecasting, queries
from src.queries import Filters
from src.utils import df_to_records

from .schemas import (AlertOut, FilterOptions, ForecastResponse, GroupRow, HealthResponse,
                      KPIResponse, TopCustomerOut, TransactionOut)

app = FastAPI(
    title="Real-Time Business Monitoring API",
    version="1.0.0",
    description="KPIs, transactions, anomalies, forecasts and alerts from the monitoring pipeline.",
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    first_line = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
    return JSONResponse(status_code=503, content={"detail": f"Database error: {first_line}"})


def get_filters(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    category: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    payment_method: Optional[List[str]] = Query(None),
    risk_level: Optional[List[str]] = Query(None),
    anomaly_status: str = Query("all", pattern="^(all|anomaly|normal)$"),
) -> Filters:
    return Filters(start=start, end=end, categories=category, cities=city,
                   payment_methods=payment_method, anomaly_status=anomaly_status,
                   risk_levels=risk_level)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health():
    ok, message = database.check_connection()
    if not ok:
        return HealthResponse(status="degraded", database=message)
    return HealthResponse(
        status="ok", database="connected",
        latest_transaction_time=database.get_latest_timestamp(),
        total_transactions=database.table_count("transactions"),
        total_scored=database.table_count("transaction_scores"),
    )


@app.get("/api/kpis", response_model=KPIResponse, tags=["analytics"])
def get_kpis(filters: Filters = Depends(get_filters)):
    return queries.kpis(filters)


@app.get("/api/transactions", response_model=List[TransactionOut], tags=["data"])
def get_transactions(filters: Filters = Depends(get_filters),
                     limit: int = Query(100, ge=1, le=5000)):
    return df_to_records(queries.transactions(filters, limit))


@app.get("/api/anomalies", response_model=List[TransactionOut], tags=["data"])
def get_anomalies(filters: Filters = Depends(get_filters),
                  limit: int = Query(100, ge=1, le=5000)):
    return df_to_records(queries.transactions(filters, limit, only_anomalies=True))


@app.get("/api/revenue", response_model=List[GroupRow], tags=["analytics"])
def get_revenue(filters: Filters = Depends(get_filters), group_by: str = Query("category")):
    if group_by not in queries.GROUP_EXPRESSIONS:
        raise HTTPException(status_code=400,
                            detail=f"group_by must be one of {sorted(queries.GROUP_EXPRESSIONS)}")
    return df_to_records(queries.grouped(group_by, filters))


@app.get("/api/top-customers", response_model=List[TopCustomerOut], tags=["analytics"])
def get_top_customers(filters: Filters = Depends(get_filters), limit: int = Query(10, ge=1, le=100)):
    return df_to_records(queries.top_customers(filters, limit))


@app.get("/api/forecast", response_model=ForecastResponse, tags=["forecast"])
def get_forecast(horizon: int = Query(12, ge=1, le=48)):
    data_now = database.get_latest_timestamp()
    if data_now is None:
        return ForecastResponse(status="no_data", message="No transactions yet.")
    start = data_now - timedelta(hours=config.LOOKBACK_HOURS)
    hourly = queries.hourly_series(start)
    return forecasting.build_forecast(hourly, data_now, horizon)


@app.get("/api/alerts", response_model=List[AlertOut], tags=["alerts"])
def get_alerts(limit: int = Query(50, ge=1, le=500), severity: Optional[str] = None):
    return df_to_records(queries.alerts(limit, severity))


@app.get("/api/filter-options", response_model=FilterOptions, tags=["system"])
def get_filter_options():
    return queries.filter_options()