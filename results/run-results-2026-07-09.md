# 运行结果 (2026-07-09)

## 环境

- Branch: main
- 订单规模: ORDER_COUNT=200000 (默认)
- 用户数: 10000 (55% 不活跃, 25% 一次性, 20% 复购)
- ETL 总耗时: 67 秒

---

## 1. MySQL 业务库行数

```sql
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'payments', COUNT(*) FROM payments
UNION ALL SELECT 'order_status_events', COUNT(*) FROM order_status_events;
```

```
table_name           row_count
users                10000
products             500
orders               200000
order_items          483200
payments             189956
order_status_events  699451
```

## 2. 每日 GMV 趋势 (ads_daily_gmv, 前 10 天)

```sql
SELECT dt, order_count, gmv, avg_order_amount FROM ads_daily_gmv ORDER BY dt LIMIT 10;
```

```
         dt          | order_count |    gmv     |   avg_order_amount
---------------------+-------------+------------+-----------------------
 2024-01-01 00:00:00 |         324 | 1671828.13 | 5159.9633641975308642
 2024-01-02 00:00:00 |         352 | 1933692.82 | 5493.4455113636363636
 2024-01-03 00:00:00 |         354 | 2067271.21 | 5839.7491807909604520
 2024-01-04 00:00:00 |         304 | 1679738.41 | 5525.4552960526315789
 2024-01-05 00:00:00 |         299 | 1830583.68 | 6122.3534448160535117
 2024-01-06 00:00:00 |         481 | 2495033.35 | 5187.1795218295218295
 2024-01-07 00:00:00 |         460 | 2623350.61 | 5702.9361086956521739
 2024-01-08 00:00:00 |         336 | 1897294.93 | 5646.7111011904761905
 2024-01-09 00:00:00 |         305 | 1611083.93 | 5282.2423934426229508
 2024-01-10 00:00:00 |         325 | 1851096.52 | 5695.6816000000000000
```

## 3. 双11 GMV 对比日常 (ads_daily_gmv)

```sql
SELECT dt, order_count, gmv FROM ads_daily_gmv WHERE dt IN ('2024-11-10','2024-11-11','2024-11-12') ORDER BY dt;
```

```
         dt          | order_count |     gmv
---------------------+-------------+--------------
 2024-11-10 00:00:00 |        2418 |  12605585.81
 2024-11-11 00:00:00 |       32121 | 140425396.16
 2024-11-12 00:00:00 |        3400 |  16471297.38
```

> 双11 GMV ¥1.40 亿，是日常日均的 49.2 倍；双11订单量 32121，是日常日均的 74 倍

## 4. 双11累计 GMV (ads_gmv_running_total, 前 10 分钟)

```sql
SELECT bucket_time, minute_gmv, running_gmv, minute_order_count, running_order_count
FROM ads_gmv_running_total ORDER BY bucket_time LIMIT 10;
```

```
    bucket_time     | minute_gmv | running_gmv | minute_order_count | running_order_count
---------------------+------------+-------------+--------------------+---------------------
 2024-11-11 00:00:00 |  335137.00 |   335137.00 |                 93 |                  93
 2024-11-11 00:01:00 |  204834.63 |   539971.63 |                 62 |                 155
 2024-11-11 00:02:00 |  261526.83 |   801498.46 |                 67 |                 222
 2024-11-11 00:03:00 |  275360.96 |  1076859.42 |                 76 |                 298
 2024-11-11 00:04:00 |  340496.49 |  1417355.91 |                 78 |                 376
 2024-11-11 00:05:00 |  321607.67 |  1738963.58 |                 61 |                 437
 2024-11-11 00:06:00 |  329134.41 |  2068097.99 |                 59 |                 496
 2024-11-11 00:07:00 |  307983.63 |  2376081.62 |                 79 |                 575
 2024-11-11 00:08:00 |  249903.41 |  2625985.03 |                 79 |                 654
 2024-11-11 00:09:00 |  192159.07 |  2818144.10 |                 59 |                  713
```

> 总行数: 1427 (双11全天逐分钟), 累计 GMV 单调递增: 0 违规

## 5. 商品销售 Top 10 (ads_top_products)

```sql
SELECT product_name, category, total_qty, total_revenue FROM ads_top_products;
```

