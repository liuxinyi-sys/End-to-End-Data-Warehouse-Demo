#!/bin/bash
set -euo pipefail

source /opt/ymatrix/matrixdb5/greenplum_path.sh
export MASTER_DATA_DIRECTORY=/data/master/gpseg-1

DB_NAME="${MATRIXDB_DB:-dw_demo}"
DB_USER="${MATRIXDB_USER:-mxadmin}"
DB_PASSWORD="${MATRIXDB_PASSWORD:-mxadmin123}"

run_as_mxadmin() {
    su - mxadmin -c "source /opt/ymatrix/matrixdb5/greenplum_path.sh && export MASTER_DATA_DIRECTORY=/data/master/gpseg-1 && $1"
}

if [ ! -f "$MASTER_DATA_DIRECTORY/postgresql.conf" ]; then
    echo "ERROR: MatrixDB data directory is not initialized: $MASTER_DATA_DIRECTORY" >&2
    exit 1
fi

/usr/sbin/sshd || true

if ! run_as_mxadmin "psql -h localhost -p 5432 -d postgres -tAc 'SELECT 1'" >/dev/null 2>&1; then
    echo "Starting MatrixDB cluster..."
    run_as_mxadmin "gpstart -a"
fi

ready=0
for _ in $(seq 1 120); do
    if run_as_mxadmin "psql -h localhost -p 5432 -d postgres -tAc 'SELECT 1'" 2>/dev/null | grep -qx 1; then
        ready=1
        break
    fi
    sleep 1
done

if [ "$ready" -ne 1 ]; then
    echo "ERROR: MatrixDB did not enter dispatch mode within 120 seconds" >&2
    exit 1
fi

if ! run_as_mxadmin "psql -h localhost -p 5432 -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'\"" | grep -qx 1; then
    run_as_mxadmin "createdb -h localhost -p 5432 '$DB_NAME'"
fi

run_as_mxadmin "psql -h localhost -p 5432 -d postgres -v ON_ERROR_STOP=1 -c \"ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD'\""

echo "MatrixDB is ready: database=$DB_NAME user=$DB_USER"
tail -f /dev/null
