-- ============================================================
-- YMatrix Benchmark Suite
-- 用法: docker-compose exec -T ymatrix /opt/ymatrix/matrixdb5/bin/psql \
--        -h localhost -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/02_benchmark.sql
--
-- 4 大维度: 存储压缩 | 查询性能 MARS3 vs HEAP | 分区裁剪 | ETL 吞吐
-- 对应 Python 多次取平均版本: sync/benchmark.py
-- ============================================================

\timing on
\pset pager off

-- ============================================================
-- 1. 存储压缩: MARS3 vs HEAP (800万行同数据)
-- ============================================================
\echo '=== 1. 存储压缩: MARS3 vs HEAP ==='

SELECT
  'MARS3 (lz4)'  AS engine,
  pg_size_pretty(pg_total_relation_size('ods_orders_mars_compare')) AS total_size,
  pg_total_relation_size('ods_orders_mars_compare') AS bytes
UNION ALL
SELECT
  'HEAP'          AS engine,
  pg_size_pretty(pg_total_relation_size('ods_orders_heap')) AS total_size,
  pg_total_relation_size('ods_orders_heap') AS bytes;

SELECT
  pg_size_pretty(pg_total_relation_size('ods_orders_mars_compare')) AS mars3_size,
  pg_size_pretty(pg_total_relation_size('ods_orders_heap'))         AS heap_size,
  ROUND(
    (1 - pg_total_relation_size('ods_orders_mars_compare')::NUMERIC
           / NULLIF(pg_total_relation_size('ods_orders_heap'), 0)
    ) * 100, 1
  ) AS savings_pct;

-- ============================================================
-- 1b. 分区存储分布: 展示双11月份分区膨胀
-- ============================================================
\echo '=== 1b. 分区存储分布 (ods_orders 12 月分区) ==='

SELECT
  pg_get_expr(c.relpartbound, c.oid) AS partition_range,
  pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
  pg_total_relation_size(c.oid) AS bytes
FROM pg_class c
JOIN pg_inherits i ON c.oid = i.inhrelid
WHERE i.inhparent = 'ods_orders'::regclass
ORDER BY pg_total_relation_size(c.oid) DESC;

-- ============================================================
-- 2. 查询性能: MARS3 vs HEAP (同 800万行数据)
--    用 EXPLAIN ANALYZE 获取精确执行时间
-- ============================================================
\echo '=== 2. 查询性能: MARS3 vs HEAP ==='

\echo '--- Q1: 列投影聚合 (SUM 单列) — 列存只读 1 列 ---'
EXPLAIN (ANALYZE) SELECT SUM(total_amount) FROM ods_orders_mars_compare;
EXPLAIN (ANALYZE) SELECT SUM(total_amount) FROM ods_orders_heap;

\echo '--- Q2: 分组聚合 (GROUP BY status) ---'
EXPLAIN (ANALYZE) SELECT status, COUNT(*), SUM(total_amount) FROM ods_orders_mars_compare GROUP BY status;
EXPLAIN (ANALYZE) SELECT status, COUNT(*), SUM(total_amount) FROM ods_orders_heap GROUP BY status;

\echo '--- Q3: 范围过滤 + 聚合 (WHERE order_date) ---'
EXPLAIN (ANALYZE) SELECT COUNT(*), SUM(total_amount) FROM ods_orders_mars_compare WHERE order_date >= '2024-11-01' AND order_date < '2024-12-01';
EXPLAIN (ANALYZE) SELECT COUNT(*), SUM(total_amount) FROM ods_orders_heap WHERE order_date >= '2024-11-01' AND order_date < '2024-12-01';

\echo '--- Q4: Top-N 排序 ---'
EXPLAIN (ANALYZE) SELECT order_id, total_amount FROM ods_orders_mars_compare ORDER BY total_amount DESC LIMIT 10;
EXPLAIN (ANALYZE) SELECT order_id, total_amount FROM ods_orders_heap ORDER BY total_amount DESC LIMIT 10;

-- ============================================================
-- 3. 分区裁剪: 命中单月分区 vs 全表扫描
-- ============================================================
\echo '=== 3. 分区裁剪: ods_orders (12 月分区) ==='

\echo '--- 命中单分区 (11月, 双11数据) ---'
EXPLAIN (ANALYZE) SELECT COUNT(*), SUM(total_amount) FROM ods_orders WHERE order_date >= '2024-11-01' AND order_date < '2024-12-01';

\echo '--- 全表扫描 (12 个分区) ---'
EXPLAIN (ANALYZE) SELECT COUNT(*), SUM(total_amount) FROM ods_orders;

-- ============================================================
-- 4. 物化视图 vs 直接聚合: 预计算 vs 实时计算
-- ============================================================
\echo '=== 4. 物化视图预聚合 vs 直接 DWD 聚合 ==='

\echo '--- DWS 预聚合 (物化视图直接读) ---'
EXPLAIN (ANALYZE) SELECT * FROM dws_daily_gmv ORDER BY dt;

\echo '--- DWD 实时聚合 (现场 GROUP BY) ---'
EXPLAIN (ANALYZE) SELECT DATE(order_date) AS dt, COUNT(*) AS order_count, SUM(total_amount) AS gmv FROM dwd_order_fact GROUP BY DATE(order_date) ORDER BY dt;

-- ============================================================
-- 5. ETL 吞吐: 从 etl_log 取各阶段耗时和行数
-- ============================================================
\echo '=== 5. ETL 各阶段吞吐 ==='

SELECT
  step,
  rows_processed                                                      AS rows,
  duration_ms                                                         AS duration_ms,
  CASE WHEN duration_ms > 0
       THEN ROUND(rows_processed::NUMERIC / (duration_ms / 1000.0), 0)
       ELSE 0
  END                                                                AS rows_per_sec,
  CASE WHEN duration_ms > 0
       THEN ROUND(duration_ms / 1000.0, 2)
       ELSE 0
  END                                                                AS duration_sec
FROM etl_log
ORDER BY log_id;
