"""Pydantic models: they describe and validate what the API returns."""
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str
    latest_transaction_time: Optional[datetime] = None
    total_transactions: Optional[int] = None
    total_scored: Optional[int] = None


class KPIResponse(BaseModel):
    transaction_count: int
    total_revenue: float
    avg_transaction_value: float
    anomaly_count: int
    anomaly_rate_pct: float
    high_risk_count: int
    critical_count: int
    revenue_at_risk: float


class TransactionOut(BaseModel):
    transaction_id: str
    txn_timestamp: datetime
    customer_id: str
    product_id: str
    category: str
    quantity: int
    unit_price: float
    total_amount: float
    payment_method: str
    city: str
    device_type: str
    is_anomaly: Optional[int] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    reasons: Optional[str] = None


class GroupRow(BaseModel):
    label: str
    revenue: float
    transactions: int
    anomalies: int


class TopCustomerOut(BaseModel):
    customer_id: str
    transactions: int
    revenue: float
    avg_transaction_value: float
    anomalies: int


class AlertOut(BaseModel):
    alert_id: int
    event_time: datetime
    alert_type: str
    severity: str
    title: str
    message: str
    related_key: str
    risk_score: Optional[int] = None


class FilterOptions(BaseModel):
    categories: List[str]
    cities: List[str]
    payment_methods: List[str]


class ForecastPoint(BaseModel):
    hour: datetime
    revenue: float
    transactions: float


class BacktestPoint(BaseModel):
    hour: datetime
    actual_revenue: float
    forecast_revenue: float
    actual_transactions: float
    forecast_transactions: float


class ForecastResponse(BaseModel):
    status: str
    message: str = ""
    method: str = ""
    metrics: Dict[str, Optional[float]] = {}
    actual: List[ForecastPoint] = []
    backtest: List[BacktestPoint] = []
    forecast: List[ForecastPoint] = []