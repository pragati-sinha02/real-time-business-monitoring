USE business_monitor;

-- 1. Total revenue, count, average
SELECT SUM(total_amount) AS total_revenue, COUNT(*) AS transactions,
       ROUND(AVG(total_amount),2) AS avg_transaction_value
FROM transactions;

-- 2. Revenue by category
SELECT category, SUM(total_amount) AS revenue, COUNT(*) AS txns
FROM transactions GROUP BY category ORDER BY revenue DESC;

-- 3. Revenue by city
SELECT city, SUM(total_amount) AS revenue, COUNT(*) AS txns
FROM transactions GROUP BY city ORDER BY revenue DESC;

-- 4. Revenue by payment method
SELECT payment_method, SUM(total_amount) AS revenue, COUNT(*) AS txns
FROM transactions GROUP BY payment_method ORDER BY revenue DESC;

-- 5. Transactions by hour of day
SELECT HOUR(txn_timestamp) AS hour_of_day, COUNT(*) AS txns, SUM(total_amount) AS revenue
FROM transactions GROUP BY hour_of_day ORDER BY hour_of_day;

-- 6. Transactions by day
SELECT DATE(txn_timestamp) AS day, COUNT(*) AS txns, SUM(total_amount) AS revenue
FROM transactions GROUP BY day ORDER BY day;

-- 7. Top 10 customers by revenue
SELECT customer_id, COUNT(*) AS txns, SUM(total_amount) AS revenue
FROM transactions GROUP BY customer_id ORDER BY revenue DESC LIMIT 10;

-- 8. High-value transactions (top 20)
SELECT transaction_id, txn_timestamp, customer_id, category, total_amount
FROM transactions ORDER BY total_amount DESC LIMIT 20;

-- 9. Anomaly statistics (after the pipeline has run)
SELECT COUNT(*) AS scored,
       SUM(is_anomaly) AS anomalies,
       ROUND(100 * SUM(is_anomaly) / COUNT(*), 2) AS anomaly_pct
FROM transaction_scores;

-- 10. Risk level distribution
SELECT risk_level, COUNT(*) AS txns FROM transaction_scores GROUP BY risk_level;

-- 11. Revenue at risk (High + Critical)
SELECT SUM(t.total_amount) AS revenue_at_risk
FROM transactions t JOIN transaction_scores s ON s.transaction_id = t.transaction_id
WHERE s.risk_level IN ('High','Critical');

-- 12. Latest alerts
SELECT event_time, severity, alert_type, title FROM alerts ORDER BY event_time DESC LIMIT 20;