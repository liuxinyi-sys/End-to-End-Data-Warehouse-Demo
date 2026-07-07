#!/bin/bash

echo "=========================================="
echo "  YMatrix Data Warehouse Demo"
echo "=========================================="

# 检查 MatrixDB 安装包
if [ ! -f "ymatrix/matrixdb5_*.deb" ]; then
    echo "ERROR: MatrixDB 5 deb package not found!"
    echo "Please place matrixdb5_*.deb in ymatrix/ directory"
    exit 1
fi

echo "Found MatrixDB 5 deb package:"
ls -la ymatrix/matrixdb5_*.deb

# 启动服务
echo ""
echo "Starting services..."
docker compose up -d

echo ""
echo "Waiting for services to be ready..."
sleep 30

# 显示状态
docker compose ps

echo ""
echo "=========================================="
echo "  Services are ready!"
echo "  Grafana: http://localhost:3000"
echo "  YMatrix: psql -h localhost -p 5432 -U mxadmin -d dw_demo"
echo "  MySQL: localhost:3306"
echo ""
echo "  Credentials:"
echo "    YMatrix: mxadmin/mxadmin123"
echo "    Grafana: admin/admin"
echo "    MySQL: root/root"
echo "=========================================="