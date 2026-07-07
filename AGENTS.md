# AGENTS.md

> AI 智能体开发指南 — "不要问我能做什么，先看这个文件"

## 项目概述

构建一个从 MySQL 业务库到数仓分层再到 Grafana 仪表盘的最小可运行 Demo，展示 **YMatrix (MatrixDB)** 在数据仓库场景中的完整使用方式。

### 设计原则

- **可运行性优先**: 一个 `docker-compose up -d && bash init_all.sh` 从头跑到尾
- **Docker Compose 编排**: 三容器（MySQL + YMatrix + Grafana），零主机环境依赖
- **分层清晰**: ODS → DIM → DWD → DWS → ADS 五层明确分离（含维度层）
- **YMatrix 特性展示**: MARS3/HEAP 双引擎、mxgate 高速写入、物化视图预聚合、RANGE 分区
- **指标可见**: 所有 7 个 ADS 指标在 YMatrix 中可直接查询，Grafana 零代码展示

### 技术栈

| 类别 | 技术 | 版本 | 由来 |
|--------|--------|----------|--------|
| 业务库 | MySQL (Docker) | 8.0 | 真实电商场景，mysql_fdw 跨库查询 |
| 数仓引擎 | YMatrix (MatrixDB) | 5.2.1 社区版 | MPP 分布式，MARS3/HEAP 双引擎 |
| 同步引擎 | Python + mxgate | 3.6 / 5.2.1 | mxgate stdin 高性能写入 Segment |
| 数据处理 | pandas + numpy | 1.1.x / 1.19.x | 清洗与聚合 |
| 可视化 | Grafana | latest | 预置 Dashboard，零代码仪表盘 |
| 容器编排 | Docker Compose | 2.x | 一鍵启动三容器 |

## 目录结构与负责区域

```
D:\End-to-End-Data-Warehouse-Demo/
├── init_all.sh                # [入口] 一鍵初始化脚本。修改时确保同步 README
├── README.md                  # 项目介绍
├── AGENTS.md                   # 本文件。AI 开发者指南
├── report.md                   # 项目报告，面向客户和评委
├── ai_usage.md                 # AI 使用记录
├── docker-compose.yml          # 三容器编排: MySQL + YMatrix + Grafana
├── .gitignore
│
├── mysql/
│   └── init.sql                # 业务库 DDL + 种子数据（容器入口点）
│
├── ymatrix/
│   ├── Dockerfile               # 基于 matrixdb/centos7_demo 构建 YMatrix 镜像
│   ├── docker-entrypoint.sh     # 容器入口脚本：初始化 + 启动
│   ├── matrixdb5_5.2.1+community-1_amd64.deb  # YMatrix RPM 安装包（.deb 备用）
│   ├── init/                    # 容器入口点 initdb 脚本（按编号顺序执行）
│   │   ├── 01_init.sql          # 创建 ext, APM, dim_date 生成
│   │   ├── 02_ods.sql           # ODS 5 表 DDL (MARS3, RANGE分区, lz4)
│   │   ├── 03_dim.sql           # DIM 5 维度表 DDL (HEAP)
│   │   ├── 03_dwd.sql           # DWD 2 事实表 DDL (MARS3, RANGE分区)
│   │   ├── 04_dws.sql           # DWS 物化视图 DDL (time_bucket)
│   │   ├── 05_ads.sql           # ADS 视图 DDL (7 个业务指标)
│   │   └── 06_fdw.sql           # mysql_fdw 跨库查询（可选展示）
│   └── verify/
│       └── 01_compression.sql   # MARS3 vs HEAP 压缩率对比查询
│
├── sync/                        # 数据同步引擎
│   ├── sync_data.py             # [入口] 编排全流程：extract → transform → load
│   ├── gen_data.py              # 生成 MySQL 种子数据
│   ├── extract.py               # MySQL → DataFrame
│   ├── transform.py             # pandas 清洗逻辑
│   ├── load_ods.py              # mxgate stdin → ODS
│   ├── load_dim.py              # TRUNCATE + mxgate → DIM
│   ├── load_dwd.py              # SQL INSERT INTO...SELECT... → DWD / REFRESH MV
│   ├── verify.py                # 验证 + etl_log 写入
│   └── requirements.txt         # pandas, PyMySQL, psycopg2-binary
│
├── grafana/                     # Grafana 预置配置
│   ├── datasources/
│   │   └── ymatrix.yaml          # YMatrix (PostgreSQL) 数据源
│   └── dashboards/
│       └── ymatrix_dw_demo.json  # 预置 6 面板 Dashboard
│
├── docs/
│   ├── supplementary.md          # 补充文档：设计决策记录
│   └── superpowers/plans/       # 实施计划文件
│
├── screenshots/                  # 运行结果截图
│
├── data/                         # Docker volumes (gitignored)
│
├── sql/                          # （历史遗留）旧 SQLite 方案文件
│   ├── business/
│   ├── warehouse/
│   └── metrics/
│
└── dashboard/                    # （历史遗留）旧 Flask 仪表盘
    ├── app.py
    └── templates/
```

## 常用命令

### 开发循环

