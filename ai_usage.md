# AI 使用说明

## 1. 使用了哪些 AI 工具

| 工具 | 版本/模型 | 用途 |
|------|----------|------|
| Codex (GPT-5) | 2026.07 | 项目设计文档、设计审阅、DDL 生成、ETL 代码、文档写作 |
| DimAgent (Claude) | 2026.07 | Plan 执行、集成测试调试、跨平台问题修复、验证报告生成 |

### 使用的 Skills

| Skill | 作用 | 使用阶段 |
|-------|------|---------|
| OpenSpec | 规范驱动开发：定义需求规格 (spec) 和实施计划 (plan)，让 AI 严格按规格而非凭直觉编码 | 设计阶段（Codex 侧）输出 spec，执行阶段对照 plan 推进 |
| Superpowers | 内含多个子技能，约束 AI 的工作方法，避免"拍脑袋"式产出 | 全流程：头脑风暴→实施→验证→调试 |

Superpowers 中实际调用的子技能：

| 子技能 | 触发场景 |
|--------|---------|
| `brainstorming` | 架构与数据合理性评审：指出 order_items 价格与商品脱钩、订单分布过于均匀、缺少时序能力等问题 |
| `verification-before-completion` | 全链路集成测试：要求在标记完成前跑通 21 项断言，并记录到 md 文档 |
| `systematic-debugging` | 根据测试报告系统化修复 bug，而非随机猜测 |

OpenSpec 产出的规格/计划文件位于 `docs/superpowers/`，例如：
- [docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md](docs/superpowers/specs/2026-07-09-ecommerce-business-timeseries-design.md)（设计规格）
- [docs/superpowers/plans/2026-07-09-ecommerce-business-timeseries-implementation.md](docs/superpowers/plans/2026-07-09-ecommerce-business-timeseries-implementation.md)（实施计划）

## 2. 关键 Prompt 示例

### 设计阶段（Codex）
```
背景 ：客⼾希望理解 YMatrix 在数仓场景中的完整使⽤⽅式。请实现⼀个从业务库到数仓分层再到报表展⽰ 
的最⼩ Demo。
现在需要你理解YMatrix 的官方文档https://ymatrix.cn/zh/doc/5.2，总结出一个skill，以便我进行demo的开发。

[$superpowers:brainstorming](C:\\Users\\82044\\.codex\\plugins\\cache\\openai-api-curated\\superpowers\\d6169bef\\skills\\brainstorming\\SKILL.md) 目标：完成数仓端到端 Demo
背景：客⼾希望理解 YMatrix 在数仓场景中的完整使⽤⽅式。请实现⼀个从业务库到数仓分层再到报表展⽰的最⼩ Demo。
要求：1. 构造⼀个业务数据库场景。建议使⽤电商场景，包含：users、products、orders、order_items、payments
2. 实现数据同步。从 MySQL 或其他业务库同步到 YMatrix。⼯具不限：DataX、Flink CDC、⾃写脚本、其他开源⼯具
3. 在 YMatrix 中完成数仓分层。⾄少包含：ODS：原始同步层、DWD：清洗明细层、DWS：汇总层、ADS：应⽤报表层
4. ⾄少实现 5 个业务指标。
⽰例：每⽇ GMV、每⽇订单数、商品销售 Top 10、⽤⼾复购率、品类销售占⽐
5. 提供展⽰⽅式。可以是：SQL 查询结果、Markdown 报告、Grafana / Superset、简单 Web ⻚⾯、截图。
需要有：
1. Git 仓库地址，或压缩包
2. README.md
3. report.md
4. ai_usage.md
5. 运⾏结果截图或⽇志。如使⽤外部服务、Docker、数据库或特殊依赖，请在 README 中说明。

目前的分层要加入DIM层
ODS（原始层）→ DWD（明细层）→ DWS（汇总层）→ ADS（应用层）
                              ↑
                           DIM（维表层）
如果有地区维度表，可以按省→市→区下钻分析 GMV 分布，展示 YMatrix 的多维度分析能力。日志/审计表 etl_log
需要针对真实电商业务场景设计表？例如双11大促

数据特征和表结构不对，表结构 中少了dim_date 、dim_region
```

### Plan 执行阶段（DimAgent）
```
[提供了 plan 文件 2026-07-09-ecommerce-business-timeseries-implementation.md]
根据 plan 文件继续执行未完成的内容，已经进行到 task3 了。
先确认当前修改到哪一步。
```

### 问题指正与修改

[$superpowers:verification-before-completion](C:\\Users\\82044\\.codex\\plugins\\cache\\openai-api-curated\\superpowers\\d6169bef\\skills\\verification-before-completion\\SKILL.md) 你来帮我进行全流程测试，遇到问题查日志检查，记录到md文档中。

[$superpowers:systematic-debugging](C:\\Users\\82044\\.codex\\plugins\\cache\\openai-api-curated\\superpowers\\d6169bef\\skills\\systematic-debugging\\SKILL.md) 根据测试报告修bug

[$superpowers:brainstorming](C:\\Users\\82044\\.codex\\plugins\\cache\\openai-api-curated\\superpowers\\d6169bef\\skills\\brainstorming\\SKILL.md) 查看当前的项目，生成的数据合理吗？是不是会生成偏差（例如商品是食品但品牌是美妆）指标正确吗？能完成向客户展示YMatrix 在数仓场景中的完整使⽤⽅式的目标吗？

