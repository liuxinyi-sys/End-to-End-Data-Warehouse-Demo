# YMatrix 数仓端到端 Demo

## 项目目标

构建一个从**业务库到数仓分层再到 Grafana 报表展示**的最小可运行 Demo，
完整展示 YMatrix 在数据仓库场景中的使用方式。

**评分维度**: 可运行性 / 场景理解 / 工程完整度 / 测试与验证 / AI 使用能力 / 报告与表达

## 环境依赖

| 组件 | 版本 | 用途 |
|------|------|------|
| Docker Desktop | 20.10+ | 容器编排 |
| Python | 3.6 | ETL 脚本 |
| MySQL 8.0 | Docker 镜像 | 模拟业务库 |
| MatrixDB 5.2.1 | .deb 包 + Dockerfile 构建 | 数仓引擎 |
| Grafana | Docker 镜像 | 可视化仪表盘 |

## 安装步骤

### 1. 克隆仓库
```bash
git clone git@github.com:liuxinyi-sys/End-to-End-Data-Warehouse-Demo.git
cd End-to-End-Data-Warehouse-Demo
```

### 2. 验证 MatrixDB 安装包完整性
```bash
certutil -hashfile ymatrix/matrixdb5_5.2.1+community-1_amd64.deb MD5
# 期望值: 4e4ac2df9792d1ef91628525f4f30614
```

### 3. 启动服务
```bash
docker-compose build   # 构建 MatrixDB 镜像（含 .deb 安装）
docker-compose up -d   # 启动 MySQL + YMatrix + Grafana
```

### 4. 初始化数仓
```bash
bash init_all.sh       # 一键初始化: init SQL -> 生成数据 -> ETL -> 验证
```

## 配置说明

### docker-compose.yml
- **MySQL**: 端口 3306，用户 root，密码 root
- **YMatrix**: 端口 5432，用户 mxadmin，数据库 dw_demo
- **Grafana**: 端口 3000，初始用户 admin/admin

### 初始化 SQL 顺序
```
ymatrix/init/
├── 01_init.sql        # CREATE EXTENSION matrixts, APM, dim_date 生成
├── 02_ods.sql         # ODS 5 表 DDL
├── 03_dim.sql         # DIM 5 表 DDL
├── 04_dwd.sql         # DWD 2 事实表 DDL
├── 05_dws.sql         # 物化视图 DDL
├── 06_ads.sql         # ADS 视图 DDL
└── 07_fdw.sql         # mysql_fdw（可选）
```

## 运行方式

### 一键初始化
```bash
bash init_all.sh
```

### 分步执行
```bash
# 1. 初始化 YMatrix 数据库对象
for f in ymatrix/init/*.sql; do
    docker-compose exec -T ymatrix psql -U mxadmin -d dw_demo -f /docker-entrypoint-initdb.d/$(basename $f)
done

# 2. 生成业务数据并执行 ETL
cd sync && python gen_data.py && python sync_data.py

# 3. 验证
python verify.py
cd ..
```

## 示例输出

Grafana 仪表盘: [http://localhost:3000](http://localhost:3000)
- 每日 GMV 趋势（折线图）
- 商品销售 Top 10（表格）
- 品类销售占比（饼图）
- 用户复购率（单值 Stat）
- GMV 按省份分布（Treemap）
- 促销 vs 日常对比（柱状图）
- 用户价值分层（饼图）

## 已知限制

- **单节点部署**: 仅演示单台 Docker 容器，不涉及 MPP 集群扩展
- **批量 ETL 模式**: 使用标准物化视图 + REFRESH，非实时流式处理
- **模拟数据**: 50K 订单 / 200K 明细，非真实业务数据
- **无 HA/容错**: 未配置 Mirror / 数据备份
