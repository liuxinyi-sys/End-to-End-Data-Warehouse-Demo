-- Compression ratio: MARS3 vs HEAP
SELECT 'MARS3' AS engine, pg_size_pretty(pg_total_relation_size('ods_orders')) AS total_size
UNION ALL
SELECT 'HEAP', pg_size_pretty(pg_total_relation_size('ods_orders_heap'));
-- Expected: MARS3 saves >= 50% space vs HEAP
