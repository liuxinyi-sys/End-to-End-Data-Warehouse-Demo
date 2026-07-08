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
Assert-Contains 'init_all.sh' 'MSYS_NO_PATHCONV=1' 'Git Bash container path conversion is not disabled'
Assert-Contains 'init_all.sh' '--default-character-set=utf8mb4' 'MySQL seed import does not force UTF-8'
Assert-Contains 'ymatrix/init/01_init.sql' 'season VARCHAR\(10\)' 'season column is too short'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(user_id\)' 'ods_users lacks a MARS3 order key'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(product_id\)' 'ods_products lacks a MARS3 order key'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ods_orders_mars_compare' 'Compression check lacks a non-partitioned MARS3 control table'
Assert-Contains 'sync/load_ods.py' 'docker-compose' 'ODS loader calls host mxgate'
Assert-Contains 'sync/extract.py' 'charset=utf8mb4' 'MySQL extraction does not force UTF-8'
Assert-Contains 'sync/load_ods.py' 'encode\("utf-8"\)' 'ODS loader does not send UTF-8 bytes'
Assert-Contains 'sync/load_ods.py' '/opt/ymatrix/matrixdb5/bin/mxgate' 'ODS loader does not use the image mxgate path'
Assert-Contains 'sync/load_ods.py' '"--time-format","raw"' 'ODS loader uses mxgate unix timestamp conversion'
Assert-Contains 'sync/load_ods.py' 'COMPRESSION_SAMPLE_COPIES = 40' 'Compression sample is too small for a meaningful comparison'
Assert-Contains 'sync/load_ods.py' 'generate_series' 'Compression controls are not derived from the mxgate-loaded ODS data'
Assert-Contains 'sync/load_dim.py' 'docker-compose' 'DIM loader calls host MatrixDB tools'
Assert-Contains 'sync/load_dim.py' 'encode\("utf-8"\)' 'DIM loader does not send UTF-8 bytes'
Assert-Contains 'sync/load_dim.py' '/opt/ymatrix/matrixdb5/bin/mxgate' 'DIM loader does not use the image mxgate path'
Assert-Contains 'sync/load_dim.py' '"--time-format","raw"' 'DIM loader uses mxgate unix timestamp conversion'
Assert-Contains 'sync/load_dwd.py' 'docker-compose' 'DWD loader calls host psql'
Assert-Contains 'sync/sync_data.py' 'docker-compose' 'ETL logger calls host psql'
Assert-Contains 'sync/verify.py' 'docker-compose' 'Verifier calls host psql'
Assert-Contains 'sync/verify.py' 'float\(n11\)' 'Verifier parses NUMERIC GMV as integer'
Assert-Contains 'sync/verify.py' 'promo_compare: 2 non-empty periods' 'Promotion verification uses an invalid total-GMV comparison'
Assert-Contains 'sync/verify.py' 'c == 4' 'Region verification confuses five cities with four provinces'
Assert-Contains 'sync/verify.py' "pg_total_relation_size\('ods_orders_mars_compare'\)" 'Compression verification measures a partitioned parent table'
Assert-Contains 'ymatrix/init/05_ads.sql' 'promo_id > 0' 'Promotion view treats promo_id 0 as promoted'
Assert-Contains 'ymatrix/init/05_ads.sql' 'NTILE\(3\)' 'User segmentation cannot produce three stable segments'
Assert-Contains 'ymatrix/docker-entrypoint.sh' 'host all all samenet md5' 'YMatrix does not allow password-authenticated Docker network clients'
Assert-Contains 'grafana/dashboards/ymatrix_dw_demo.json' '2024-01-01T00:00:00.000Z' 'Grafana default time range does not include the demo data'
Assert-Contains 'grafana/datasources/ymatrix.yaml' 'uid: ymatrix-dw-demo' 'Grafana datasource UID is not stable'
Assert-Contains 'grafana/datasources/ymatrix.yaml' '      database: dw_demo' 'Grafana PostgreSQL plugin lacks jsonData.database'
Assert-Contains 'grafana/dashboards/ymatrix_dw_demo.json' '"uid":"ymatrix-dw-demo"' 'Grafana panels use a legacy datasource name reference'
Assert-Contains 'grafana/dashboards/ymatrix_dw_demo.json' '"uid":"ymatrix-warehouse-demo"' 'Grafana dashboard UID is not stable'
Assert-Contains 'grafana/dashboards/ymatrix_dw_demo.json' 'grafana-postgresql-datasource' 'Grafana panels use the legacy PostgreSQL plugin type'
Assert-Contains 'grafana/dashboards/ymatrix_dw_demo.json' '"type":"barchart"' 'Grafana region panel depends on an unavailable plugin'

$dashboardProvider = Join-Path $root 'grafana/dashboards/provider.yaml'
if (-not (Test-Path $dashboardProvider)) {
    throw 'Grafana dashboard provider missing'
}

Write-Output 'Preflight checks passed'
