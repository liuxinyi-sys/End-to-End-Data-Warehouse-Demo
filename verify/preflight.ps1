$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Assert-Contains($path, $pattern, $message) {
    $fullPath = Join-Path $root $path
    if (-not (Select-String -Path $fullPath -Pattern $pattern -Quiet)) {
        throw $message
    }
}

Assert-Contains 'docker-compose.yml' 'ymatrix/init:/docker-entrypoint-initdb.d:ro' 'YMatrix SQL mount missing'
Assert-Contains 'docker-compose.yml' 'grafana/dashboards:/etc/grafana/provisioning/dashboards' 'Grafana dashboard mount missing'
Assert-Contains 'init_all.sh' 'ON_ERROR_STOP=1' 'YMatrix SQL is not fail-fast'
Assert-Contains 'ymatrix/init/01_init.sql' 'season VARCHAR\(10\)' 'season column is too short'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(user_id\)' 'ods_users lacks a MARS3 order key'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(product_id\)' 'ods_products lacks a MARS3 order key'
Assert-Contains 'sync/load_ods.py' 'docker-compose' 'ODS loader calls host mxgate'
Assert-Contains 'sync/load_dim.py' 'docker-compose' 'DIM loader calls host MatrixDB tools'
Assert-Contains 'sync/load_dwd.py' 'docker-compose' 'DWD loader calls host psql'
Assert-Contains 'sync/sync_data.py' 'docker-compose' 'ETL logger calls host psql'
Assert-Contains 'sync/verify.py' 'docker-compose' 'Verifier calls host psql'

$dashboardProvider = Join-Path $root 'grafana/dashboards/provider.yaml'
if (-not (Test-Path $dashboardProvider)) {
    throw 'Grafana dashboard provider missing'
}

Write-Output 'Preflight checks passed'
