# AGENTS.md

> AI 智能体开发指南 — “不要问我能做什么，先看这个文件”

## 项目概述

这是一个展示 YMatrix 在数据仓库场景中完整使用方式的最小 Demo。模拟从电商业务库到数仓分层再到报表展示的完整数据链路。

### 设计原则

- **可运行性优先**: 无外部服务依赖，一个 `python init_all.py` 从头跑到尾
- **SQLite 作为默认引擎**: 用于模拟 MySQL + YMatrix，SQL 保持 PostgreSQL 兼容
- **分层清晰**: ODS → DWD → DWS → ADS 四层明确分离
- **指标可见**: 所有指标在 ADS 层可直接查询

### 技术栈

| 类别 | 技术 | 版本 | 由来 |
|--------|--------|----------|--------|
| 业务库 | SQLite | 3.x (内置) | 模拟 MySQL，无外部依赖 |
| 数仓 | SQLite | 3.x (内置) | 模拟 YMatrix/PostgreSQL，SQL 兼容 |
| 同步引擎 | Python + SQLAlchemy | 3.11 / 1.4.39 | 数据抽取与加载 |
| 数据处理 | pandas + numpy | 1.5.3 / 1.24.3 | 清洗与聚合 |
| Web 框架 | Flask + Jinja2 | 2.2.2 / 3.1.2 | 仪表盘后端 |
| 可视化 | Plotly | 5.9.0 | 交互式图表 |

## 目录结构与负责区域

```
D:\End-to-End-Data-Warehouse-Demo/
├── init_all.py              # [入口] 一键初始化。修改时需确保同步更新 README
├── README.md                # 项目介绍。访问频率最高的文档
├── AGENTS.md                 # 本文件。AI 开发者指南
├── report.md                 # 项目报告，面向客户和评委
├── ai_usage.md               # AI 使用记录，展示使用 AI 的过程
│
├── sql/
│   ├── business/            # 业务库 DDL+DML。包含建表和示例数据
│   ├── warehouse/           # 数仓 DDL。按分层编号：01_ods, 02_dwd, 03_dws, 04_ads
│   └── metrics/             # 业务指标 SQL。只读查询，不包含 DDL
│
├── sync/                     # 数据同步引擎。包含抽取、清洗、加载全链路
│   ├── sync_data.py         # [核心] 主逻辑文件，同时担当命令行入口
│   └── requirements.txt     # 依赖声明文件
│
├── dashboard/                 # Web 仪表盘
│   ├── app.py               # Flask 应用
│   └── templates/
│       └── index.html         # Plotly 图表嵌入的 HTML
│
├── data/                      # 运行时生成的数据库文件
│   ├── business.db          # Git-ignored
│   └── warehouse.db         # Git-ignored
│
├── screenshots/              # 截图文件。仅 git add 时更新
│
├── docker-compose.yml         # (可选) Docker 配置，用于真实 YMatrix+MySQL
└── .gitignore
```

## 常用命令

### 开发循环

```bash
# 从头运行全链路
python init_all.py

# 只重启数据同步（不重建库）
python sync/sync_data.py --sync

# 只启动仪表盘（不重新同步）
python dashboard/app.py
```

### SQL 查询

```bash
# 查看数据库所有表
python -c "import sqlite3; c=sqlite3.connect('data/warehouse.db'); [print(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]"

# 查看某个表
python -c "import sqlite3; c=sqlite3.connect('data/warehouse.db'); [print(r) for r in c.execute('SELECT * FROM ads_daily_gmv ORDER BY dt')]"
```

### 清理

```bash
# 删除数据库文件（彻底重来）
rm data/business.db data/warehouse.db
python init_all.py
```

## 编程规范

### SQL

- 大写关键词（SELECT, FROM, WHERE, GROUP BY, JOIN, AS）
- 表名小写下划线（snake_case）
- 表名前缀按层级：无前缀(业务库)、ods_、dwd_、dws_、ads_
- 字段名小写下划线
- 使用单引号包含字符串字面量
- 尽量使用标准 SQL，避免数据库特有语法

### Python

- 使用 Python 3.11+特性（如 f-string）
- 名称空间主要使用 Python 标准库 + SQLAlchemy + pandas
- 避免引入外部大型框架（Spark、Flink 等）
- 错误处理：关键步骤用 try-except 包裹，输出清晰错误信息
- 日志：使用 print (console demo，不必 logging)

### 数据库

- 不修改数据库连接方式（硬编码 SQLite 路径）
- 不直接在业务库上执行汇总查询（数仓分层的核心价值）
- 不修改 .db 文件的相对路径（data/ 下）

## 边界与约束

### 不能碰的区域

- `.git/` 目录下的任何文件
- `.codex/` 和 `.agents/` 目录下的配置文件
- `openspec/` 下的配置文件和规范

### 不应该做的事

- 不引入 Spark / Flink / Kafka 等大型框架（违背最小 Demo 定位）
- 不使用 Docker 作为必要依赖（可选）
- 不写单元测试（范围外，可在后续规划中提及）
- 不增加复杂 CI/CD 配置
- 不修改数据库连接信息的编码方式（硬编码相对路径）

### 安全触触脑

- 如果需要增加新的数据库驱动（如 psycopg2 或 pymysql），必须更新 requirements.txt
- 如果需要修改数据库连接路径，必须同时更新 init_all.py 和 sync_data.py
- 如果增加新的数仓层，必须在 sql/warehouse/ 下新建 .sql 文件并在 sync_data.py 中注册
- 如果增加新的业务指标，必须在 ADS 层定义表结构并更新 README 中的指标列表

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

1. `python init_all.py` 能从头跑到底且输出正确
2. 所有表在数据库中存在且行数合理
3. ADS 层指标数据在合理范围内
4. 仪表盘 http://127.0.0.1:5000 正常访问且图表正确渲染
5. .gitignore 已包含 data/*.db 和 其他未必要文件

---

*本文件使用 AI 協作维护。如果发现过时信息，请更新并提交。*
