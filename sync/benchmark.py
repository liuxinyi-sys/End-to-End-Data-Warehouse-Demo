#!/usr/bin/env python3
"""YMatrix Benchmark Suite — 查询性能对比 (多次运行取平均)。

维度:
  1. 查询性能: MARS3 vs HEAP (同 800万行数据, 4 类查询)
  2. 分区裁剪: 命中单月分区 vs 全表扫描
  3. 物化视图: 预聚合 MV vs 实时 DWD 聚合
  4. 存储压缩: MARS3 vs HEAP 各表大小
  5. ETL 吞吐: 各阶段 rows/s

用法: cd sync && python benchmark.py [runs]
  runs: 每个查询重复次数, 默认 5
"""
import subprocess
import sys
import os
import time
import re
from datetime import datetime

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
PSQL = ["docker-compose", "exec", "-T", "ymatrix",
        "/opt/ymatrix/matrixdb5/bin/psql",
        "-h", "localhost", "-p", "5432", "-U", "mxadmin",
        "-d", "dw_demo", "-v", "ON_ERROR_STOP=1"]


def run_sql(sql, capture=True):
    """Execute SQL via psql, return stdout string."""
    r = subprocess.run(PSQL + ["-t", "-A", "-c", sql],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("SQL error: " + r.stderr[:500])
    return r.stdout.strip() if capture else ""


def run_explain_analyze(sql):
    """Run EXPLAIN (ANALYZE) and extract Execution Time in ms.

    Returns list of float (one per run).
    """
    times = []
    for _ in range(RUNS):
        r = subprocess.run(PSQL + ["-c", f"EXPLAIN (ANALYZE) {sql}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("EXPLAIN error: " + r.stderr[:500])
        # Parse all "Execution Time: X ms" lines
        matches = re.findall(r"Execution Time:\s+([\d.]+)\s+ms", r.stdout)
        if matches:
            # Take the last one (outer query, not subqueries)
            times.append(float(matches[-1]))
        else:
            times.append(0.0)
    return times


def fmt_times(times):
    """Format timing list: avg / min / max ms."""
    avg = sum(times) / len(times) if times else 0
    return {
        "avg": round(avg, 2),
        "min": round(min(times), 2) if times else 0,
        "max": round(max(times), 2) if times else 0,
    }


def speedup(mars3_ms, heap_ms):
    """How many times faster MARS3 is vs HEAP."""
    if heap_ms > 0 and mars3_ms > 0:
        return round(heap_ms / mars3_ms, 1)
    return 0


def get_order_count():
    return int(run_sql("SELECT COUNT(*) FROM ods_orders;"))


def get_storage_info():
    """Get storage sizes for MARS3 vs HEAP and all major tables."""
    mars3_bytes = int(run_sql("SELECT pg_total_relation_size('ods_orders_mars_compare');"))
    heap_bytes = int(run_sql("SELECT pg_total_relation_size('ods_orders_heap');"))

    # Partition sizes
    part_sql = """
SELECT pg_get_expr(c.relpartbound, c.oid),
       pg_total_relation_size(c.oid)
FROM pg_class c
JOIN pg_inherits i ON c.oid = i.inhrelid
WHERE i.inhparent = 'ods_orders'::regclass
ORDER BY pg_total_relation_size(c.oid) DESC;
"""
    r = run_sql(part_sql)
    partitions = []
    for line in r.split("\n"):
        if "|" in line:
            rng, sz = line.rsplit("|", 1)
            partitions.append((rng.strip(), int(sz.strip())))

    return mars3_bytes, heap_bytes, partitions


def get_etl_log():
    """Get ETL pipeline timing from etl_log table."""
    sql = """
SELECT step, rows_processed, duration_ms
FROM etl_log ORDER BY log_id;
"""
    r = run_sql(sql)
    entries = []
    for line in r.split("\n"):
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                step = parts[0].strip()
                rows = int(parts[1].strip()) if parts[1].strip() else 0
                ms = int(parts[2].strip()) if parts[2].strip() else 0
                entries.append({"step": step, "rows": rows, "ms": ms})
    return entries


def pretty_size(bytes_val):
    if bytes_val >= 1073741824:
        return f"{bytes_val / 1073741824:.1f} GB"
    elif bytes_val >= 1048576:
        return f"{bytes_val / 1048576:.1f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"


def run_benchmark():
    order_count = get_order_count()
    mars3_bytes, heap_bytes, partitions = get_storage_info()
    etl_entries = get_etl_log()

    savings_pct = round((1 - mars3_bytes / heap_bytes) * 100, 1) if heap_bytes > 0 else 0

    # Benchmark queries: (label, sql)
    mars3_heap_queries = [
        ("Q1 列投影聚合 SUM(total_amount)",
         "SELECT SUM(total_amount) FROM {table}"),
        ("Q2 分组聚合 GROUP BY status",
         "SELECT status, COUNT(*), SUM(total_amount) FROM {table} GROUP BY status"),
        ("Q3 范围过滤+聚合 (11月)",
         "SELECT COUNT(*), SUM(total_amount) FROM {table} WHERE order_date >= '2024-11-01' AND order_date < '2024-12-01'"),
        ("Q4 Top-N 排序 LIMIT 10",
         "SELECT order_id, total_amount FROM {table} ORDER BY total_amount DESC LIMIT 10"),
    ]

    # Use ods_order_status_events (700K+ rows, 12 partitions) for more visible pruning effect
    partition_queries = [
        ("命中单分区 (11月, 1/12 数据)",
         "SELECT COUNT(*) FROM ods_order_status_events WHERE event_time >= '2024-11-01' AND event_time < '2024-12-01'"),
        ("全表扫描 (12 个分区)",
         "SELECT COUNT(*) FROM ods_order_status_events"),
    ]

    mv_queries = [
        ("DWS 物化视图 (预聚合, 直接读)",
         "SELECT * FROM dws_daily_gmv ORDER BY dt"),
        ("DWD 实时聚合 (现场 GROUP BY)",
         "SELECT DATE(order_date) AS dt, COUNT(*) AS order_count, SUM(total_amount) AS gmv FROM dwd_order_fact GROUP BY DATE(order_date) ORDER BY dt"),
    ]

    # Run benchmarks
    print("=" * 60)
    print(f"YMatrix Benchmark Suite — {RUNS} runs per query")
    print(f"Data scale: {order_count:,} orders")
    print("=" * 60)

    # 1. MARS3 vs HEAP
    print("\n[1/5] Running MARS3 vs HEAP query benchmarks...")
    mh_results = []
    for label, sql_template in mars3_heap_queries:
        print(f"  {label}...")
        m3_times = run_explain_analyze(sql_template.format(table="ods_orders_mars_compare"))
        hp_times = run_explain_analyze(sql_template.format(table="ods_orders_heap"))
        m3 = fmt_times(m3_times)
        hp = fmt_times(hp_times)
        sp = speedup(m3["avg"], hp["avg"])
        mh_results.append({"label": label, "mars3": m3, "heap": hp, "speedup": sp})

    # 2. Partition pruning
    print("\n[2/5] Running partition pruning benchmarks...")
    part_results = []
    for label, sql in partition_queries:
        print(f"  {label}...")
        times = run_explain_analyze(sql)
        r = fmt_times(times)
        part_results.append({"label": label, "timing": r})

    # Capture EXPLAIN plans to prove partition pruning works
    explain_pruned = subprocess.run(PSQL + ["-c",
        "EXPLAIN SELECT COUNT(*) FROM ods_order_status_events WHERE event_time >= '2024-11-01' AND event_time < '2024-12-01';"],
        capture_output=True, text=True).stdout
    explain_full = subprocess.run(PSQL + ["-c",
        "EXPLAIN SELECT COUNT(*) FROM ods_order_status_events;"],
        capture_output=True, text=True).stdout
    # Count partitions scanned by looking for _1_prt_ in scan nodes
    pruned_count = explain_pruned.count("_1_prt_")
    full_count = explain_full.count("_1_prt_")

    # 3. Materialized view vs direct
    print("\n[3/5] Running materialized view benchmarks...")
    mv_results = []
    for label, sql in mv_queries:
        print(f"  {label}...")
        times = run_explain_analyze(sql)
        r = fmt_times(times)
        mv_results.append({"label": label, "timing": r})

    # 4. Storage already collected
    print("\n[4/5] Storage data collected.")

    # 5. ETL log already collected
    print("\n[5/5] ETL log data collected.")

    # Generate markdown report
    report = generate_markdown(order_count, mars3_bytes, heap_bytes,
                                savings_pct, partitions, etl_entries,
                                mh_results, part_results, mv_results,
                                pruned_count, full_count)

    # Write to results/
    results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
    os.makedirs(results_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    results_path = os.path.join(results_dir, f"benchmark-results-{date_str}.md")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Also write canonical name
    canonical = os.path.join(results_dir, "benchmark-results.md")
    with open(canonical, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n{'=' * 60}")
    print(f"Results written to:")
    print(f"  {results_path}")
    print(f"  {canonical}")
    print(f"{'=' * 60}")

    # Print summary
    print(report)


def generate_markdown(order_count, mars3_bytes, heap_bytes, savings_pct,
                      partitions, etl_entries, mh_results, part_results, mv_results,
                      pruned_count=1, full_count=13):
    lines = []
    lines.append(f"# YMatrix Benchmark 结果 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(f"> 数据规模: **{order_count:,}** 订单 (ods_orders)")
    lines.append(f"> 压缩对比表: {order_count * 40:,} 行 (ods_orders_mars_compare / ods_orders_heap)")
    lines.append(f"> 每查询重复: {RUNS} 次, 取平均值")
    lines.append("")

    # --- 1. 存储 ---
    lines.append("## 1. 存储压缩: MARS3 vs HEAP")
    lines.append("")
    lines.append("| 引擎 | 压缩 | 总大小 | 行数 |")
    lines.append("|------|------|--------|------|")
    lines.append(f"| MARS3 | lz4 level 7 | {pretty_size(mars3_bytes)} | {order_count * 40:,} |")
    lines.append(f"| HEAP  | 无 | {pretty_size(heap_bytes)} | {order_count * 40:,} |")
    lines.append("")
    lines.append(f"**压缩节省: {savings_pct}%** (节省 {pretty_size(heap_bytes - mars3_bytes)})")
    lines.append("")

    # --- 1b. 分区分布 ---
    lines.append("### 1b. 分区存储分布 (ods_orders)")
    lines.append("")
    lines.append("| 分区范围 | 大小 |")
    lines.append("|---------|------|")
    for rng, sz in partitions:
        lines.append(f"| {rng} | {pretty_size(sz)} |")
    lines.append("")

    # --- 2. MARS3 vs HEAP 查询 ---
    lines.append("## 2. 查询性能: MARS3 vs HEAP")
    lines.append("")
    lines.append(f"> 同一份数据 ({order_count * 40:,} 行), 仅引擎不同")
    lines.append("")
    lines.append("| 查询 | MARS3 avg (ms) | HEAP avg (ms) | MARS3 倍速 |")
    lines.append("|------|----------------|--------------|-----------|")
    for r in mh_results:
        lines.append(f"| {r['label']} | {r['mars3']['avg']} | {r['heap']['avg']} | {r['speedup']}x |")
    lines.append("")
    lines.append("<details><summary>详细计时 (min/max)</summary>")
    lines.append("")
    lines.append("| 查询 | MARS3 min | MARS3 max | HEAP min | HEAP max |")
    lines.append("|------|-----------|-----------|----------|----------|")
    for r in mh_results:
        lines.append(f"| {r['label']} | {r['mars3']['min']} | {r['mars3']['max']} | {r['heap']['min']} | {r['heap']['max']} |")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    # --- 3. 分区裁剪 ---
    lines.append("## 3. 分区裁剪: 命中单分区 vs 全表扫描")
    lines.append("")
    lines.append(f"> ods_order_status_events: {order_count * 35 // 10:,}+ 行, 13 月分区 (RANGE on event_time)")
    lines.append("")
    lines.append(f"> EXPLAIN 计划验证: 命中查询扫描 **{pruned_count} 个分区**, 全表扫描 **{full_count} 个分区**")
    lines.append("")
    lines.append("| 场景 | 扫描分区数 | avg (ms) | 说明 |")
    lines.append("|------|-----------|----------|------|")
    for r in part_results:
        cnt = pruned_count if "命中" in r["label"] else full_count
        lines.append(f"| {r['label']} | {cnt} | {r['timing']['avg']} | |")
    if len(part_results) == 2 and part_results[1]["timing"]["avg"] > 0 and part_results[0]["timing"]["avg"] > 0:
        sp = round(part_results[1]["timing"]["avg"] / part_results[0]["timing"]["avg"], 1)
        lines.append(f"| **加速比** | | **{sp}x** | 全表/命中分区 |")
    lines.append("")
    lines.append("> 注: 分区裁剪的收益随数据规模增长。20万订单级别数据量小，"
                 "单分区扫描与全表扫描差异不显著；百万级以上时分区裁剪可跳过 11/12 的数据读取。")
    lines.append("")

    # --- 4. 物化视图 ---
    lines.append("## 4. 物化视图预聚合 vs DWD 实时聚合")
    lines.append("")
    lines.append("| 场景 | avg (ms) | 说明 |")
    lines.append("|------|----------|------|")
    for r in mv_results:
        lines.append(f"| {r['label']} | {r['timing']['avg']} | |")
    if len(mv_results) == 2 and mv_results[1]["timing"]["avg"] > 0:
        sp = round(mv_results[1]["timing"]["avg"] / mv_results[0]["timing"]["avg"], 1) if mv_results[0]["timing"]["avg"] > 0 else 0
        lines.append(f"| **加速比** | **{sp}x** | 实时聚合/预聚合 |")
    lines.append("")

    # --- 5. ETL 吞吐 ---
    lines.append("## 5. ETL 各阶段吞吐")
    lines.append("")
    lines.append("| 阶段 | 行数 | 耗时 (s) | 吞吐 (rows/s) |")
    lines.append("|------|------|---------|--------------|")
    for e in etl_entries:
        rps = round(e["rows"] / (e["ms"] / 1000), 0) if e["ms"] > 0 and e["rows"] > 0 else 0
        dur = round(e["ms"] / 1000, 2)
        lines.append(f"| {e['step']} | {e['rows']:,} | {dur} | {rps:,.0f} |")
    lines.append("")

    lines.append("---")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 每查询重复 {RUNS} 次*")

    return "\n".join(lines)


if __name__ == "__main__":
    run_benchmark()
