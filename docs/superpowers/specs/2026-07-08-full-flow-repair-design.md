# Full-Flow Repair Design

## Goal

Repair the current local-image YMatrix Demo so that both a clean initialization and a repeated initialization complete successfully while preserving the MySQL -> ODS -> DIM -> DWD -> DWS -> ADS -> Grafana flow.

## Scope

This change uses the existing local image `ymatrix5.2-clean:latest`. Building a portable YMatrix image on a new machine is explicitly out of scope. The repair covers findings F1-F9 in `docs/full-flow-test-report-2026-07-08.md` except for replacing the local-image distribution strategy.

## Architecture

The three-service Compose topology remains unchanged. The repair makes each boundary deterministic:

1. The YMatrix entrypoint starts the baked-in cluster, waits for dispatch mode, creates `dw_demo` idempotently, and sets the configured password.
2. `init_all.sh` waits for service readiness, resets only Demo-owned data and warehouse objects, generates exact seed cardinalities, loads MySQL, applies YMatrix DDL over TCP, runs ETL, and invokes verification.
3. Warehouse DDL retains MARS3, HEAP, RANGE partitioning, materialized views, and `time_bucket`, but uses monthly partitions to fit the single-Segment Demo resource envelope.
4. Grafana receives a valid dashboard provider plus the existing data source and six-panel dashboard.

## Isolation And Git Strategy

Implementation runs in `.worktrees/fix-full-flow` on branch `codex/fix-full-flow`. Because the main worktree contains user changes, only the approved repair inputs are transferred into the worktree. Unrelated changes are not reset, reverted, or reformatted.

## Component Design

### Docker Compose

- Keep service names `mysql`, `ymatrix`, and `grafana`.
- Keep `ymatrix5.2-clean:latest` with `pull_policy: never`.
- Mount `./ymatrix/init` read-only at `/docker-entrypoint-initdb.d`.
- Mount Grafana provisioning directories without changing ports.
- Remove `GF_INSTALL_PLUGINS=grafana-postgresql-datasource` because PostgreSQL is a core data source.
- Strengthen the YMatrix health check so it verifies `dw_demo` in normal dispatch mode rather than accepting a recovery/utility listener.

### YMatrix Entrypoint

- Replace corrupted comment/statement lines with ASCII-safe shell text.
- Start SSH, load `greenplum_path.sh`, and set `MASTER_DATA_DIRECTORY`.
- Start the baked-in cluster only when it is not already in dispatch mode.
- Poll a real SQL query until distributed recovery completes.
- Create `dw_demo` only when absent and set the `mxadmin` password.
- Fail visibly on startup errors; do not hide database creation failures behind `|| true`.
- Keep the foreground process alive without repeatedly restarting MatrixDB.

### Idempotent Orchestration

- Wait for all three services using health/API checks rather than matching `docker-compose ps` text.
- Reset MySQL tables in foreign-key-safe order before seed loading.
- Drop Demo-owned ADS views, DWS materialized views, DWD/DIM/ODS tables, and `etl_log` before replaying numbered SQL files.
- Use `psql -h localhost -v ON_ERROR_STOP=1` for every warehouse SQL file.
- Preserve the numbered files and current layer ordering.
- Run ETL and verification only after all DDL succeeds.

### Deterministic Seed Data

- Keep the seeded random generator for repeatable values.
- Generate exactly 50,000 orders.
- Allocate exactly 200,000 order items across those orders while preserving realistic per-order variation.
- Generate exactly one payment per order, for 50,000 payments.
- Preserve the promotion-period skew and existing table schemas.

### Warehouse SQL Compatibility

- Keep `matrixts`, which exists in the local image.
- Remove unsupported `postgres_fdw` and `apm_enable_partition_maintenance()` calls from mandatory initialization. The optional MySQL FDW showcase remains isolated in `06_fdw.sql` and must not block the core path.
- Change `dim_date.season` to `VARCHAR(10)`.
- Add stable `ORDER BY` keys to every MARS3 table.
- Change ODS and DWD date partitions from daily to monthly while retaining RANGE partitioning.
- Keep DWS materialized views and daily `time_bucket` aggregation.
- Make schema creation fail fast so the first incompatible statement is reported directly.

### Resource Strategy

The default repair reduces partition fan-out instead of disabling `gp_vmem_protect_limit`. This keeps MatrixDB memory protection enabled and addresses the observed failure where multiple daily-partitioned fact tables exhausted VM Protect accounting during materialized-view creation. If the same failure remains after monthly partitioning, the implementation stops and gathers fresh master/Segment evidence before considering a memory setting change.

### Grafana Provisioning

- Add a dashboard provider YAML under `grafana/dashboards` that points to the mounted dashboard directory.
- Keep the PostgreSQL data source named `YMatrix`.
- Supply the configured database password through Grafana provisioning.
- Verify through the Grafana API that exactly one Demo dashboard is present and that it contains six panels.

## Error Handling

- Shell scripts use `set -euo pipefail` and explicit readiness timeouts.
- Database commands use fail-fast options and print the failing stage.
- Python subprocess calls check return codes and surface stderr.
- Repeated initialization cleans only known Demo objects and tables.
- Optional FDW setup reports a skip instead of aborting the warehouse pipeline when the extension is unavailable.

## Test Strategy

The project excludes unit tests, so bug-first coverage uses focused integration and static checks:

1. A preflight verification script initially fails on the known defects: missing mount/provider, corrupt entrypoint control flow, unsupported mandatory SQL, missing MARS3 order keys, and wrong seed targets.
2. Each repair is applied minimally until its corresponding check passes.
3. A clean-volume acceptance run executes `docker-compose down -v`, `docker-compose up -d`, and `./init_all.sh`.
4. A second `./init_all.sh` runs without deleting volumes to prove idempotency.
5. Final SQL checks verify MySQL counts, layer object counts, seven non-empty ADS metrics, compression savings, and ETL log entries.
6. Grafana API and browser checks verify the provisioned six-panel dashboard renders without query errors.

## Acceptance Criteria

- Three containers start and remain healthy.
- Clean and repeated `init_all.sh` runs exit 0.
- MySQL counts are exactly 1,000 users, 500 products, 50,000 orders, 200,000 order items, and 50,000 payments.
- YMatrix contains ODS 5, DIM 5, DWD 2, DWS 3, and ADS 7 required objects.
- All seven ADS views return non-empty, reasonable results.
- Grafana provisions and renders the six-panel Demo dashboard.
- MARS3 saves at least 50% versus the HEAP comparison table.
- `etl_log` records the full pipeline timing.
- `.gitignore` continues to exclude `data/` and local Docker artifacts.

## Non-Goals

- Publishing or rebuilding `ymatrix5.2-clean:latest`.
- Introducing Spark, Flink, Kafka, CI/CD, or a new test framework.
- Refactoring historical SQLite/Flask directories.
- Changing service names, ports, MySQL root password, or database credential encoding.
