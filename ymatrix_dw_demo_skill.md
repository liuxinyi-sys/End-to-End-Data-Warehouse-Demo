
---
name: ymatrix-dw-demo
description: "基于 YMatrix 数据库的数据仓库场景 Demo 开发指南。覆盖从业务库到数仓分层再到报表展示的完整技术栈，包括 MPP 架构、MARS3/HEAP 双引擎设计、MatrixGate 高性能写入、物化视图预聚合、流计算实时加工、联邦查询跨源集成、Grafana 监控等。"
---

# YMatrix 数仓场景 Demo 开发完整指南

官方文档: https://ymatrix.cn/zh/doc/5.2

## 一、YMatrix 核心架构概述

YMatrix（原 ZNBase）是一款基于 **PostgreSQL** 系的 MPP 分布式数据库，单库融合时序（Time-series）、分析（OLAP）、事务（OLTP）、AI 四大场景。

### 1.1 MPP 架构

- **Master 节点**：入口网关，接收 SQL、规划查询计划、协调分布式执行
- **Segment 节点**：数据存储和计算节点，并行处理
- **etcd 集群**：强一致性集群管理，实现 3 秒内故障转移
- **Mirror 机制**：数据镜像分布，支持高可用
- **非平衡部署模式**：允许异构节点混合部署

### 1.2 数据分布

- **DISTRIBUTED BY (column)**：哈希分布，相同值落在同一节点
- **DISTRIBUTED RANDOMLY**：随机分布，适合无关联查询的表
- **ORDER BY (column)**：节点内排序键，优化时序查询性能

### 1.3 双存储引擎

| 引擎 | 类型 | 适用场景 | 核心特点 |
|------|------|----------|----------|
| **HEAP** | 行存 | 维表、小表、OLTP 类工作负载 | 支持更新删除，默认引擎 |
| **MARS3** | 行列混存 | 时序数据、大规模分析 | 高性能压缩（zstd/zlib/lz4），DIMS 自适应列存，自动分区 |

> MARS3 表依赖 `matrixts` 扩展，建表前需 `CREATE EXTENSION matrixts;`

### 1.4 高级组件

| 组件 | 用途 |
|------|------|
| **MatrixGate (mxgate)** | 高性能数据加载工具，直连 Segment 写入，千万点/秒 |
| **MatrixShift (mxshift)** | 全库/增量数据迁移工具，Segment-to-Segment 传输 |
| **MatrixArchive** | 增量在线备份与恢复 |
| **MatrixUI** | 图形化运维管理面板 |
| **Domino 流计算引擎** | SQL 级实时流处理，替代 Flink/Spark |

---

## 二、数据仓库分层设计（Demo 推荐模式）

标准的数仓分层架构如下，Demo 可简化实现：

+-----------------------------------+
|  源数据层 (Source)                 |
|  MySQL / CSV / Kafka / API 等业务系统 |
+---------------^--------------------+
                |
                | mxgate / mxshift / FDW
                v
+-----------------------------------+
|  ODS 层 (操作数据存储)              |
|  原始数据镜像，按时间分区 + MARS3    |
+---------------^--------------------+
                |
                | SQL ETL
                v
+-----------------------------------+
|  DWD 层 (明细数据)                  |
|  清洗/去重/标准化后的明细数据         |
+---------------^--------------------+
                |
                | SQL 聚合 / 物化视图
                v
+-----------------------------------+
|  DWS 层 (汇总数据)                  |
|  宽表 + 预聚合指标，使用物化视图      |
+---------------^--------------------+
                |
                | SQL 查询
                v
+-----------------------------------+
|  ADS 层 (应用数据)                  |
|  面向 BI/报表的专用查询视图           |
+-----------------------------------+

---

## 三、存储引擎选型与建表最佳实践

### 3.1 建表语法要点

```sql
-- MARS3 时序表（核心数仓表）
CREATE TABLE dwd_trip (
    vendor_id        text,
    pickup_datetime  timestamp,
    dropoff_datetime timestamp,
    passenger_count  int,
    trip_distance    numeric,
    payment_type     int,
    total_amount     numeric,
    trip_duration    numeric GENERATED ALWAYS AS (
        EXTRACT(EPOCH FROM (dropoff_datetime - pickup_datetime)::INTERVAL)/60
    ) STORED
)
USING MARS3
WITH (compresstype='lz4', compresslevel=1)
DISTRIBUTED BY (vendor_id)
ORDER BY (vendor_id, pickup_datetime)
PARTITION BY RANGE (pickup_datetime)
( START (date '2024-01-01') INCLUSIVE
  END (date '2024-02-01') EXCLUSIVE
  EVERY (INTERVAL '1 day') );

-- HEAP 维表（静态配置数据）
CREATE TABLE dim_payment_type (
    payment_type int,
    description  text
) USING HEAP
DISTRIBUTED BY (payment_type);
```