```bash
# 一鍵全链路（启动容器 + 建表 + 生成数据 + ETL）
docker-compose up -d && bash init_all.sh

# 只重启 ETL（不重启容器）
cd sync && python sync_data.py && cd ..

# 只重启仪表盘（浏览器刷新 Grafana:3000 即可）
# Grafana 预置数据源和面板，连接 YMatrix 自动加载数据
```

### SQL 查询 (YMatrix)

```bash
# 查看所有表
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "\dt"

# 查看 ADS 指标
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "SELECT * FROM ads_daily_gmv ORDER BY dt LIMIT 10"

# 查看 ETL 日志
docker-compose exec ymatrix psql -U mxadmin -d dw_demo -c "SELECT * FROM etl_log ORDER BY log_id"
```

### SQL 查询 (MySQL)

```bash
# 查看业务库行数
docker-compose exec mysql mysql -uroot -proot -D ecommerce -e "SELECT COUNT(*) FROM orders"
```

### 清理

```bash
# 彻底重来
docker-compose down -v
docker-compose up -d
bash init_all.sh
```

### 镜像构建

```bash
# 单独构建 YMatrix 镜像（首次或更新软件包后）
docker-compose build ymatrix
```

## 编程规范

### SQL (YMatrix/PostgreSQL)

- 大写关键词（SELECT, FROM, WHERE, GROUP BY, JOIN, AS）
- 表名小写下划线（snake_case）
- 表名前缀按层级：无前缀(业务库)、ods_、dwd_、dws_、ads_、dim_
- 字段名小写下划线
- 使用单引号包含字符串字面量
- ODS/DWD 表使用 `USING MARS3` 引擎，DIM 表使用 `USING HEAP`
- ODS/DWD 表添加 `lz4` 压缩和 RANGE 分区
- 所有表添加 `DISTRIBUTED BY (主键)` 分布键
- DWS 层优先使用 `CREATE MATERIALIZED VIEW` + `REFRESH`
- 使用 `time_bucket()` 函数展示 YMatrix 时序能力

### Python

- 使用 Python 3.6 特性（如 f-string）
- 数据库连接：psycopg2 连接 YMatrix，PyMySQL 连接 MySQL
- 数据加载：mxgate --source stdin 子进程方式写入
- 名称空间：pandas + numpy + 标准库，不引入 Spark/Flink 等
- 错误处理：关键步骤用 try-except 包裹，写入 etl_log
- 日志：使用 print (console demo，不必 logging)

### Docker

- 不修改 docker-compose.yml 中的服务名（mysql, ymatrix, grafana）
- 不小修改 ymatrix/Dockerfile 的基础镜像（matrixdb/centos7_demo）
- 不删除 ymatrix/docker-entrypoint.sh 中的初始化逻辑
- 不修改 mysql 的 root 密码（root, 与 docker-compose 一致）
- 新加的 init SQL 文件必须放在 ymatrix/init/ 目录并按编号前缀命名

## 边界与约束

### 不能碰的区域

- `.git/` 目录下的任何文件
- `.codex/` 和 `.agents/` 目录下的配置文件
- `openspec/` 下的配置文件和规范

### 不应该做的事

- 不引入 Spark / Flink / Kafka 等大型框架（违背最小 Demo 定位）
- 不要求主机安装 YMatrix 或 MySQL（全容器化）
- 不写单元测试（以集成验证为主，范围外）
- 不增加复杂 CI/CD 配置
- 不修改数据库连接信息的编码方式

### 安全觸發器

- 如果增加新的 Python 依赖（如新的数据库驱动），必须更新 sync/requirements.txt
- 如果修改 ymatrix/init/ 下的 SQL 文件编号，必须同时更新 init_all.sh 中的执行顺序
- 如果增加新的数仓层，必须在 ymatrix/init/ 下新建 .sql 文件并在 init_all.sh 中注册
- 如果增加新的业务指标，必须在 ADS 层定义视图并更新 README 中的指标列表
- 如果修改 docker-compose.yml 中的端口映射，必须同时更新 init_all.sh 和 README

## Git 工作流

```bash
# 分支命名规范
git checkout -b codex/<feature-name>

# 提交规范
git add .
git commit -m "feat: <简短描述>"

# 推送
git push origin HEAD
```

### 不要做

- 不要 `git rebase` 已推送的分支
- 不要 `git reset --hard` （除非显式要求）
- 不要 revert 用户的现有修改

## 验证检查点

在认为工作已完成之前，执行以下检查:

1. `docker-compose up -d` 三容器启动成功（MySQL + YMatrix + Grafana）
2. `bash init_all.sh` 能从头跑到底且输出正确
3. MySQL 5 表行数符合预期（users 1000, products 500, orders 50000, order_items 200000, payments 50000）
4. YMatrix 四层对象完整（ODS 5 + DIM 5 + DWD 2 + DWS 3 + ADS 7）
5. ADS 层 7 个指标数据在合理范围内（各查询返回非空结果）
6. Grafana http://localhost:3000 正常访问，6 个面板图表正确渲染
7. MARS3 相比 HEAP 至少节省 50% 存储空间
8. etl_log 记录全链路分步耗时
9. .gitignore 已包含 data/ 和 Docker volumes

---

*本文件使用 AI 协作维护。如果发现过时信息，请更新并提交。*
