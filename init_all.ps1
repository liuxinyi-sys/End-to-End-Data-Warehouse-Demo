# init_all.ps1 - Windows PowerShell 一键启动脚本
# 用法: .\init_all.ps1

Write-Host "=== YMatrix DW Demo - Init All ===" -ForegroundColor Cyan

# Step 0: Check containers
Write-Host "`nStep 0: Checking containers..." -ForegroundColor Yellow
$running = docker-compose ps --services --filter "status=running"
$expected = @("mysql", "ymatrix", "grafana")
foreach ($svc in $expected) {
    if ($running -notcontains $svc) {
        Write-Host "ERROR: $svc is not running. Start with: docker-compose up -d" -ForegroundColor Red
        exit 1
    }
}
Write-Host "All containers running." -ForegroundColor Green

# Step 1: Generate seed data
Write-Host "`nStep 1: Generating seed data..." -ForegroundColor Yellow
Push-Location sync
python gen_data.py
Pop-Location
Write-Host "Seed data generated." -ForegroundColor Green

# Step 2: Load seed data into MySQL
Write-Host "`nStep 2: Loading seed data into MySQL..." -ForegroundColor Yellow
$seedFiles = @("seed_users.sql","seed_products.sql","seed_orders.sql","seed_order_items.sql","seed_payments.sql")
foreach ($f in $seedFiles) {
    $path = "sync/$f"
    Write-Host "  Loading $f..."
    docker-compose exec -T mysql mysql -uroot -proot -D ecommerce < $path
}
Write-Host "Seed data loaded." -ForegroundColor Green

# Step 3: Verify MySQL
Write-Host "`nStep 3: Verifying MySQL data..." -ForegroundColor Yellow
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e "SELECT 'users',COUNT(*)FROM users UNION SELECT 'products',COUNT(*)FROM products UNION SELECT 'orders',COUNT(*)FROM orders UNION SELECT 'order_items',COUNT(*)FROM order_items UNION SELECT 'payments',COUNT(*)FROM payments;"

# Step 4: Init YMatrix schema
Write-Host "`nStep 4: Initializing YMatrix schema..." -ForegroundColor Yellow
$sqlFiles = Get-ChildItem "ymatrix/init/*.sql" | Sort-Object Name
foreach ($f in $sqlFiles) {
    $name = $f.Name
    Write-Host "  Running $name..."
    docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f "/docker-entrypoint-initdb.d/$name"
}
Write-Host "YMatrix schema initialized." -ForegroundColor Green

# Step 5: Run ETL
Write-Host "`nStep 5: Running ETL pipeline..." -ForegroundColor Yellow
Push-Location sync
python sync_data.py
Pop-Location
Write-Host "ETL complete." -ForegroundColor Green

# Step 6: Verify
Write-Host "`nStep 6: Running verification..." -ForegroundColor Yellow
Push-Location sync
python verify.py
Pop-Location

Write-Host "`n=== All Done ===" -ForegroundColor Cyan
Write-Host "Grafana: http://localhost:3000 (admin/admin)" -ForegroundColor Cyan
