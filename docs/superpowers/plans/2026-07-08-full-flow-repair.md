# Full-Flow Demo Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing-local-image YMatrix Demo pass clean and repeated end-to-end initialization, warehouse verification, and Grafana provisioning.

**Architecture:** Keep the current three-container topology and `ymatrix5.2-clean:latest`. Repair each component boundary with fail-fast shell orchestration, deterministic seed generation, MatrixDB-compatible monthly partitioned DDL, and explicit Grafana provisioning. Use integration checks instead of unit tests, as required by `AGENTS.md`.

**Tech Stack:** Docker Compose, Bash, Python 3.6-compatible code, MySQL 8.0, YMatrix 5.2.1, mxgate, PostgreSQL SQL, Grafana provisioning.

---

### Task 1: Create Isolated Worktree And Failing Preflight

**Files:**
- Create: `.worktrees/fix-full-flow`
- Create: `verify/preflight.ps1`
- Reference: `docs/full-flow-test-report-2026-07-08.md`

- [ ] **Step 1: Create the worktree**

Run:

```powershell
git worktree add .worktrees/fix-full-flow -b codex/fix-full-flow 14689dd
```

Expected: a clean worktree on `codex/fix-full-flow` containing the approved design.

- [ ] **Step 2: Write failing static integration checks**

Create `verify/preflight.ps1` to assert:

```powershell
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Assert-Contains($path, $pattern, $message) {
    if (-not (Select-String -Path (Join-Path $root $path) -Pattern $pattern -Quiet)) {
        throw $message
    }
}

Assert-Contains 'docker-compose.yml' 'ymatrix/init:/docker-entrypoint-initdb.d:ro' 'YMatrix SQL mount missing'
Assert-Contains 'docker-compose.yml' 'grafana/dashboards:/etc/grafana/provisioning/dashboards' 'Grafana dashboard mount missing'
Assert-Contains 'init_all.sh' 'ON_ERROR_STOP=1' 'YMatrix SQL is not fail-fast'
Assert-Contains 'ymatrix/init/01_init.sql' 'season VARCHAR\(10\)' 'season column is too short'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(user_id\)' 'ods_users lacks a MARS3 order key'
Assert-Contains 'ymatrix/init/02_ods.sql' 'ORDER BY \(product_id\)' 'ods_products lacks a MARS3 order key'

$dashboardProvider = Join-Path $root 'grafana/dashboards/provider.yaml'
if (-not (Test-Path $dashboardProvider)) { throw 'Grafana dashboard provider missing' }

Write-Output 'Preflight checks passed'
```

- [ ] **Step 3: Run preflight and verify RED**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File verify/preflight.ps1
```

Expected: FAIL with `YMatrix SQL mount missing`.

- [ ] **Step 4: Commit the failing check**

```powershell
git add verify/preflight.ps1
git commit -m "test: add full-flow preflight checks"
```

### Task 2: Repair Compose And YMatrix Entrypoint

**Files:**
- Modify: `docker-compose.yml`
- Modify: `ymatrix/docker-entrypoint.sh`
- Test: `verify/preflight.ps1`

- [ ] **Step 1: Add required mounts and remove redundant plugin install**

Update the YMatrix volumes to include:

```yaml
volumes:
  - ./ymatrix/docker-entrypoint.sh:/docker-entrypoint.sh:ro
  - ./ymatrix/init:/docker-entrypoint-initdb.d:ro
```

Remove `GF_INSTALL_PLUGINS`. Keep ports, service names, credentials, and local image unchanged.

- [ ] **Step 2: Strengthen the YMatrix health check**

Use a real query against `dw_demo`:

```yaml
healthcheck:
  test: ["CMD-SHELL", "PGPASSWORD=mxadmin123 /opt/ymatrix/matrixdb5/bin/psql -h localhost -p 5432 -U mxadmin -d dw_demo -tAc 'SELECT 1' | grep -qx 1"]