### 3.2 建表关键参数

| 参数 | MARS3 值 | 说明 |
|------|----------|------|
| USING MARS3 | 时序/分析表 | 行列混存引擎 |
| USING HEAP | 维表/小表 | 行存引擎 |
| WITH (compresstype='lz4', compresslevel=1) | 压缩 | zstd(1-19)、zlib(1-9)、lz4(1-20) |
| DISTRIBUTED BY (column) | 哈希分布键 | 选择关联查询多的列 |
| ORDER BY (columns) | 排序键 | MARS3 专用，影响查询剪枝 |
| PARTITION BY RANGE | 时间范围分区 | 按天/月/年，便于 TTL 管理 |

### 3.3 自动化分区管理

```sql
-- 安装扩展
CREATE EXTENSION matrixts;

-- 启用自动分区
SELECT apm_enable_partition_maintenance();

-- 查看分区状态
SELECT * FROM apm_partition_status;
```

---

## 四、数据加载（ETL 层）

### 4.1 MatrixGate（mxgate） — 高性能写入（首选）

**服务模式**（生产推荐）：

```bash
# 1. 生成配置
mxgate config \
    --db-database dw_demo \
    --db-master-host mdw \
    --db-master-port 5432 \
    --db-user mxadmin \
    --target dwd_trip \
    --time-format raw \
    --delimiter ',' \
    > mxgate.conf

# 2. 启动服务
mxgate start --config mxgate.conf

# 3. 提交数据（HTTP API）
curl -X POST \
    -H "Content-Type: text/plain" \
    -d 'data1,2024-01-01 10:00:00,2024-01-01 10:30:00,2,5.6,1,28.5' \
    http://localhost:8090/mxgate/insert
```

**命令行模式**（批量导入）：

```bash
tail -n +2 data.csv | mxgate \
    --source stdin \
    --db-database dw_demo \
    --db-master-host mdw \
    --db-master-port 5432 \
    --db-user mxadmin \
    --time-format raw \
    --target dwd_trip \
    --parallel 256 \
    --delimiter ','
```

**编程语言 SDK 连接 mxgate**：支持 Go、Java、Python 等语言通过 SDK 直接写入 mxgate，适用于微服务场景。

### 4.2 Kafka 接入

```bash
-- 安装 Kafka 扩展
CREATE EXTENSION kafka;

-- 创建 Kafka 外表
CREATE FOREIGN TABLE kafka_trip (...)
 SERVER kafka_server
 OPTIONS (topic 'trip_data', format 'csv');
```

### 4.3 数据迁移（mxshift）

```bash
mxshift \
    --source-host old-host --source-port 5432 \
    --source-user mxadmin --source-database dw_demo \
    --dest-host new-host --dest-port 5432 \
    --dest-user mxadmin --dest-database dw_demo \
    --include-table dwd_trip
```

### 4.4 UPSERT（数据分批合并场景）

```bash
mxgate config \
    --target dwd_trip \
    --on-conflict-key vendor_id,pickup_datetime
```

### 4.5 从文件加载（小数据量测试）

```sql
COPY dwd_trip FROM '/path/to/data.csv' DELIMITER ',' CSV;
```

---

## 五、数据查询与分析

### 5.1 基本查询

YMatrix 完整兼容 PostgreSQL 查询语法，支持 JOIN、子查询、窗口函数、CTE。

```sql
-- 基本 JOIN
SELECT t.*, p.description AS payment_desc
FROM dwd_trip t
JOIN dim_payment_type p ON t.payment_type = p.payment_type
WHERE t.pickup_datetime >= '2024-01-01'
  AND t.pickup_datetime < '2024-01-02';

-- 窗口函数
SELECT vendor_id, pickup_datetime, total_amount,
       AVG(total_amount) OVER (
           PARTITION BY vendor_id
           ORDER BY pickup_datetime
           ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
       ) AS rolling_avg_fare
FROM dwd_trip;

-- CTE
WITH daily_stats AS (
    SELECT date_trunc('day', pickup_datetime) AS day,
           COUNT(*) AS trip_count,
           SUM(total_amount) AS total_revenue
    FROM dwd_trip
    GROUP BY 1
)
SELECT day, trip_count, total_revenue,
       SUM(total_revenue) OVER (ORDER BY day) AS cumulative_revenue
FROM daily_stats;
```

### 5.2 时序专用函数（time_bucket）

```sql
-- 安装时序扩展
CREATE EXTENSION matrixts;

-- 按 15 分钟窗口聚合
SELECT time_bucket('15 minutes', pickup_datetime) AS bucket,
       COUNT(*) AS trips,
       AVG(total_amount) AS avg_fare,
       AVG(trip_distance) AS avg_distance
FROM dwd_trip
WHERE pickup_datetime >= '2024-01-01'
  AND pickup_datetime < '2024-01-08'
GROUP BY bucket
ORDER BY bucket;
```

