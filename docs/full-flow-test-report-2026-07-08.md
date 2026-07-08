# YMatrix DW Demo Full-Flow Test Report

## 1. Test Summary

- Test date: 2026-07-08 (Asia/Shanghai)
- Workspace: `D:\End-to-End-Data-Warehouse-Demo`
- Result: **FAIL - the Demo does not complete the documented one-command flow**
- Primary failing stage: `init_all.sh`, Step 4 (YMatrix schema initialization)
- Clean-run command: `docker-compose down -v`, `docker-compose up -d`, then Git Bash `./init_all.sh`

The three containers can start, but the clean full-flow run stops before ETL. MySQL loads data, while YMatrix database creation, authentication, SQL mounting, DDL compatibility, and restart behavior contain blocking defects. Grafana starts and provisions its data source, but provisions no dashboard.

## 2. Environment Evidence

| Item | Observed result |
|---|---|
| Docker Desktop | 4.46.0 |
| Docker Engine | 28.4.0, Linux/amd64 |
| Compose services | `mysql`, `ymatrix`, `grafana` |
| MySQL | 8.0.46, healthy |
| MatrixDB | 5.2.1 community, one Segment |
| Grafana | 13.1.0, HTTP health `database: ok` |
| Compose validation | PASS (`docker-compose config --quiet`) |
| Python syntax | PASS, 8/8 files compile |
| Dashboard JSON syntax | PASS, title `YMatrix DW Demo`, 6 panels |
| `.gitignore` | PASS, contains `/data/` |

## 3. Full-Flow Execution

### 3.1 Existing-volume run

`./init_all.sh` failed in Step 2 with:

```text
ERROR 1062 (23000) at line 1: Duplicate entry '1' for key 'users.PRIMARY'
```

Root cause: the MySQL named volume retained prior rows, while `init_all.sh` performs plain `INSERT` operations without truncation or idempotent loading.

### 3.2 Clean-volume run

After `docker-compose down -v` and `docker-compose up -d`, all seed files loaded into MySQL. The observed row counts were:

| Table | Expected | Actual | Result |
|---|---:|---:|---|
| users | 1,000 | 1,000 | PASS |
| products | 500 | 500 | PASS |
| orders | 50,000 | 50,000 | PASS |
| order_items | 200,000 | 144,977 | FAIL |
| payments | 50,000 | 47,522 | FAIL |

The run then stopped at `01_init.sql` with:

```text
FATAL: Peer authentication failed for user "mxadmin"
```

`init_all.sh` invokes `psql -U mxadmin` as container user `root`, which uses the Unix socket and conflicts with `pg_hba.conf` (`local ... mxadmin ident`). The TCP test reached the server but reported that `dw_demo` did not exist.

## 4. Root-Cause Findings

### F1 - YMatrix entrypoint does not create the configured database

Severity: Blocker

In `ymatrix/docker-entrypoint.sh`, the `if` statements on lines 11, 25, and 29 are appended to comment lines. Bash therefore treats them as comments. Database creation and password setup never execute.

Evidence:

```text
TCP_TEST
FATAL: database "dw_demo" does not exist
```

### F2 - Schema SQL directory is not mounted

Severity: Blocker

`init_all.sh` reads `/docker-entrypoint-initdb.d/<file>`, but the YMatrix service mounts only `./ymatrix/docker-entrypoint.sh`. Container inspection returned:

```text
ls: cannot access /docker-entrypoint-initdb.d: No such file or directory
```

### F3 - Wrong connection mode in `init_all.sh`

Severity: Blocker

The schema command omits `-h localhost` and runs as root, causing peer/ident authentication failure. The health check uses TCP and can report healthy while schema initialization still fails.

### F4 - Seed generator does not meet required cardinalities

Severity: High

The clean run generated 144,977 order items and 47,522 payments. The acceptance targets require exactly 200,000 and 50,000 respectively.

### F5 - `01_init.sql` is incompatible with the image

Severity: Blocker

After creating `dw_demo` manually in the test container, SQL execution reported:

```text
postgres_fdw.control: No such file or directory
function apm_enable_partition_maintenance() does not exist
value too long for type character varying(4)
```

`season VARCHAR(4)` cannot store `spring`, `summer`, `autumn`, or `winter`.

