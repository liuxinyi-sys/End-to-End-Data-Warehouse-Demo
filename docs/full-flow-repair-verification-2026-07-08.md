# Full-Flow Repair Verification (2026-07-08)

## Scope

Validated a clean Docker Compose deployment from MySQL seed generation through YMatrix ODS/DIM/DWD/DWS/ADS processing and Grafana rendering. The test used the existing local `ymatrix5.2-clean:latest` image.

## Final Result

**PASS** - `docker-compose down -v`, `docker-compose up -d`, and `bash init_all.sh` completed with exit code 0 in 138.7 seconds. The ETL verifier passed 10/10 checks.

| Check | Result |
|---|---|
| MySQL rows | users 1,000; products 500; orders 50,000; order_items 200,000; payments 50,000 |
| YMatrix objects | ODS 5; DIM 5; DWD 2; DWS 3; ADS 7 |
| ADS checks | 10/10 passed |
| Compression controls | 2,000,000 rows each |
| MARS3 vs HEAP | 13,109,587 vs 149,946,368 bytes; 91.3% saved |
| ETL log | 8 entries |
| Grafana datasource | `Database Connection OK` |
| Grafana dashboard | 6 panels provisioned and visually rendered with data |

## Defects Found And Fixed

1. Container startup and SQL initialization were not deterministic. The YMatrix entrypoint, health checks, mounts, fail-fast SQL execution, and Git Bash path handling were corrected.
2. Seed generation and loaders did not consistently preserve exact counts or UTF-8 data. Generation is deterministic and mxgate loads now validate row counts.
3. Several YMatrix DDL and ADS queries were incompatible or semantically incorrect. Partitioning, MARS order keys, promotion logic, region counts, segmentation, and optional FDW behavior were corrected.
4. Compression verification measured a partitioned parent and falsely reported 100% savings. Dedicated non-partitioned MARS3/HEAP controls now derive 40 copies from the mxgate-loaded ODS orders, producing a meaningful 2-million-row comparison.
5. Grafana provisioning imported a dashboard that showed no data. Fixed causes were the 2024 default time range, stable datasource/dashboard UIDs, Grafana 13 datasource references, `jsonData.database`, YMatrix `pg_hba.conf` access for same-network clients, and replacement of the unavailable treemap plugin with the built-in bar chart.

## Verification Commands

```powershell
docker-compose down -v
docker-compose up -d
& 'C:\Program Files\Git\bin\bash.exe' init_all.sh
powershell -ExecutionPolicy Bypass -File verify/preflight.ps1
python -m py_compile sync/load_ods.py sync/verify.py
docker-compose config --quiet
curl.exe -u admin:admin http://localhost:3000/api/datasources/uid/ymatrix-dw-demo/health
```

Dashboard: `http://localhost:3000/d/ymatrix-warehouse-demo/ymatrix-dw-demo` (`admin` / `admin`).

## Accepted Limitation

The local YMatrix image does not include `mysql_fdw`; `06_fdw.sql` reports a notice and skips this optional showcase. The required MySQL-to-YMatrix path still runs through extract, transform, mxgate, SQL fact loading, materialized-view refresh, and ADS views.