### 5.3 物化视图（预聚合 DWS 层）

```sql
-- 创建物化视图作为 DWS 层
CREATE MATERIALIZED VIEW dws_daily_trip_stats AS
SELECT
    date_trunc('day', pickup_datetime) AS day,
    vendor_id,
    payment_type,
    COUNT(*) AS trip_count,
    SUM(passenger_count) AS total_passengers,
    SUM(trip_distance) AS total_distance,
    SUM(total_amount) AS total_revenue,
    AVG(trip_distance) AS avg_distance,
    AVG(total_amount) AS avg_fare
FROM dwd_trip
GROUP BY 1, 2, 3
DISTRIBUTED BY (day);

-- 刷新物化视图
REFRESH MATERIALIZED VIEW dws_daily_trip_stats;

-- 查询预聚合数据
SELECT day, SUM(trip_count) AS trips, SUM(total_revenue) AS revenue
FROM dws_daily_trip_stats
WHERE day >= '2024-01-01' AND day < '2024-02-01'
GROUP BY day
ORDER BY day;
```

### 5.4 高级查询特性

| 特性 | 说明 | 文档 |
|------|------|------|
| 窗口函数 | ROW_NUMBER(), RANK(), LAG(), LEAD() 等 | /dataquery/advanced |
| 递归 CTE | 树形/层级数据查询 | /dataquery/basic |
| 全文搜索 | tsvector/tsquery | /reference/full_text_search |
| ORCA 优化器 | 复杂 JOIN 查询优化（默认启用） | /reference/orca |
| Runtime Filter | JOIN 动态过滤优化 | /reference/mxvector/runtimefilter |

---

## 六、流计算引擎（Domino） — 实时加工

YMatrix Domino 流计算引擎可在数据库内部以 SQL 方式处理实时数据流，无需 Flink/Spark。

### 6.1 创建流

```sql
-- 创建流（类似 Flink source）
CREATE STREAM trip_stream (
    vendor_id        text,
    pickup_datetime  timestamp,
    dropoff_datetime timestamp,
    passenger_count  int,
    trip_distance    numeric,
    payment_type     int,
    total_amount     numeric
);

-- 创建连续视图（持续聚合，类似 Flink streaming SQL）
CREATE CONTINUOUS VIEW cv_realtime_stats AS
SELECT
    time_bucket('5 minutes', pickup_datetime) AS window,
    COUNT(*) AS trips,
    SUM(passenger_count) AS passengers,
    SUM(total_amount) AS revenue,
    AVG(total_amount) AS avg_fare
FROM trip_stream
GROUP BY window;

-- 写入流数据（通过 mxgate 或 INSERT）
INSERT INTO trip_stream VALUES (...);

-- 查询实时聚合结果
SELECT * FROM cv_realtime_stats ORDER BY window DESC LIMIT 10;
```

### 6.2 滑动窗口

```sql
CREATE CONTINUOUS VIEW cv_sliding_stats AS
SELECT
    time_bucket('5 minutes', pickup_datetime) AS window,
    COUNT(*) AS trips
FROM trip_stream
WHERE pickup_datetime >= now() - INTERVAL '1 hour'
GROUP BY window;
```

**功能示例文档**：/zh/doc/5.2/reference/streaming/function_practice

---

## 七、联邦查询（跨源数据集成）

YMatrix 支持通过 FDW 和 PXF 访问外部数据源。

### 7.1 FDW 方式

```sql
-- 连接 PostgreSQL
CREATE EXTENSION postgres_fdw;
CREATE SERVER pg_oltp FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'oltp-host', port '5432', dbname 'orders');
CREATE USER MAPPING FOR mxadmin SERVER pg_oltp
    OPTIONS (user 'pg_user', password 'secret');
CREATE FOREIGN TABLE f_orders (
    order_id int, customer_id int, amount numeric
) SERVER pg_oltp
    OPTIONS (schema_name 'public', table_name 'orders');
```

支持的外部数据源：PostgreSQL、MySQL、MongoDB

### 7.2 PXF 方式（大数据生态）

支持：HDFS、Hive ORC、S3、ClickHouse、Oracle、SQL Server

### 7.3 自动化降级存储（冷热分离）

```sql
-- 将旧数据自动转移到 S3
CREATE TABLESPACE s3_tablespace
    OWNER mxadmin
    LOCATION 's3://bucket/path'
    WITH (accesskey='xxx', secretkey='xxx');

ALTER TABLE dwd_trip MOVE PARTITION FOR ('2023-01-01')
    TABLESPACE s3_tablespace;
```

