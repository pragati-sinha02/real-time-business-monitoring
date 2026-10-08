"""Streamlit dashboard.  Start:  streamlit run dashboard/app.py"""
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Business Monitoring", page_icon="📊", layout="wide")

RISK_ORDER = ["Low", "Medium", "High", "Critical"]
RISK_COLORS = {"Low": "#2e9e5b", "Medium": "#f2b01e", "High": "#f07b2a",
               "Critical": "#d62839", "Unscored": "#9aa5b1"}
STATUS_COLORS = {"Normal": "#2e9e5b", "Anomaly": "#d62839"}
SEVERITY_ICONS = {"Critical": "🔴 Critical", "High": "🟠 High", "Medium": "🟡 Medium"}
WINDOWS = {"Last 1 hour": 1, "Last 3 hours": 3, "Last 6 hours": 6, "Last 24 hours": 24,
           "Last 3 days": 72, "Last 7 days": 168}
ANOMALY_CHOICES = {"All": "all", "Anomalies only": "anomaly", "Normal only": "normal"}

st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
h1 {font-size: 1.8rem !important;}
div[data-testid="stMetricValue"] {font-size: 1.5rem;}
</style>
""", unsafe_allow_html=True)


class ApiError(Exception):
    pass


def api_get(path, params=None):
    try:
        response = requests.get(f"{API_URL}{path}", params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        raise ApiError(f"Could not get data from the API ({API_URL}{path}). "
                       f"Is the API running? Details: {exc}") from exc


def inr(x) -> str:
    x = float(x)
    sign = "-" if x < 0 else ""
    digits = f"{abs(x):.0f}"
    if len(digits) > 3:
        head, tail, groups = digits[:-3], digits[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join(groups + [tail])
    return f"{sign}₹{digits}"


def compact_inr(x) -> str:
    x = float(x)
    if x >= 1e7:
        return f"₹{x / 1e7:.2f} Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.2f} L"
    return f"₹{x:,.0f}"


@st.cache_data(ttl=60, show_spinner=False)
def load_filter_options():
    return api_get("/api/filter-options")


def style(fig, height=320):
    fig.update_layout(template="plotly_white", height=height,
                      margin=dict(l=10, r=10, t=30, b=10), legend_title_text="")
    return fig


# ------------------------------------------------------------------ sidebar
try:
    OPTIONS = load_filter_options()
except ApiError:
    OPTIONS = {"categories": [], "cities": [], "payment_methods": []}

with st.sidebar:
    st.header("Filters")
    st.selectbox("Time window (data time)", list(WINDOWS), index=3, key="window")
    st.multiselect("Category", OPTIONS["categories"], key="categories", placeholder="All categories")
    st.multiselect("City", OPTIONS["cities"], key="cities", placeholder="All cities")
    st.multiselect("Payment method", OPTIONS["payment_methods"], key="payments", placeholder="All methods")
    st.radio("Anomaly status", list(ANOMALY_CHOICES), key="anomaly_status")
    st.multiselect("Risk level", RISK_ORDER, key="risk_levels", placeholder="All levels")
    st.divider()
    st.toggle("Auto-refresh", value=True, key="auto_refresh")
    st.slider("Refresh every (seconds)", 3, 60, 5, key="refresh_seconds")
    st.caption(f"API: {API_URL}")


def build_params(data_now: datetime) -> dict:
    hours = WINDOWS[st.session_state["window"]]
    params = {"start": (data_now - timedelta(hours=hours)).isoformat(),
              "anomaly_status": ANOMALY_CHOICES[st.session_state["anomaly_status"]]}
    if st.session_state["categories"]:
        params["category"] = st.session_state["categories"]
    if st.session_state["cities"]:
        params["city"] = st.session_state["cities"]
    if st.session_state["payments"]:
        params["payment_method"] = st.session_state["payments"]
    if st.session_state["risk_levels"]:
        params["risk_level"] = st.session_state["risk_levels"]
    return params


# ------------------------------------------------------------------ main view
def render_dashboard():
    try:
        health = api_get("/health")
        if health["status"] != "ok":
            st.error(f"Database problem: {health['database']}")
            return
        if not health.get("latest_transaction_time"):
            st.info("No transactions yet. Run the seed and generator scripts first.")
            return

        data_now = datetime.fromisoformat(health["latest_transaction_time"])
        params = build_params(data_now)
        hours = WINDOWS[st.session_state["window"]]
        bucket = "15min" if hours <= 6 else "hour"

        kpi = api_get("/api/kpis", params)
        time_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": bucket}))
        cat_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": "category"}))
        city_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": "city"}))
        pay_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": "payment_method"}))
        status_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": "anomaly_status"}))
        risk_df = pd.DataFrame(api_get("/api/revenue", {**params, "group_by": "risk_level"}))
        tx_df = pd.DataFrame(api_get("/api/transactions", {**params, "limit": 1000}))
        an_df = pd.DataFrame(api_get("/api/anomalies", {**params, "limit": 15}))
        alerts = api_get("/api/alerts", {"limit": 20})
        forecast = api_get("/api/forecast", {"horizon": 12})
    except ApiError as exc:
        st.error(str(exc))
        return

    st.caption(f"Latest data time: {data_now:%d %b %Y %H:%M:%S} (simulated clock)  •  "
               f"Dashboard refreshed: {datetime.now():%H:%M:%S}")

    # ---- alert banner ----
    if kpi["critical_count"] > 0:
        st.error(f"🚨 {kpi['critical_count']} CRITICAL transaction(s) in this window — "
                 f"{inr(kpi['revenue_at_risk'])} of revenue is at risk.")
    elif kpi["high_risk_count"] > 0:
        st.warning(f"⚠️ {kpi['high_risk_count']} high-risk transaction(s) in this window.")
    else:
        st.success("✅ No high-risk activity in this window.")

    # ---- KPI cards ----
    cards = [
        ("Total Revenue", compact_inr(kpi["total_revenue"]), None),
        ("Transactions", f"{kpi['transaction_count']:,}", None),
        ("Avg Transaction Value", inr(kpi["avg_transaction_value"]), None),
        ("Anomalies", f"{kpi['anomaly_count']:,}", f"{kpi['anomaly_rate_pct']:.1f}% of transactions"),
        ("High-Risk Transactions", f"{kpi['high_risk_count']:,}", f"{kpi['critical_count']} critical"),
        ("Revenue at Risk", compact_inr(kpi["revenue_at_risk"]), None),
    ]
    for col, (label, value, delta) in zip(st.columns(6), cards):
        with col, st.container(border=True):
            st.metric(label, value, delta=delta, delta_color="off")

    # ---- performance over time ----
    st.subheader("Live business performance")
    left, right = st.columns(2)
    if time_df.empty:
        left.info("No data for the selected filters.")
    else:
        time_df["label"] = pd.to_datetime(time_df["label"])
        time_df["normal"] = time_df["transactions"] - time_df["anomalies"]
        fig = px.area(time_df, x="label", y="revenue", title="Revenue over time")
        fig.update_layout(xaxis_title=None, yaxis_title="Revenue (₹)")
        left.plotly_chart(style(fig), key="rev_time")
        fig = px.bar(time_df, x="label", y=["normal", "anomalies"], title="Transaction volume over time",
                     color_discrete_map={"normal": "#4c78a8", "anomalies": "#d62839"})
        fig.update_layout(xaxis_title=None, yaxis_title="Transactions", barmode="stack")
        right.plotly_chart(style(fig), key="vol_time")

    # ---- breakdowns ----
    st.subheader("Where the revenue comes from")
    c1, c2, c3 = st.columns(3)
    if not cat_df.empty:
        fig = px.bar(cat_df.sort_values("revenue"), x="revenue", y="label", orientation="h",
                     title="Revenue by category")
        fig.update_layout(xaxis_title="Revenue (₹)", yaxis_title=None)
        c1.plotly_chart(style(fig), key="by_cat")
    if not city_df.empty:
        fig = px.bar(city_df.sort_values("revenue"), x="revenue", y="label", orientation="h",
                     title="Revenue by city")
        fig.update_layout(xaxis_title="Revenue (₹)", yaxis_title=None)
        c2.plotly_chart(style(fig), key="by_city")
    if not pay_df.empty:
        fig = px.pie(pay_df, names="label", values="revenue", hole=0.5, title="Payment method distribution")
        c3.plotly_chart(style(fig), key="by_pay")

    # ---- risk ----
    st.subheader("Anomalies and risk")
    r1, r2, r3 = st.columns(3)
    if not status_df.empty:
        fig = px.pie(status_df, names="label", values="transactions", hole=0.5,
                     color="label", color_discrete_map=STATUS_COLORS, title="Anomaly distribution")
        r1.plotly_chart(style(fig), key="anom_dist")
    if not risk_df.empty:
        risk_df["label"] = pd.Categorical(risk_df["label"], RISK_ORDER + ["Unscored"], ordered=True)
        risk_df = risk_df.sort_values("label")
        fig = px.bar(risk_df, x="label", y="transactions", color="label",
                     color_discrete_map=RISK_COLORS, title="Transactions by risk level")
        fig.update_layout(xaxis_title=None, showlegend=False)
        r2.plotly_chart(style(fig), key="chart_risk_levels")
    scored = tx_df[tx_df["risk_score"].notna()] if not tx_df.empty else tx_df
    if not scored.empty:
        fig = px.histogram(scored, x="risk_score", nbins=20, title="Risk score distribution (latest 1,000)")
        fig.update_layout(xaxis_title="Risk score (0-100)", yaxis_title="Transactions")
        fig.update_traces(marker_color="#4c78a8")
        r3.plotly_chart(style(fig), key="risk_hist")

    # ---- forecast ----
    st.subheader("Forecast vs actual")
    if forecast["status"] != "ok":
        st.info(forecast.get("message") or "Forecast not available yet.")
    else:
        tabs = st.tabs(["Revenue", "Transactions"])
        for tab, (key, label) in zip(tabs, [("revenue", "Revenue (₹)"), ("transactions", "Transactions per hour")]):
            with tab:
                actual = pd.DataFrame(forecast["actual"])
                future = pd.DataFrame(forecast["forecast"])
                back = pd.DataFrame(forecast["backtest"])
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=pd.to_datetime(actual["hour"]), y=actual[key],
                                         name="Actual", line=dict(color="#4c78a8", width=2)))
                if not back.empty:
                    fig.add_trace(go.Scatter(x=pd.to_datetime(back["hour"]), y=back[f"forecast_{key}"],
                                             name="Backtest forecast (last 24h)",
                                             line=dict(color="#9aa5b1", dash="dot")))
                fig.add_trace(go.Scatter(x=pd.to_datetime(future["hour"]), y=future[key],
                                         name="Forecast (next 12h)",
                                         line=dict(color="#f07b2a", dash="dash", width=2)))
                fig.update_layout(yaxis_title=label, xaxis_title=None)
                st.plotly_chart(style(fig, 340), key=f"fc_{key}")
        metrics = forecast.get("metrics") or {}
        if metrics.get("revenue_wape_pct") is not None:
            st.caption(f"Method: {forecast['method']}. 24-hour backtest error (WAPE): "
                       f"revenue {metrics['revenue_wape_pct']:.1f}%, "
                       f"transactions {metrics['transactions_wape_pct']:.1f}%.")

    # ---- tables ----
    st.subheader("Recent activity")
    t1, t2, t3 = st.tabs(["Recent transactions", "Recent anomalies", "Alerts"])
    columns = ["txn_timestamp", "transaction_id", "customer_id", "category", "city",
               "payment_method", "total_amount", "risk_score", "risk_level", "reasons"]
    with t1:
        if tx_df.empty:
            st.info("No transactions for these filters.")
        else:
            st.dataframe(tx_df[columns].head(15), hide_index=True)
    with t2:
        if an_df.empty:
            st.info("No anomalies for these filters.")
        else:
            st.dataframe(an_df[columns], hide_index=True)
    with t3:
        if not alerts:
            st.info("No alerts yet.")
        else:
            alert_df = pd.DataFrame(alerts)
            alert_df["severity"] = alert_df["severity"].map(lambda s: SEVERITY_ICONS.get(s, s))
            st.dataframe(alert_df[["event_time", "severity", "alert_type", "title", "risk_score"]],
                         hide_index=True)
            critical = [a for a in alerts if a["severity"] == "Critical"]
            if critical:
                with st.expander("Latest critical alert (full text)", expanded=True):
                    st.code(critical[0]["message"], language=None)


# ------------------------------------------------------------------ page
st.title("📊 Real-Time Transaction & Business Anomaly Monitor")
st.caption("Simulated live data  •  MySQL → ML scoring pipeline → FastAPI → Streamlit")

refresh = st.session_state["refresh_seconds"] if st.session_state["auto_refresh"] else None
live_view = st.fragment(render_dashboard, run_every=refresh)
live_view()