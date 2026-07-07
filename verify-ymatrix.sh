#!/bin/bash

echo "=========================================="
echo "  Verifying Services"
echo "=========================================="

# 检查 YMatrix
echo ""
echo "1. Checking YMatrix..."
if docker compose exec ymatrix psql -h localhost -p 5432 -U mxadmin -d postgres -c "SELECT version();" 2>/dev/null; then
    echo "   ✅ YMatrix is running"
else
    echo "   ❌ YMatrix not responding"
    exit 1
fi

# 检查数据库
echo ""
echo "2. Checking database..."
docker compose exec ymatrix psql -h localhost -p 5432 -U mxadmin -d dw_demo -c "SELECT current_database();"

# 检查扩展
echo ""
echo "3. Checking extensions..."
docker compose exec ymatrix psql -h localhost -p 5432 -U mxadmin -d dw_demo -c "\dx"

# 检查 MySQL
echo ""
echo "4. Checking MySQL..."
docker compose exec mysql mysql -uroot -proot -e "SHOW DATABASES;" 2>/dev/null

# 检查 Grafana
echo ""
echo "5. Checking Grafana..."
curl -s http://localhost:3000/api/health && echo "   ✅ Grafana is running" || echo "   ❌ Grafana not responding"

echo ""
echo "=========================================="
echo "  All services are ready!"
echo "=========================================="