### F6 - Two MARS3 ODS tables have no order key

Severity: Blocker

`ods_users` and `ods_products` use MARS3 without `ORDER BY`. MatrixDB rejected the first table with:

```text
ERROR: mars3 storage must declare at least one order key
```

### F7 - DWS creation triggers repeatable VM Protect failure

Severity: Blocker

After temporary container-only DDL compensation, DIM and DWD tables could be created. The second DWS materialized view failed repeatedly:

```text
FATAL: Out of memory
DETAIL: VM Protect failed to allocate 65544 bytes, 0 MB available
```

This was not host memory exhaustion: the container had about 13.6 GiB available, no cgroup memory limit, and used about 379 MiB. `gp_vmem_protect_limit` was consistently 8192 MB on master and Segment. Attempts to restart after changing the test-container setting timed out and left the master in utility/recovery mode.

### F8 - Grafana dashboard is not provisioned

Severity: High

Grafana health and data-source provisioning worked:

```text
GET /api/health        -> database: ok
GET /api/datasources   -> YMatrix data source exists
```

Dashboard search returned no entries:

```text
GET /api/search?query=YMatrix -> []
GET /api/search?type=dash-db  -> []
```

Browser verification showed the normal Grafana home page with `Create your first dashboard`, not the six-panel Demo. The dashboards provisioning directory contains only the dashboard JSON and no provider YAML.

### F9 - Grafana plugin configuration emits errors

Severity: Medium

Grafana logs report that `grafana-postgresql-datasource` is a core plugin and cannot be installed separately. Other bundled plugin updates also failed with permission errors. PostgreSQL data-source functionality remained available, but the startup configuration is noisy and fragile.

## 5. Acceptance Checklist

| # | Checkpoint | Result | Evidence |
|---:|---|---|---|
| 1 | Three containers start | PASS | MySQL and YMatrix healthy; Grafana HTTP available |
| 2 | `init_all.sh` completes | FAIL | Stops at YMatrix schema authentication |
| 3 | MySQL expected row counts | FAIL | `order_items` and `payments` below targets |
| 4 | ODS 5 + DIM 5 + DWD 2 + DWS 3 + ADS 7 | BLOCKED | Core DDL fails; DWS also hits VM Protect |
| 5 | Seven ADS metrics return data | BLOCKED | ETL and ADS creation never complete |
| 6 | Grafana renders six panels | FAIL | Zero dashboards provisioned |
| 7 | MARS3 saves at least 50% | BLOCKED | ODS load and comparison cannot complete |
| 8 | `etl_log` records all steps | BLOCKED | ETL stage is never reached |
| 9 | `.gitignore` contains data/ and volumes | PASS | `/data/` is present; named volumes are not workspace paths |

Overall: **2 PASS, 3 FAIL, 4 BLOCKED**.

## 6. Diagnostic-Only Actions

To discover downstream failures, the test temporarily performed the following inside the disposable YMatrix container only:

- Created `dw_demo` manually.
- Copied `ymatrix/init/*.sql` to `/tmp/ymatrix-init`.
- Expanded `dim_date.season` and added MARS3 order keys to continue DDL testing.
- Tested `gp_vmem_protect_limit=0` and attempted cluster restart.

These actions did not modify repository source files and do not count as a successful product flow. The final YMatrix test container remained in distributed transaction recovery/utility mode after restart timeouts.

## 7. Recommended Repair Order

1. Repair line structure/encoding in `ymatrix/docker-entrypoint.sh`; verify database creation and password setup.
2. Restore the YMatrix `build:` configuration or document the required local image, and mount `./ymatrix/init:/docker-entrypoint-initdb.d:ro`.
3. Use TCP consistently (`-h localhost`) or run local `psql` as `mxadmin`.
4. Make MySQL loading idempotent and generate exact required row counts.
5. Remove unsupported extensions/functions or install the matching components; widen `season`.
6. Add `ORDER BY` to every MARS3 table.
7. Establish a supported MatrixDB container memory/restart configuration before retrying DWS.
8. Add a Grafana dashboard provider YAML and remove the redundant core-plugin installation request.
9. Re-run the complete clean-volume acceptance sequence and require all nine checkpoints to pass.
