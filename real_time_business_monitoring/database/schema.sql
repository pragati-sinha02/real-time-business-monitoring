CREATE DATABASE IF NOT EXISTS business_monitor
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE business_monitor;

CREATE TABLE IF NOT EXISTS transactions (
  transaction_id        VARCHAR(20)   NOT NULL,
  txn_timestamp         DATETIME      NOT NULL,
  customer_id           VARCHAR(10)   NOT NULL,
  product_id            VARCHAR(20)   NOT NULL,
  category              VARCHAR(40)   NOT NULL,
  quantity              INT           NOT NULL,
  unit_price            DECIMAL(12,2) NOT NULL,
  total_amount          DECIMAL(14,2) NOT NULL,
  payment_method        VARCHAR(30)   NOT NULL,
  city                  VARCHAR(40)   NOT NULL,
  device_type           VARCHAR(20)   NOT NULL,
  injected_anomaly_type VARCHAR(30)   NULL,
  created_at            TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transaction_id),
  KEY idx_txn_time (txn_timestamp),
  KEY idx_customer_time (customer_id, txn_timestamp),
  KEY idx_category (category),
  KEY idx_city (city),
  CONSTRAINT chk_quantity   CHECK (quantity > 0),
  CONSTRAINT chk_unit_price CHECK (unit_price > 0),
  CONSTRAINT chk_total      CHECK (total_amount > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transaction_scores (
  transaction_id VARCHAR(20) NOT NULL,
  scored_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  z_score        DOUBLE      NOT NULL,
  z_flag         TINYINT     NOT NULL,
  iso_score      DOUBLE      NOT NULL,
  iso_flag       TINYINT     NOT NULL,
  is_anomaly     TINYINT     NOT NULL,
  risk_score     INT         NOT NULL,
  risk_level     VARCHAR(10) NOT NULL,
  reasons        TEXT        NULL,
  PRIMARY KEY (transaction_id),
  KEY idx_is_anomaly (is_anomaly),
  KEY idx_risk_score (risk_score),
  CONSTRAINT fk_scores_txn FOREIGN KEY (transaction_id)
      REFERENCES transactions (transaction_id) ON DELETE CASCADE,
  CONSTRAINT chk_risk CHECK (risk_score BETWEEN 0 AND 100)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS alerts (
  alert_id    BIGINT       NOT NULL AUTO_INCREMENT,
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  event_time  DATETIME     NOT NULL,
  alert_type  VARCHAR(30)  NOT NULL,
  severity    VARCHAR(10)  NOT NULL,
  title       VARCHAR(120) NOT NULL,
  message     TEXT         NOT NULL,
  related_key VARCHAR(80)  NOT NULL,
  risk_score  INT          NULL,
  PRIMARY KEY (alert_id),
  UNIQUE KEY uq_alert (alert_type, related_key),
  KEY idx_alert_time (event_time),
  KEY idx_alert_severity (severity)
) ENGINE=InnoDB;