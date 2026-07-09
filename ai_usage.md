# AI 使用说明

## 1. 使用了哪些 AI 工具

| 工具 | 版本/模型 | 用途 |
|------|----------|------|
| Codex (GPT-5) | 2026.07 | 项目设计文档、设计审阅、DDL 生成、ETL 代码、文档写作 |
| DimCode (Claude) | 2026.07 | Plan 执行、集成测试调试、跨平台问题修复、验证报告生成 |

## 2. 关键 Prompt 示例

### 设计阶段（Codex）
```
[提供了 YMatrix SKILL.md 和现有设计文档]
帮我看当前的设计还有什么遗漏？
输出: 27 条遗漏清单，按 7 类分，含阻塞级 3 条
```

### Plan 执行阶段（DimCode）
```
[提供了 plan 文件 2026-07-09-ecommerce-business-timeseries-implementation.md]
根据 plan 文件继续执行未完成的内容，已经进行到 task3 了。
先确认当前修改到哪一步。
```

### 跨平台问题诊断（DimCode）
```
mxgate loaded 0 of 1000 rows into ods_users
all 1000 first rows in this segment were rejected
→ 诊断: Windows CRLF 行尾导致 mxgate 解析失败
→ 修复: csv.writer lineterminator="\n" + .gitattributes eol=lf
```

### 时区问题诊断（DimCode）
```
no partition of relation "dwd_order_fact" found for row
Partition key (order_date) = (2023-12-31)
→ 诊断: TIMESTAMP(3) 无时区列 + AT TIME ZONE 导致 UTC 偏移
→ 修复: ODS 时间已是本地时间，直接使用不做时区转换
```

## 3. AI 帮助完成了哪些部分

| 模块 | AI 参与程度 | 说明 |
|------|-----------|------|
| 架构设计 | 100% | 五层数仓架构、MySQL 电商场景、YMatrix 特性选型 |
| DDL SQL (9 个 init 文件) | 90% | MARS3/HEAP 双引擎、RANGE 分区、物化视图、ADS 视图 |
| Python ETL (7 个脚本) | 85% | mxgate 加载、pandas 清洗、SQL INSERT..SELECT、验证脚本 |
| 数据生成 (gen_data.py) | 100% | 可信电商数据：5 品类 25 品牌、双11加权流量、状态事件流 |
| Grafana Dashboard | 100% | 6 面板 JSON 预置配置 |
| 跨平台修复 | 100% | CRLF 行尾、mxgate TRUNCATE、时区转换、DWS 列歧义 |
| 文档写作 | 100% | README.md、report.md、ai_usage.md、config.example.yaml |
| 集成测试 | 100% | 21/21 自动化验证通过 |

## 4. AI 生成内容中出现过的问题

| # | 问题 | 表现 | 根因 | 修正方式 |
|---|------|------|------|---------|
| 1 | 连续视图语法错误 | CREATE VIEW WITH (CONTINUOUS) 不兼容 | YMatrix 5.2 社区版限制 | 改为标准 MATERIALIZED VIEW + REFRESH |
| 2 | DWS 列引用歧义 | `order_date` 在 JOIN 两表中都存在 | 物化视图 JOIN 未限定表别名 | 添加 `d.order_date` 表别名 |
| 3 | Windows CRLF 污染 | mxgate 拒绝所有行 | `csv.writer` 默认 `\r\n` 行尾 | `lineterminator="\n"` + `.gitattributes` |
| 4 | mxgate 重复加载 | 压缩样本表行数翻倍 | 加载前未 TRUNCATE | `_gate()` 函数开头加 `TRUNCATE` |
| 5 | TIMESTAMP 时区偏移 | 分区键 `2023-12-31` 超出范围 | `AT TIME ZONE` 对无时区列做 UTC 偏移 | ODS 时间已是本地，直接使用 |
| 6 | SEED_OUTPUT_DIR 路径错误 | Git Bash Unix 路径传给 Windows Python | `$(pwd)` 返回 `/d/...` | 移除该环境变量，用 Python 默认值 |
| 7 | MySQL LOAD DATA CRLF | `status` 字段值含 `\r` | CSV CRLF + `LINES TERMINATED BY '\n'` | gen_data.py 输出 LF 行尾 |
| 8 | verify.py 阈值过时 | region 检查 `== 4` 失败 | 旧 5 城市改为 10 城市 | 更新为 `>= 5` |
| 9 | 批量文件转换 bug | Python 脚本清空文件 | `open(f,'wb')` 先截断再读 | 从 git restore 恢复 |

## 5. 你如何验证和修正

1. **自动化验证脚本**: verify.py 执行 21 项断言检查，覆盖行数、压缩率、时区对齐、金额对账、流量突发等
2. **集成测试**: `docker-compose down -v && docker-compose up -d && bash init_all.sh` 从零跑全链路
3. **SQL 证据**: 直接查询 ADS 层验证指标数据合理性（双11 GMV、状态漏斗、促销对比等）
4. **Grafana 健康检查**: `curl http://localhost:3000/api/health` 确认可视化层正常
5. **迭代修复**: 每次发现问题后修改代码 → 重新运行 → 检查结果，共经历 7 轮迭代

### 验证结果

```
21/21 passed
ETL 总耗时: 78.9 秒
MARS3 压缩节省: 83.2%
Grafana: {"database":"ok"}
```

## 6. 如果不使用 AI，预计需要多久完成

| 阶段 | AI 辅助 | 纯人工估计 | 节省倍数 |
|------|---------|-----------|---------|
| 架构设计 + 文档 | 2h | 8-12h | 5x |
| DDL + ETL 代码 | 3h | 16-20h | 6x |
| 数据生成器 | 1h | 6-8h | 7x |
| 跨平台调试 | 2h | 8-12h | 5x |
| 文档 + 验证报告 | 1h | 4-6h | 5x |
| **总计** | **~9h** | **42-58h** | **~5x** |

> 注：跨平台调试（CRLF、mxgate、时区）是 AI 加速最显著的部分。AI 能快速定位错误日志中的关键信息并给出修复方案，人工排查通常需要反复试错。
