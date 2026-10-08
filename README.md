# Real-Time Transaction & Business Anomaly Monitoring System

A local, end-to-end monitoring system that simulates a live stream of online store transactions, scores every transaction for risk with machine learning, watches business KPIs (revenue and volume), forecasts the next hours, raises alerts, and shows everything on an auto-refreshing dashboard.

> **Honest scope note:** this is a *real-time simulation using micro-batch polling every few seconds*. It is not a production streaming system. It does not use Kafka or Spark.

## Business problem

An online business processes thousands of transactions. Teams need to notice quickly when:

- a single transaction looks suspicious (a very large amount, or many orders in a few minutes), or
- the business itself behaves oddly (revenue drops, volume drops, or one category suddenly surges).

## Solution

The system generates realistic transactions, stores them in MySQL, scores each one with a statistical baseline and an Isolation Forest model, converts the result into an explainable 0-100 risk score, checks hourly business KPIs against what is normally expected for that hour, forecasts revenue and volume, and presents everything through a REST API and a Streamlit dashboard.

## Architecture

```
Transaction Generator (src/data_generator.py)
        |  inserts about 1 row per second
        v
MySQL: transactions
        |
        v
Pipeline worker (src/pipeline.py), every 5 seconds
  cleaning -> feature engineering -> Z-score + Isolation Forest
  -> risk score (0-100) + reasons -> transaction_scores
  -> transaction alerts + business KPI alerts -> alerts
        |
        v
FastAPI (api/main.py)  - SQL analytics + forecast
        |  HTTP / JSON
        v
Streamlit + Plotly dashboard (auto-refresh)
```

The dashboard only talks to the API, never directly to the database. This keeps the layers separate.

## Features

- Realistic transaction generator with a simulated clock, customer profiles and daily traffic patterns
- Configurable anomaly injection (`ANOMALY_RATE`): large amounts, bursts, spending spikes, unusual categories, night activity
- Business scenarios: volume drop, revenue drop, category surge
- 12+ engineered features (customer average, rolling 10-minute and 1-hour counts, spending velocity, category affinity, and more)
- Two detectors: Z-score baseline and Isolation Forest
- Explainable risk score (Low, Medium, High, Critical) with plain-English reasons
- Business anomaly monitoring: revenue, volume, category-level and time-of-day aware
- Lightweight forecasting with a 24-hour backtest
- Alert system (stored in MySQL, shown in the dashboard, logged to `logs/alerts.log`)
- REST API with Pydantic models and automatic docs
- Interactive dashboard with filters, KPI cards, charts, tables and alert banner
- Unit tests with pytest

## Technologies

Python, MySQL, SQLAlchemy, PyMySQL, pandas, NumPy, scikit-learn, FastAPI, Uvicorn, Pydantic, Streamlit, Plotly, pytest.

## ML approach

1. **Z-score baseline:** how many standard deviations is the amount from its category's typical amount (log scale). `|z| >= 3` is flagged.
2. **Isolation Forest:** trained on 9 features at once, so it can catch cases like a normal amount but many orders in a few minutes. `contamination=0.02` means about 2% of training data is expected to be anomalous.
3. **Combined label:** a transaction is an anomaly if either detector flags it.
4. **Risk score:**

```
risk = 100 x (0.55 x iso_norm + 0.25 x z_norm + 0.20 x behavior_norm)
```

Levels: 0-30 Low, 31-60 Medium, 61-80 High, 81-100 Critical.

Reasons come from simple rules on the features. They are indicators, not proven causes.

## Forecasting

Seasonal profile with level adjustment: the median value for each hour of the day, multiplied by a level factor from the last 24 hours (limited to 0.5-1.5). It is simple, fast and easy to explain. It ignores weekly patterns and promotions, and needs at least 48 complete hours of data.

## Database schema

| Table | Purpose |
|---|---|
| `transactions` | Raw transactions (id, timestamp, customer, product, category, quantity, price, amount, payment method, city, device, injected anomaly label) |
| `transaction_scores` | Z-score, Isolation Forest score, flags, risk score, risk level, reasons |
| `alerts` | Transaction and business alerts (unique per type and key to avoid duplicates) |

