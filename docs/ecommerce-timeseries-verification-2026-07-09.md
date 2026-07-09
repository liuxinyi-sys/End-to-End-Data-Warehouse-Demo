# Ecommerce Timeseries Verification - 2026-07-09

## Environment

- Branch: codex/fix-full-flow
- Default order count: 200000
- Business timezone: Asia/Shanghai

## Commands

- docker-compose down -v
- docker-compose up -d
- bash init_all.sh

## Results

- MySQL orders: 200000
- MySQL order_items: 481931
- MySQL order_status_events: 699854
- YMatrix ads_gmv_running_total rows: 1425
- YMatrix ads_gmv_running_total preview (first 5 rows):

```
    bucket_time     | minute_gmv | running_gmv | minute_order_count | running_order_count
---------------------+------------+-------------+--------------------+---------------------
 2024-11-11 00:00:00 |  353851.17 |   353851.17 |                 84 |                  84
 2024-11-11 00:01:00 |  163053.97 |   516905.14 |                 59 |                  143
 2024-11-11 00:02:00 |  298688.15 |   815593.29 |                 76 |                  219
 2024-11-11 00:03:00 |  287136.18 |  1102729.47 |                 67 |                  286
 2024-11-11 00:04:00 |  272278.59 |  1375008.06 |                 78 |                  364
```

- verify.py result: 21/21 PASS
- Grafana health: {"database":"ok","version":"13.1.0","commit":"b309c9bb3b81a748c3a75289236a27309ed2566a"}
- etl_log entries: 17

## Verification Checks (all PASS)

```
  ads_daily_gmv: 365 rows -> PASS
  Nov 11: 126199926.89 vs avg: 2569047 -> PASS
  top_products: 10 rows -> PASS
  category pct: 100.00% -> PASS
  repurchase: 100.00% -> PASS
  gmv_by_region: 9 rows -> PASS
  promo_compare: 2 non-empty periods -> PASS
  user_segment: 3 segments -> PASS
  compression: MARS3 saves 83.2% -> PASS
  etl_log: 17 entries -> PASS
  ods_orders equals configured scale 200000 rows -> PASS
  order_items 2x to 5x orders 481931 rows -> PASS
  Nov 11 >= 50x normal daily average 33790 vs 456.62 -> PASS
  status events present 699854 rows -> PASS
  order item count varies 200000 non-four-item orders -> PASS
  product dimension credible 0 invalid products -> PASS
  order/detail amount reconciles 0 mismatches -> PASS
  minute traffic non-empty 124032 rows -> PASS
  running GMV non-empty 1425 rows -> PASS
  running GMV monotonic 0 violations -> PASS
  DWD timezone date aligned 0 shifted rows -> PASS
```

## Notes

- DWD timestamps are stored as Asia/Shanghai local time directly from ODS TIMESTAMP(3) columns.
- ODS time columns use TIMESTAMP(3) for millisecond precision.
- CSV seed files use LF line endings (lineterminator="\n") for cross-platform mxgate compatibility.
- 1000000-order performance run is not part of the default gate. Record it in a separate section only when that command is actually executed.