```

- [ ] **Step 3: Replace the entrypoint with deterministic startup**

Implement `set -euo pipefail`, start SSH, source `greenplum_path.sh`, set `MASTER_DATA_DIRECTORY`, run `gpstart -a` only when dispatch SQL is unavailable, wait up to 120 seconds for `postgres`, create `dw_demo` only when absent, set the password, then wait on the master process. Use `su - mxadmin -c` for local administrative SQL so ident authentication succeeds.

- [ ] **Step 4: Run shell and Compose checks**

Run:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -n ymatrix/docker-entrypoint.sh
docker-compose config --quiet
```

Expected: both commands exit 0.

- [ ] **Step 5: Commit**

```powershell
git add docker-compose.yml ymatrix/docker-entrypoint.sh
git commit -m "fix: make ymatrix startup deterministic"
```

### Task 3: Make Seed Generation Exact And Initialization Idempotent

**Files:**
- Modify: `sync/gen_data.py`
- Modify: `init_all.sh`
- Modify: `README.md`
- Test: generated SQL counts and repeated script behavior

- [ ] **Step 1: Verify current seed cardinality RED**

Run:

```powershell
Push-Location sync
python gen_data.py
Pop-Location
Select-String sync/seed_order_items.sql -Pattern '^\(' | Measure-Object
Select-String sync/seed_payments.sql -Pattern '^\(' | Measure-Object
```

Expected: item/payment counts differ from 200000/50000.

- [ ] **Step 2: Generate exactly four items per order**

In `gen_orders`, generate four order-item rows for every order while retaining random product, quantity, price, promotion discount, and total calculation. Generate one completed payment for every order. Keep `random.seed(42)` and Python 3.6 syntax.

- [ ] **Step 3: Add idempotent resets to `init_all.sh`**

Before loading seeds:

```bash
docker-compose exec -T mysql mysql -uroot -proot -D ecommerce -e \
  "SET FOREIGN_KEY_CHECKS=0; TRUNCATE TABLE payments; TRUNCATE TABLE order_items; TRUNCATE TABLE orders; TRUNCATE TABLE products; TRUNCATE TABLE users; SET FOREIGN_KEY_CHECKS=1;"
```

Before replaying YMatrix DDL, drop the seven ADS views, three DWS materialized views, DWD tables, DIM tables, ODS tables, `dim_date`, and `etl_log` with `IF EXISTS ... CASCADE`. Execute numbered SQL files with TCP and `-v ON_ERROR_STOP=1`.

- [ ] **Step 4: Verify exact generated counts GREEN**

Run the generator and parse each `INSERT` file. Expected: users 1000, products 500, orders 50000, order_items 200000, payments 50000.

- [ ] **Step 5: Synchronize README workflow text**

Document that `init_all.sh` is safe to rerun and that this configuration requires `ymatrix5.2-clean:latest` locally.

- [ ] **Step 6: Commit**

```powershell
git add sync/gen_data.py init_all.sh README.md
git commit -m "fix: make demo data loading deterministic"
```

### Task 4: Repair YMatrix DDL Compatibility And Resource Footprint

**Files:**
- Modify: `ymatrix/init/01_init.sql`
- Modify: `ymatrix/init/02_ods.sql`
- Modify: `ymatrix/init/03_dwd.sql`
- Modify: `ymatrix/init/06_fdw.sql`
- Test: `verify/preflight.ps1`, SQL execution in YMatrix

- [ ] **Step 1: Verify DDL defects RED**

Run `verify/preflight.ps1` and confirm failure on `season VARCHAR(10)` or a missing MARS3 order key after Compose defects are fixed.

- [ ] **Step 2: Repair mandatory initialization**

Keep `CREATE EXTENSION IF NOT EXISTS matrixts`. Remove mandatory `postgres_fdw` creation and `apm_enable_partition_maintenance()`. Change `season` to `VARCHAR(10)`.

- [ ] **Step 3: Add all MARS3 order keys**

Add `ORDER BY (user_id)` to `ods_users` and `ORDER BY (product_id)` to `ods_products`. Preserve the existing order keys on all other MARS3 tables.

- [ ] **Step 4: Reduce date partition fan-out**

Change date RANGE clauses in `ods_orders`, `dwd_order_fact`, and `dwd_order_detail_fact` from `EVERY (INTERVAL '1 day')` to `EVERY (INTERVAL '1 month')`. Keep the 2024 boundaries and daily DWS aggregation.

