# 补充文档

## 1. 本次作业的核心目标

构建一个最小的、可运行的**数据仓库端到端 Demo**，
展示 **YMatrix (MatrixDB) 在数仓场景**中的完整使用链路：
从业务数据库（MySQL）到数仓分层（ODS → DWD → DWS → ADS），
最终输出为 Grafana 可视化仪表盘。

## 2. 我做了哪些关键判断

### 决策 1: mxgate stdin 模式 vs 服务模式
- **选择**: mxgate --source stdin 命令模式
- **理由**: 更轻量，不需要先启动 mxgate 服务 + HTTP API 监听，适合批处理脚本
- **放弃**: 服务模式（生产推荐），需要额外的 mxgate config + mxgate start 步骤，Demo 场景无必要

### 决策 2: CREATE MATERIALIZED VIEW 而非 CREATE VIEW WITH (CONTINUOUS)
- **选择**: 标准物化视图 + REFRESH
- **理由**: SKILL.md 明确区分了两种场景——MATERIALIZED VIEW 用于 DWS 层批处理（§5.3），CONTINUOUS VIEW 用于 Domino 实时流计算（§6.1）
- **放弃**: 连续视图虽然自动刷新，但不支持多表 JOIN，且时序批处理场景无需实时

### 决策 3: Docker Compose 容器化部署 vs 手动安装
- **选择**: Docker Compose 三容器（MySQL + YMatrix + Grafana）
- **理由**: 零依赖宿主机环境，一键启动，最简复现路径
- **放弃**: 手动安装 YMatrix + MySQL + Grafana（步骤多、环境不一致、不易复现）

### 决策 4: 全量 TRUNCATE + mxgate 而非 CDC 增量同步
- **选择**: 每日全量刷新
- **理由**: Demo 数据量仅 50K 订单 / 200K 明细，全量耗时 < 30s，幂等性好
- **放弃**: CDC 增量同步（Debezium / Maxwell），复杂度高，维表仅 < 1000 行无增量意义

### 决策 5: .deb 安装包 + Ubuntu 镜像而非 yum/RPM 或官方 Docker 镜像
- **选择**: Ubuntu 20.04 + .deb 包构建
- **理由**: 获取到的是 Ubuntu 20.04 的 .deb 包，与 Docker Hub 镜像 tag 损坏不可用的现实一致
- **放弃**: centos:7 + RPM（源文档方案，与获取的 .deb 包不匹配），以及 Docker Hub 镜像（pull 报 manifest 错误）

## 3. 我验证过的场景

### 正常场景
- ✅ MD5 校验通过（文件完整性）
- ✅ 设计文档 24/24 项验证通过
- ✅ SKILL.md 语法对比一致（物化视图、DIM 引擎、压缩参数）
- ✅ 字段映射与衍生逻辑完整性（4 个衍生字段有定义）

### 异常场景
- **Docker pull 失败**: matrixdb/matrixdb-community:v5.3.3-v0.13.0 报 manifest 校验错误
  → 处理: 改用 .deb 包 + Dockerfile 自建镜像
- **连续视图语法不兼容**: CREATE VIEW WITH (CONTINUOUS) 语法验证不通过
  → 处理: 切换为标准物化视图 + REFRESH（配 SKILL.md 验证）
- **DIM 引擎选择错误**: 原设计全部使用 MARS3，但 SKILL.md 明确建议维表用 HEAP
  → 处理: 修正为 USING HEAP
- **编码问题**: PowerShell heredoc 写入 UTF-8 编码异常，中文和特殊字符丢失
  → 处理: 改用管道 stdin 方式直接执行 Python

### 边界条件
- **分区边界**: ODS 和 DWD 表按天分区覆盖 2024-01-01 ~ 2025-01-01，精确到天，确保边界数据无遗漏
- **幂等性**: 每次全量 TRUNCATE + 重载，重跑不会产生重复数据
- **时间戳类型**: time_bucket 仅支持 TIMESTAMP，订单日期为 DATE 类型 → 改用 date_trunc
- **空值处理**: 必填字段为 NULL 跳过写入 etl_log，可选字段填默认值