The full SQL is in `database/schema.sql`. Example analytics queries are in `database/analytics.sql`.

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | API and database status |
| `GET /api/kpis` | Revenue, transaction count, average value, anomalies, revenue at risk |
| `GET /api/transactions` | Recent transactions with scores |
| `GET /api/anomalies` | Only anomalous transactions |
| `GET /api/revenue?group_by=category` | Revenue grouped by category, city, payment method, hour, and more |
| `GET /api/top-customers` | Top customers by revenue |
| `GET /api/forecast` | Forecast, backtest and error metrics |
| `GET /api/alerts` | Latest alerts |
| `GET /api/filter-options` | Values for the dashboard filters |

Interactive docs: `http://127.0.0.1:8000/docs`

## Dashboard screenshots

Add your own screenshots here after running the project:

![Dashboard](docs/screenshots/dashboard.png)

## Installation

Requirements: Windows 10/11 (also works on Linux/macOS), Python 3.11+, MySQL 8, Git.

```powershell
git clone https://github.com/YOUR-USERNAME/real-time-business-monitoring.git
cd real-time-business-monitoring
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

1. Copy `.env.example` to `.env` and set your MySQL port and password.
2. In MySQL Workbench, run `database/schema.sql`.

## Usage

One-time setup (run from the project folder):

```powershell
python -m src.seed_history
python -m src.train_model
python -m src.pipeline --once
```

Start the live system (one terminal each, venv active):

```powershell
python -m src.data_generator
python -m src.pipeline
uvicorn api.main:app --port 8000
streamlit run dashboard/app.py
```

Open `http://localhost:8501`. Stop each service with Ctrl+C.

Useful demo options:

```powershell
python -m src.data_generator --scenario volume_drop
python -m src.data_generator --scenario revenue_drop
python -m src.data_generator --scenario category_surge
python -m src.data_generator --anomaly-rate 0.10
```

## Project structure

```
real_time_business_monitoring/
├── api/                  FastAPI app and Pydantic schemas
├── dashboard/            Streamlit dashboard
├── data/sample/
├── database/             schema.sql, seed.sql, analytics.sql
├── models/               Saved Isolation Forest (created by training)
├── notebooks/
├── src/
│   ├── config.py             Settings from .env
│   ├── database.py           MySQL access
│   ├── queries.py            SQL used by the API
│   ├── data_generator.py     Transaction generator
│   ├── seed_history.py       Back-fills history
│   ├── preprocessing.py      Data cleaning
│   ├── feature_engineering.py
│   ├── anomaly_detection.py  Z-score and Isolation Forest
│   ├── train_model.py
│   ├── risk_scoring.py       Risk score and reasons
│   ├── business_anomalies.py Revenue / volume / category monitoring
│   ├── forecasting.py
│   ├── alerts.py
│   ├── pipeline.py           Scoring worker
│   └── evaluate.py           Precision / recall vs simulator labels
├── tests/
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

## Results

I have not published numbers I did not measure. To measure them on your own run:

```powershell
python -m pytest -v
python -m src.evaluate
```

`evaluate` compares the detectors with the labels the simulator injected. Copy your own output into this table:

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| Z-score baseline | (your result) | (your result) | (your result) |
| Isolation Forest | (your result) | (your result) | (your result) |
| Combined | (your result) | (your result) | (your result) |

The forecast dashboard also shows a 24-hour backtest error (WAPE) measured on your data.

## Limitations

- The data is simulated, so results show the system works, not how it performs on real business data.
- It is a polling simulation (every few seconds), not a distributed streaming system.
- The model is evaluated on data it was trained on (in-sample). Use `--hours` in `evaluate` to look at newer data.
- The first transaction of a burst can look normal because features only use the past.
- Reasons are rule-based indicators, not confirmed causes.
- The forecast ignores weekly patterns and promotions.

## Future improvements

- Docker and docker-compose for one-command startup
- Email or Slack alert delivery
- Retraining on a schedule and model monitoring
- Weekly seasonality and better forecasting models
- Authentication on the API
- Optional: Kafka for true streaming (an advanced extension, not part of this project)