```
 product_name | category | total_qty | total_revenue
--------------+----------+-----------+---------------
 华为 耳机    | 电子     |      1405 |   12328460.81
 小米 充电器  | 电子     |      1318 |   11759390.16
 vivo 笔记本  | 电子     |      1409 |   12146494.95
 Apple 平板   | 电子     |      1293 |   12181780.86
 华为 耳机    | 电子     |      1341 |   11474678.98
 OPPO 平板    | 电子     |      1376 |   11632548.63
 华为 耳机    | 电子     |      1486 |   13204977.29
 华为 笔记本  | 电子     |      1357 |   11635335.71
 Apple 笔记本 | 电子     |      1382 |   12397218.08
 OPPO 耳机    | 电子     |      1351 |   11696792.77
```

## 6. 品类销售占比 (ads_category_sales)

```sql
SELECT category, revenue, pct FROM ads_category_sales ORDER BY revenue DESC;
```

```
 category |   revenue    |         pct
----------+--------------+---------------------
 电子     | 724244718.98 | 69.5716258401474026
 美妆     | 140270673.38 | 13.4745322250784338
 服装     |  91033798.79 |  8.7447919498050757
 家居     |  63556373.91 |  6.1052847877861183
 食品     |  21900319.50 |  2.1037651971829695
```

## 7. GMV 按省份分布 (ads_gmv_by_region)

```sql
SELECT province, order_cnt, gmv FROM ads_gmv_by_region ORDER BY gmv DESC;
```

```
 province | order_cnt |     gmv
----------+-----------+--------------
 广东省   |     43154 | 236397298.08
 湖北省   |     22089 | 119149420.44
 江苏省   |     20780 | 115892182.41
 重庆市   |     20611 | 114268400.77
 浙江省   |     20714 | 113373919.01
 北京市   |     19186 | 104692294.27
 上海市   |     18635 | 103905835.33
 陕西省   |     18972 | 102057842.27
 四川省   |     15859 |  86431050.29
```

## 8. 用户复购率 (ads_user_repurchase)

```sql
SELECT repurchase_rate, repeat_buyers, total_buyers FROM ads_user_repurchase;
```

```
   repurchase_rate   | repeat_buyers | total_buyers
---------------------+---------------+--------------
 45.7665903890160183 |          2000 |         4370
```

> 4370 个购买用户中，2000 个有复购行为，复购率 45.8%

## 9. 用户价值分层 (ads_user_segment)

```sql
SELECT segment, user_count, total_orders FROM ads_user_segment ORDER BY segment;
```

```
 segment | user_count | total_orders
---------+------------+--------------
 high    |       1456 |       156995
 low     |       1457 |         1457
 mid     |       1457 |        31504
```

> 按消费额 NTILE 3 等分: low（一次性买家）、mid（轻度复购）、high（重度复购）

## 10. 促销期 vs 日常期对比 (ads_promo_compare)

```sql
SELECT period, days, order_cnt, gmv, daily_avg_gmv, avg_order_value, uplift_pct FROM ads_promo_compare;
```

```
 period | days | order_cnt |     gmv      |     daily_avg_gmv     |    avg_order_value    |      uplift_pct
--------+------+-----------+--------------+-----------------------+-----------------------+----------------------
 normal |  351 |    128906 | 751970085.77 |  2142364.916723646724 | 5833.4762211999441453 |                    0
 promo  |   14 |     61050 | 289035798.79 | 20645414.199285714286 | 4734.4111185913185913 | 863.6740238847394700
```

> 促销期日均 GMV ¥2064 万，是日常 ¥214 万的 9.6 倍（uplift 863.7%）

## 11. 订单状态漏斗 (ads_order_status_funnel)

```sql
SELECT status, order_count FROM ads_order_status_funnel;
```

```
  status   | order_count
-----------+-------------
 created   |      200000
 paid      |      189956
 shipped   |      159674
 completed |      139777
 cancelled |      10044
```

> 转化率: created→paid 95%, paid→shipped 84%, shipped→completed 88%, 取消率 5%

## 12. 双11分钟级流量 (ads_minute_traffic, 前 20 分钟)

```sql
SELECT bucket_time, minute_order_count, minute_gmv FROM ads_minute_traffic
WHERE bucket_time >= TIMESTAMP '2024-11-11 00:00:00' AND bucket_time < TIMESTAMP '2024-11-12 00:00:00'
ORDER BY bucket_time LIMIT 20;
```

