# 运行结果 (2026-07-09)

## 环境

- Branch: codex/fix-full-flow
- 订单规模: ORDER_COUNT=200000 (默认)
- ETL 总耗时: 78.9 秒

## 1. MySQL 业务库行数

```
table_name           row_count
users                1000
products             500
orders               200000
order_items          481931
payments             190000
order_status_events  699854
```

## 2. YMatrix 数仓对象清单 (89 对象)

- ODS: 6 张 MARS3 分区表 (ods_orders, ods_order_items, ods_payments, ods_users, ods_products, ods_order_status_events)
- ODS 压缩对比: ods_orders_heap (HEAP), ods_orders_mars_compare (MARS3)
- DIM: 4 张 HEAP 表 (dim_date, dim_product, dim_promotion, dim_region, dim_user)
- DWD: 3 张 MARS3 分区表 (dwd_order_fact, dwd_order_detail_fact, dwd_order_status_event_fact)
- DWS: 7 个物化视图
- ADS: 11 个视图
- etl_log: 1 张审计表

## 3. 双11 累计 GMV (ads_gmv_running_total)

```
    bucket_time     | minute_gmv | running_gmv | minute_order_count | running_order_count
---------------------+------------+-------------+--------------------+---------------------
 2024-11-11 00:00:00 |  353851.17 |   353851.17 |                 84 |                  84
 2024-11-11 00:01:00 |  163053.97 |   516905.14 |                 59 |                 143
 2024-11-11 00:02:00 |  298688.15 |   815593.29 |                 76 |                  219
 2024-11-11 00:03:00 |  287136.18 |  1102729.47 |                 67 |                  286
 2024-11-11 00:04:00 |  272278.59 |  1375008.06 |                 78 |                  364
 2024-11-11 00:05:00 |  214278.80 |  1589286.86 |                 58 |                  422
 2024-11-11 00:06:00 |  403397.61 |  1992684.47 |                 63 |                  485
 2024-11-11 00:07:00 |  317501.52 |  2310185.99 |                 82 |                  567
 2024-11-11 00:08:00 |  318731.47 |  2628917.46 |                 86 |                  653
 2024-11-11 00:09:00 |  149344.82 |  2778262.28 |                 53 |                  706

总行数: 1425 (双11全天逐分钟)
累计 GMV 单调递增: 0 违规
```

## 4. 双11 vs 日常 GMV 对比 (ads_daily_gmv)

```
         dt          | order_count |     gmv      |   avg_order_amount
---------------------+-------------+--------------+-----------------------
 2024-11-10 00:00:00 |        2384 |  11028668.03 | 4626.1191401006711409
 2024-11-11 00:00:00 |       32062 | 126199926.89 | 3936.1214799451063564
 2024-11-12 00:00:00 |        3342 |  14247073.91 | 4263.0382734889287852

双11 GMV 是日常的 11.5x（日均 ~257万 vs 双11 ~1.26亿）
双11订单量是日均的 74x（日均 ~434 vs 双11 32062）
```

## 5. 促销对比 (ads_promo_compare)

```
 period | days | order_cnt |     gmv      |     daily_avg_gmv     |    avg_order_value    |      uplift_pct
--------+------+-----------+--------------+-----------------------+-----------------------+----------------------
 normal |  351 |    129003 | 678322275.83 |  1932542.096381766382 | 5258.1899322496376053 |                    0
 promo  |   14 |     60997 | 259379997.11 | 18527142.650714285714 | 4252.3402316507369215 | 858.6928370358416600

促销期日均 GMV 是日常的 9.6x（uplift 858.7%）
```

## 6. 订单状态漏斗 (ads_order_status_funnel)

```
  status   | order_count
-----------+-------------
 created   |      200000
 paid      |      190000
 shipped   |      159911
 completed |      139943
 cancelled |       10000

转化率: created→paid 95%, paid→shipped 84%, shipped→completed 88%
取消率: 5%
```

## 7. 商品销售 Top 10 (ads_top_products)

```
 product_name | category | total_qty | total_revenue
--------------+----------+-----------+---------------
 小米 手机     | 电子     |      1352 |   12561002.80
 Apple 笔记本  | 电子     |      1334 |   12222326.08
 小米 耳机     | 电子     |      1406 |   11714641.27
 vivo 耳机     | 电子     |      1368 |   11447578.73
 小米 平板     | 电子     |      1342 |   12190644.82
 小米 充电器   | 电子     |      1342 |   12470152.73
 OPPO 平板     | 电子     |      1335 |   12124584.15
 华为 手机     | 电子     |      1297 |   11356989.85
 小米 笔记本   | 电子     |      1280 |   11874744.42
 OPPO 耳机     | 电子     |      1373 |   11410867.72
```

## 8. 用户复购率 (ads_user_repurchase)

```
   repurchase_rate    | repeat_buyers | total_buyers
----------------------+---------------+--------------
 100.0000000000000000 |          1000 |         1000

复购率: 100%（200K 订单覆盖 1000 用户，每用户平均 200 单）
```

## 9. MARS3 vs HEAP 压缩率对比

```
 mars3_bytes | heap_bytes | savings_pct
-------------+------------+-------------
   100890096 |  601030656 |        83.2

MARS3 列存 + lz4 压缩相比 HEAP 行存节省 83.2% 存储空间
MARS3: ~96MB | HEAP: ~573MB | 节省: ~477MB
```

## 10. ETL 审计日志 (etl_log)

```
etl_log 条目数: 17
覆盖步骤: extract, transform, load_ods, load_dim, dwd_order_fact, dwd_order_detail_fact,
          dwd_order_status_event_fact, refresh_dws, etl_complete
```

## 11. verify.py 验证结果 (21/21 PASS)

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

21/21 passed
```

## 12. Grafana 健康检查

```
GET http://localhost:3000/api/health
Response: {"database":"ok","version":"13.1.0","commit":"b309c9bb3b81a748c3a75289236a27309ed2566a"}

6 个面板:
1. 每日 GMV 趋势（折线图）
2. 商品销售 Top 10（表格）
3. 品类销售占比（饼图）
4. 用户复购率（单值 Stat）
5. GMV 按省份分布（柱状图）
6. 双11 累计 GMV（折线图，ads_gmv_running_total）
```