1.缺少YMatrix 最核心的时序分析能力（如 time_bucket 函数、滑动窗口、毫秒级精度查询？例如将所有时间字段改为 TIMESTAMP（精确到秒甚至毫秒）。
2.数据一致性：订单价与商品价脱钩。 order_items 的 unit_price 是随机生成的（19.9~9999），与 products 表中的 price 没有任何关联。这会导致数仓 DWS 层在做“按商品品类统计GMV”时，数据逻辑出现混乱。保证数仓中“事实表”与“维度表”的外键一致性。
3.模拟流量爆发：订单分布过于均匀
脚本中除了双11前后，其余日期的订单量几乎是平均分配的（random.choice）。真实的电商场景在双11当天（第316天）的订单量应该是平日的 50 倍以上。

改进方案：给日期分配权重。例如：平日权重为1，双11当天（Day 316）权重设为100，预热期（Day 306-315）权重设为5。
演示价值：证明 YMatrix 能够轻松应对流量洪峰下的数据写入和实时查询压力。
4.订单商品数量：固定为4个不真实 ，，现实中用户可能买1件，也可能买20件。固定写死 for _ in range(4) 会让客户觉得数据很“假”。 改进方案：使用泊松分布或自定义权重随机生成 item_count。例如：random.choices([1,2,3,5,10], weights=[50,30,10,8,2])[0]。
5. 数据动态流转：缺少“状态变更流”当前 orders 的 status 是一次性生成的最终状态。实际业务中，订单会从 paid -> shipped -> completed 历经数天。

1.将订单数（num）提升至 100万 ~ 500万。对应的 order_items 明细行约为 300万 ~ 1500万行。生成脚本改为流式写入 CSV 文件，然后通过 mxgate 并行导入 MySQL业务库
2.评估order_date 改名为 order_time 的迁移成本，在 YMatrix 的 DWD 层 进行强类型转换和重命名是否更好？
3.orders.total 与 order_items.final_price 的对账逻辑缺失
4.新增 ADS 视图：ads_gmv_running_total（双11当日累计 GMV 趋势）。



```



## 3. AI 帮助完成了哪些部分

| 模块 | AI 参与程度 | 说明 |
|------|-----------|------|
| 架构设计 | 80% | 五层数仓架构、MySQL 电商场景、YMatrix 特性选型 |
| DDL SQL (9 个 init 文件) | 90% | MARS3/HEAP 双引擎、RANGE 分区、物化视图、ADS 视图 |
| Python ETL (7 个脚本) | 85% | mxgate 加载、pandas 清洗、SQL INSERT..SELECT、验证脚本 |
| 数据生成 (gen_data.py) | 100% | 可信电商数据：5 品类 25 品牌、双11加权流量、状态事件流 |
| Grafana Dashboard | 100% | 6 面板 JSON 预置配置 |
| 跨平台修复 | 50% | CRLF 行尾、mxgate TRUNCATE、时区转换、DWS 列歧义 |
| 文档写作 | 80% | README.md、report.md、ai_usage.md、config.example.yaml |
| 集成测试 | 90% | 21/21 自动化验证通过 |

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
| 10 | 未参考官方文档导致语法/参数错误 | MARS3 建表参数、`time_bucket` 用法、`mxgate` 参数与官方文档不一致 | AI 凭记忆生成 SQL，未先查阅 YMatrix 5.2 官方文档 | 人工核对 https://ymatrix.cn/zh/doc/5.2 后修正参数与语法 |
| 11 | 排查方向偏离实际根因 | 在路径相关错误上反复排查容器内/代码逻辑，迟迟未命中 | AI 看不到宿主机实际文件路径状态，把环境/路径问题误判为代码问题 | 人工指出路径问题后立即定位（如 `SEED_OUTPUT_DIR` 传递 Unix 路径给 Windows Python） |

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

实际 AI 辅助开发周期约 **3 天**，时间分配如下：

| 阶段 | AI 辅助耗时 | 说明 |
|------|------------|------|
| 设计（架构 + 数据建模 + spec/plan） | 约 1.5 天 | 约占一半时间：数仓五层架构、电商场景、YMatrix 特性选型、OpenSpec 规格 |
| 部署与排查错误（集成调试 + 跨平台修复） | 约 1.5 天 | 约占一半时间：CRLF、mxgate、时区、路径等跨平台问题 |
| 文档与总结 | 少量 | README、report、ai_usage、验证报告 |
| **合计** | **约 3 天** | |

如果不使用 AI，预计需要 **7 天以上**，主要增加在：

| 阶段 | 纯人工估计 | 膨胀原因 |
|------|-----------|---------|
| 架构设计 + spec/文档 | 2-3 天 | 需自行研读 YMatrix 文档、设计分层、撰写规格，AI 可快速产出初稿并评审 |
| DDL + ETL + 数据生成代码 | 2-3 天 | 9 个 SQL 文件 + 7 个 Python 脚本 + 可信数据生成器，纯手写量大 |
| 跨平台部署与调试 | 2-3 天 | CRLF、mxgate、时区、路径等需反复试错，AI 能从错误日志快速定位关键信息 |
| 文档与验证报告 | 1 天 | 自动化验证脚本与报告需自行编写 |

> **AI 加速最显著的部分：跨平台调试（CRLF、mxgate、时区、路径）。** AI 能快速定位错误日志中的关键信息并给出修复方案，人工排查通常需要反复试错。
>
> **AI 的主要短板：** 未参考官方文档时易生成错误参数/语法（问题 #10）；遇到路径/环境类问题易往代码逻辑方向误判，需人工指正方向（问题 #11）。这两类问题使"部署排查"阶段占用了一半时间。