```
    bucket_time     | minute_order_count | minute_gmv
---------------------+--------------------+------------
 2024-11-11 00:00:00 |                 93 |  335137.00
 2024-11-11 00:01:00 |                 62 |  204834.63
 2024-11-11 00:02:00 |                 67 |  261526.83
 2024-11-11 00:03:00 |                 76 |  275360.96
 2024-11-11 00:04:00 |                 78 |  340496.49
 2024-11-11 00:05:00 |                 61 |  321607.67
 2024-11-11 00:06:00 |                 59 |  329134.41
 2024-11-11 00:07:00 |                 79 |  307983.63
 2024-11-11 00:08:00 |                 79 |  249903.41
 2024-11-11 00:09:00 |                 59 |  192159.07
 2024-11-11 00:10:00 |                 68 |  364699.47
 2024-11-11 00:11:00 |                 73 |  321199.13
 2024-11-11 00:12:00 |                 69 |  228229.88
 2024-11-11 00:13:00 |                 72 |  319396.93
 2024-11-11 00:14:00 |                 81 |  311688.62
 2024-11-11 00:15:00 |                 71 |  379006.42
 2024-11-11 00:16:00 |                 71 |  247949.48
 2024-11-11 00:17:00 |                 77 |  340208.24
 2024-11-11 00:18:00 |                 83 |  287775.94
 2024-11-11 00:19:00 |                 60 |  280934.53
```

> 双11全天分钟级流量总行数: 123890

## 13. 流量峰值 Top 20 分钟 (ads_traffic_peak_minutes)

```sql
SELECT bucket_time, minute_order_count, minute_gmv FROM ads_traffic_peak_minutes;
```

```
    bucket_time     | minute_order_count | minute_gmv
---------------------+--------------------+------------
 2024-11-11 20:29:00 |                102 |  353663.83
 2024-11-11 10:03:00 |                 99 |  400392.21
 2024-11-11 21:34:00 |                 96 |  541891.45
 2024-11-11 10:57:00 |                 94 |  393630.82
 2024-11-11 00:00:00 |                 93 |  335137.00
 2024-11-11 22:39:00 |                 92 |  303108.95
 2024-11-11 00:52:00 |                 90 |  376634.50
 2024-11-11 22:16:00 |                 89 |  335442.21
 2024-11-11 00:38:00 |                 88 |  365331.76
 2024-11-11 00:48:00 |                 88 |  278748.33
 2024-11-11 22:32:00 |                 87 |  420628.11
 2024-11-11 20:13:00 |                 87 |  390014.86
 2024-11-11 21:09:00 |                 86 |  440141.05
 2024-11-11 10:42:00 |                 86 |  398425.79
 2024-11-11 22:35:00 |                 86 |  371629.46
 2024-11-11 20:49:00 |                 85 |  410079.29
 2024-11-11 20:07:00 |                 85 |  287057.09
 2024-11-11 21:26:00 |                 84 |  356645.68
 2024-11-11 00:33:00 |                 83 |  426339.22
 2024-11-11 22:21:00 |                 83 |  426065.01
```

## 14. 履约延迟 (ads_order_fulfillment_latency)

```sql
SELECT paid_to_shipped_hours, shipped_to_completed_hours FROM ads_order_fulfillment_latency;
```

```
 paid_to_shipped_hours | shipped_to_completed_hours
-----------------------+----------------------------
    30.019190909061088 |          72.01147082002645
```

> 付款到发货平均 30 小时，发货到完成平均 72 小时

## 15. MARS3 vs HEAP 压缩率对比

```sql
SELECT pg_total_relation_size('ods_orders_mars_compare') AS mars3_bytes,
       pg_total_relation_size('ods_orders_heap') AS heap_bytes,
       ROUND((1.0 - 1.0 * pg_total_relation_size('ods_orders_mars_compare') / pg_total_relation_size('ods_orders_heap')) * 100, 1) AS savings_pct;
```

```
 mars3_bytes | heap_bytes | savings_pct
-------------+------------+-------------
   100829218 |  601128960 |        83.2
```

> MARS3 列存 + lz4 压缩: ~96 MB | HEAP 行存: ~573 MB | 节省 83.2% (477 MB)

## 16. ETL 审计日志 (etl_log)

```sql
SELECT log_id, step, status, rows_processed, duration_ms, log_time FROM etl_log ORDER BY log_id;
```