- [ ] **Step 5: Make FDW optional**

Wrap `06_fdw.sql` so unsupported `mysql_fdw` emits a notice and does not abort the core path. Do not query MySQL directly for ADS data.

- [ ] **Step 6: Verify preflight GREEN**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File verify/preflight.ps1
```

Expected: `Preflight checks passed`.

- [ ] **Step 7: Commit**

```powershell
git add ymatrix/init verify/preflight.ps1
git commit -m "fix: align warehouse ddl with matrixdb"
```

### Task 5: Provision Grafana Dashboard

**Files:**
- Create: `grafana/dashboards/provider.yaml`
- Modify: `grafana/datasources/ymatrix.yaml`
- Validate: `grafana/dashboards/ymatrix_dw_demo.json`

- [ ] **Step 1: Verify provider RED**

Run preflight before creating the provider. Expected: FAIL with `Grafana dashboard provider missing`.

- [ ] **Step 2: Add the dashboard provider**

Create:

```yaml
apiVersion: 1
providers:
  - name: YMatrix DW Demo
    orgId: 1
    folder: YMatrix
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /etc/grafana/provisioning/dashboards
```

- [ ] **Step 3: Supply YMatrix credentials**

Set `secureJsonData.password` to the configured Demo password `mxadmin123` and keep SSL disabled.

- [ ] **Step 4: Validate provisioning files**

Run JSON parsing and Compose config validation. Expected: dashboard JSON reports six panels and Compose exits 0.

- [ ] **Step 5: Commit**

```powershell
git add grafana docker-compose.yml
git commit -m "fix: provision grafana demo dashboard"
```

### Task 6: Run Clean End-To-End Acceptance

**Files:**
- Modify as failures require: files owned by Tasks 2-5 only
- Update: `docs/full-flow-test-report-2026-07-08.md`

- [ ] **Step 1: Establish clean container state**

Run:

```powershell
docker-compose down -v
docker-compose up -d
```

Expected: all services become healthy, with YMatrix health proving a query to `dw_demo`.

- [ ] **Step 2: Run the complete pipeline**

Run:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' ./init_all.sh
```

Expected: exit 0 and `=== All Done ===`.

- [ ] **Step 3: Verify database checkpoints**

Query exact MySQL counts; count ODS/DIM/DWD/DWS/ADS objects; query all seven ADS views; query `etl_log`; run `ymatrix/verify/01_compression.sql`.

Expected: all project acceptance counts pass, seven ADS views are non-empty, ETL logging is present, and MARS3 savings are at least 50%.

- [ ] **Step 4: Diagnose failures before changing code**

For any failure, capture the exact command, container logs, master log, and Segment log. Form one hypothesis and make one minimal change before rerunning the failing command.

### Task 7: Prove Idempotency And Grafana Rendering

**Files:**
- Update: `docs/full-flow-test-report-2026-07-08.md`

- [ ] **Step 1: Run initialization again without deleting volumes**

Run `./init_all.sh` a second time. Expected: exit 0 with identical MySQL counts and no duplicate-object errors.

- [ ] **Step 2: Verify Grafana API**

Query `/api/health`, `/api/datasources`, and `/api/search?query=YMatrix`. Expected: healthy database, one YMatrix data source, and one Demo dashboard.

- [ ] **Step 3: Verify the browser dashboard**

Open the provisioned dashboard, confirm six panels render, and check browser/Grafana logs for query errors.

- [ ] **Step 4: Update the test report**

Record fresh commands, exit codes, counts, compression ratio, screenshots/API evidence, and final PASS/FAIL/BLOCKED status for all nine checkpoints.

- [ ] **Step 5: Run final verification**

Run preflight, Python syntax compilation, Compose validation, both full-flow runs, database checks, and Grafana checks. Read complete output and count failures before claiming completion.

- [ ] **Step 6: Commit final evidence**

```powershell
git add docs/full-flow-test-report-2026-07-08.md
git commit -m "docs: record repaired full-flow verification"
```
