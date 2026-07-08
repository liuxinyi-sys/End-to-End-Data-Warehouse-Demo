#!/bin/bash
set -euo pipefail
export MSYS_NO_PATHCONV=1

echo "=== YMatrix DW Demo - Init All ==="

echo "Waiting for MySQL..."
for _ in $(seq 1 60); do
    if docker-compose exec -T mysql mysqladmin ping -h localhost -uroot -proot --silent >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
docker-compose exec -T mysql mysqladmin ping -h localhost -uroot -proot --silent >/dev/null

echo "Waiting for YMatrix..."
for _ in $(seq 1 90); do
    if docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -tAc "SELECT 1" 2>/dev/null | grep -qx 1; then
        break
    fi
    sleep 2
done
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -tAc "SELECT 1" | grep -qx 1

echo "Waiting for Grafana..."
for _ in $(seq 1 60); do
    if curl -fsS http://localhost:3000/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
curl -fsS http://localhost:3000/api/health >/dev/null
echo "All services are ready."

echo "Step 1: Generating seed data..."
cd sync
python gen_data.py
cd ..

echo "Step 2: Resetting and loading MySQL data..."
docker-compose exec -T mysql mysql --default-character-set=utf8mb4 -uroot -proot -D ecommerce -e "SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE payments; TRUNCATE TABLE order_items; TRUNCATE TABLE orders; TRUNCATE TABLE products; TRUNCATE TABLE users; SET FOREIGN_KEY_CHECKS=1;"
for f in sync/seed_users.sql sync/seed_products.sql sync/seed_orders.sql sync/seed_order_items.sql sync/seed_payments.sql; do
    echo "  Loading $(basename "$f")..."
    docker-compose exec -T mysql mysql --default-character-set=utf8mb4 -uroot -proot -D ecommerce < "$f"
done

echo "Step 3: MySQL verification..."
docker-compose exec -T mysql mysql --default-character-set=utf8mb4 -uroot -proot -D ecommerce -e "SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users UNION ALL SELECT 'products', COUNT(*) FROM products UNION ALL SELECT 'orders', COUNT(*) FROM orders UNION ALL SELECT 'order_items', COUNT(*) FROM order_items UNION ALL SELECT 'payments', COUNT(*) FROM payments;"

echo "Step 4: Resetting YMatrix warehouse objects..."
docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -v ON_ERROR_STOP=1 <<'SQL'
DROP VIEW IF EXISTS ads_daily_gmv CASCADE;
DROP VIEW IF EXISTS ads_top_products CASCADE;
DROP VIEW IF EXISTS ads_category_sales CASCADE;
DROP VIEW IF EXISTS ads_user_repurchase CASCADE;
DROP VIEW IF EXISTS ads_user_segment CASCADE;
DROP VIEW IF EXISTS ads_gmv_by_region CASCADE;
DROP VIEW IF EXISTS ads_promo_compare CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_daily_gmv CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_product_daily_sales CASCADE;
DROP MATERIALIZED VIEW IF EXISTS dws_user_purchase_stats CASCADE;
DROP TABLE IF EXISTS dwd_order_detail_fact CASCADE;
DROP TABLE IF EXISTS dwd_order_fact CASCADE;
DROP TABLE IF EXISTS dim_user CASCADE;
DROP TABLE IF EXISTS dim_product CASCADE;
DROP TABLE IF EXISTS dim_promotion CASCADE;
DROP TABLE IF EXISTS dim_region CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS ods_orders_heap CASCADE;
DROP TABLE IF EXISTS ods_orders_mars_compare CASCADE;
DROP TABLE IF EXISTS ods_products CASCADE;
DROP TABLE IF EXISTS ods_users CASCADE;
DROP TABLE IF EXISTS ods_payments CASCADE;
DROP TABLE IF EXISTS ods_order_items CASCADE;
DROP TABLE IF EXISTS ods_orders CASCADE;
DROP TABLE IF EXISTS etl_log CASCADE;
SQL

echo "Step 5: Creating YMatrix schema..."
for f in ymatrix/init/*.sql; do
    echo "  Running $(basename "$f")..."
    docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql -h localhost -U mxadmin -d dw_demo -v ON_ERROR_STOP=1 -f "/docker-entrypoint-initdb.d/$(basename "$f")"
done

echo "Step 6: ETL pipeline..."
cd sync
python sync_data.py
cd ..

echo "Step 7: Verification..."
cd sync
python verify.py
cd ..

echo "=== All Done ==="
echo "Grafana: http://localhost:3000 (admin/admin)"
