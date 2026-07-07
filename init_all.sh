#!/bin/bash
set -e
echo "=== YMatrix DW Demo - Init All ==="
for svc in mysql ymatrix grafana; do
    docker-compose ps $svc | grep -q "Up" || { echo "ERROR: $svc not running"; exit 1; }
done
echo "All containers running."
echo "Step 1: Generating seed data..."
cd sync && python gen_data.py && cd ..
echo "Step 2: Loading seed data..."
for f in sync/seed_users.sql sync/seed_products.sql sync/seed_orders.sql sync/seed_order_items.sql sync/seed_payments.sql; do
    echo "  Loading $(basename $f)..."
    docker-compose exec -T mysql mysql -uroot -proot -D ecommerce < "$f"
done
echo "Step 3: MySQL verification..."
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT 'users',COUNT(*)FROM users UNION SELECT 'products',COUNT(*)FROM products UNION SELECT 'orders',COUNT(*)FROM orders UNION SELECT 'order_items',COUNT(*)FROM order_items UNION SELECT 'payments',COUNT(*)FROM payments;"
echo "Step 4: YMatrix schema..."
for f in ymatrix/init/*.sql; do
    echo "  Running $(basename $f)..."
    docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f "/docker-entrypoint-initdb.d/$(basename $f)"
done
echo "Step 5: ETL pipeline..."
cd sync && python sync_data.py && cd ..
echo "Step 6: Verification..."
cd sync && python verify.py && cd ..
echo "=== All Done ==="; echo "Grafana: http://localhost:3000 (admin/admin)"
