USE business_monitor;
INSERT INTO transactions
 (transaction_id, txn_timestamp, customer_id, product_id, category, quantity,
  unit_price, total_amount, payment_method, city, device_type)
VALUES
 ('TEST000001','2026-01-01 10:00:00','C0001','GRO-01','Grocery',2,650.00,1300.00,'UPI','Patna','Mobile'),
 ('TEST000002','2026-01-01 10:05:00','C0002','ELE-02','Electronics',1,4500.00,4500.00,'Credit Card','Delhi','Desktop'),
 ('TEST000003','2026-01-01 10:09:00','C0003','FAS-01','Fashion',3,900.00,2700.00,'Wallet','Pune','Mobile');
SELECT * FROM transactions;
-- IMPORTANT: remove these test rows before running seed_history:
-- DELETE FROM transactions WHERE transaction_id LIKE 'TEST%';