---

## 八、监控与运维

### 8.1 Grafana + Prometheus 监控

YMatrix 提供 Grafana 监控面板（默认端口 3000），覆盖：
- 集群健康状态 | 查询 QPS/延迟
- CPU/内存/磁盘 | Segment 负载均衡 | mxgate 写入速率

**文档**：
- Grafana 安装：/monitor/grafana_installation
- 集群监控配置：/monitor/grafana_monitoring_configuration
- 监控指标解读：/monitor/dashboard_parameter_db

### 8.2 MatrixUI 图形化管理

浏览器访问的图形化管理界面，功能包括：一键部署、自助巡检、秒级扩容、Kafka 导入配置、负载分析、查询监控、健康监测。

文档：/zh/doc/5.2/reference/MatrixUI_use

### 8.3 备份恢复

```bash
# 全量备份
mxbackup --backup-dir /backup/dw_demo

# 增量在线备份
mxarchive start --backup-dir /backup/archive

# 恢复
mxrestore --backup-dir /backup/dw_demo
```

---

## 九、Demo 快速规划建议

### 9.1 推荐技术栈

MatrixDB 5.2.x（社区版）+ MatrixGate + Python/Node.js 应用 + Grafana/自建前端

### 9.2 最小 Demo 步骤

1. **环境准备**：安装 MatrixDB 5.2.x，创建数据库，安装 matrixts 扩展
2. **建表**：ODS 层（MARS3）+ DIM 层（HEAP）
3. **数据加载**：COPY / mxgate 加载样本数据 / Python 脚本模拟生成
4. **数仓分层 ETL**：ODS → DWD 清洗 → DWS 物化视图预聚合 → ADS 视图
5. **查询与展示**：GMV 排行、用户复购率、销售趋势分析 + 可视化

### 9.3 关键 SQL 参考

```sql
-- 日销售汇总
SELECT d.date,
       COUNT(DISTINCT o.user_id) AS paying_users,
       COUNT(o.order_id) AS orders,
       SUM(o.amount) AS gmv
FROM dwd_orders o
JOIN dim_date d ON o.order_date = d.date
WHERE d.date >= '2024-01-01'
GROUP BY d.date
ORDER BY d.date;
```

---

## 十、文档索引速查

| 主题 | URL（相对 /zh/doc/5.2/）|
|------|------------------------|
| 快速入门 | /get-started |
| 时序场景实践 | /get_started/basic_use |
| 流计算场景实践 | /get_started/streaming_use |
| MatrixGate 写入 | /datainput/matrixgate |
| 基本查询 | /dataquery/basic |
| 高级查询 | /dataquery/advanced |
| 物化视图 | /datamodel/cv |
| 存储引擎概述 | /reference/storage/overview |
| 执行引擎 | /reference/mxvector/overview |
| 流计算引擎 | /reference/streaming/capability |
| 联邦查询 | /dataquery/fdw |
| 降级存储 | /maintain/storage_degradation |
| MatrixUI | /reference/MatrixUI_use |
| 备份恢复 | /maintain/backup_restore |
| ORCA 优化器 | /reference/orca |
| 资源组 | /maintain/resgroups |
| 性能调优 | /performance_tuning/overview |
| TPC-H 报告 | /what_is_ymatrix/tpch_performance_report |
| SSB 报告 | /what_is_ymatrix/ssb_performance_report |

---

## 附录：关键概念速查

| 概念 | 说明 |
|------|------|
| MPP | 大规模并行处理，数据分布在多个 Segment 节点并行计算 |
| MARS3 | 行列混存引擎，时序/分析专用，支持压缩和 DIMS 自适应列存 |
| HEAP | PostgreSQL 原生行存引擎，支持事务、更新、删除 |
| DIMS | 动态智能存储，自适应选择行存/列存 |
| MatrixGate | 高性能加载工具，直写 Segment |
| MatrixShift | 全库/增量数据迁移工具 |
| Domino | 流计算引擎，CREATE STREAM + CONTINUOUS VIEW |
| ORCA | 复杂 JOIN 查询优化器 |
| mxvector | 向量化执行引擎 |
| FDW | 外部数据包装器 |
| PXF | 大数据平台扩展框架 |
| mxarchive | 增量在线备份工具 |
| time_bucket | 时序聚合函数 |
| 自动化分区管理 | 自动创建和删除时间分区 |
| Grafana 监控 | Prometheus + Grafana 集群监控 |
| MatrixUI | 浏览器可视化运维工具 |

---

## 参考

- 官方网站：https://ymatrix.cn
- 文档首页：https://ymatrix.cn/zh/doc/5.2
- 社区版下载：https://ymatrix.cn/download
- 版本历史：https://ymatrix.cn/zh/doc/5.2/version_list