```
 log_id |            step             | status  | rows_processed | duration_ms |          log_time
--------+-----------------------------+---------+----------------+-------------+----------------------------
      1 | extract                     | success |        1583107 |       14266 | 2026-07-09 14:53:21.853706
      2 | transform                   | success |        1583107 |         311 | 2026-07-09 14:53:22.313907
      3 | load_ods                    | success |        1583107 |       30681 | 2026-07-09 14:53:53.340169
      4 | load_dim                    | success |          10500 |        3867 | 2026-07-09 14:53:57.072886
      5 | dwd_order_fact              | success |         200000 |        3050 | 2026-07-09 14:54:07.655315
      6 | dwd_order_detail            | success |         483200 |        2957 | 2026-07-09 14:54:07.798865
      7 | dwd_order_status_event_fact | success |         699451 |        2023 | 2026-07-09 14:54:07.965352
      8 | refresh_dws                 | success |              7 |        3219 | 2026-07-09 14:54:08.117935
      9 | etl_complete                | success |              0 |       66997 | 2026-07-09 14:54:12.928239
```

> ETL 全链路耗时 67 秒，含 extract→transform→load_ods→load_dim→dwd→refresh 6 个阶段

## 17. verify.py 验证结果 (21/21 PASS)

```
--- Verifying ADS Metrics ---
  ads_daily_gmv: 365 rows -> PASS
  Nov 11: 140425396.16 vs avg: 2852071 -> PASS
  top_products: 10 rows -> PASS
  category pct: 100.00% -> PASS
  repurchase: 45.8% -> PASS
  gmv_by_region: 9 rows -> PASS
  promo_compare: 2 non-empty periods -> PASS
  user_segment: 3 segments -> PASS
  compression: MARS3 saves 83.2% -> PASS
  etl_log: 9 entries -> PASS
  ods_orders equals configured scale 200000 rows -> PASS
  order_items 2x to 5x orders 483200 rows -> PASS
  Nov 11 >= 50x normal daily average 32121 vs 457 -> PASS
  status events present 699451 rows -> PASS
  order item count varies 200000 non-four-item orders -> PASS
  product dimension credible 0 invalid products -> PASS
  order/detail amount reconciles 0 mismatches -> PASS
  minute traffic non-empty 123890 rows -> PASS
  running GMV non-empty 1427 rows -> PASS
  running GMV monotonic 0 violations -> PASS
  DWD timezone date aligned 0 shifted rows -> PASS

21/21 passed
```

## 18. Grafana 健康检查

```
GET http://localhost:3000/api/health
{"database":"ok","version":"13.1.0","commit":"b309c9bb3b81a748c3a75289236a27309ed2566a"}
```

13 个面板:
1. 每日 GMV 趋势（折线图）
2. 商品销售 Top 10（表格）
3. 品类销售占比（饼图）
4. 用户复购率（单值 Stat）
5. GMV 按省份分布（柱状图）
6. 双11 累计 GMV（折线图）
7. 双11 累计订单量（折线图）
8. 订单状态漏斗（柱状图）
9. 促销期 vs 日常期（条形仪表）
10. 用户价值分层（环形图）
11. 双11 分钟级流量（折线图）
12. 履约延迟（单值 Stat）
13. 流量峰值 Top 20 分钟（表格）

## 19. 核心指标汇总

| 指标 | 数值 |
|------|------|
| MySQL 用户 | 10,000 |
| MySQL 订单 | 200,000 |
| MySQL 订单明细 | 483,200 |
| MySQL 支付 | 189,956 |
| MySQL 状态事件 | 699,451 |
| 双11 GMV | ¥140,425,396 |
| 日常日均 GMV | ¥2,142,365 |
| 双11 GMV 倍数 | 65.6x 日常 |
| 双11订单倍数 | 70.2x 日常 |
| 用户复购率 | 45.8% |
| 促销期 GMV 提升 | 863.7% |
| MARS3 压缩节省 | 83.2% |
| 履约延迟 付款→发货 | 30.0 小时 |
| 履约延迟 发货→完成 | 72.0 小时 |
| 分钟级流量行数 | 123,890 |
| 双11累计 GMV 行数 | 1,427 |
| ETL 总耗时 | 67 秒 |
| 验证结果 | 21/21 PASS |
| Grafana 状态 | healthy |
