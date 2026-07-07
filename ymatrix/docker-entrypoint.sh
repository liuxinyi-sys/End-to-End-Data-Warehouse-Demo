#!/bin/bash
set -e

if [ -d /opt/matrixdb ]; then MATRIXDB_HOME=/opt/matrixdb
elif [ -d /usr/local/matrixdb ]; then MATRIXDB_HOME=/usr/local/matrixdb
elif [ -d /usr/lib/matrixdb ]; then MATRIXDB_HOME=/usr/lib/matrixdb
else MATRIXDB_HOME=$(ls -d /opt/*matrix* /usr/local/*matrix* /usr/lib/*matrix* 2>/dev/null | head -1); fi

if [ -z "$MATRIXDB_HOME" ]; then echo "MatrixDB not found"; exit 1; fi
export PATH=$MATRIXDB_HOME/bin:$PATH
export PGDATA=${PGDATA:-$MATRIXDB_HOME/data}
export PGPORT=${PGPORT:-5432}

if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Initializing MatrixDB..."
    mkdir -p "$PGDATA"
    initdb -D "$PGDATA" --encoding=UTF8 2>/dev/null || true
fi

pg_ctl -D "$PGDATA" -l /var/log/matrixdb.log start 2>/dev/null || pg_ctl -D "$PGDATA" start

if [ -n "$MATRIXDB_USER" ] && [ -n "$MATRIXDB_DB" ]; then
    sleep 2
    psql -h localhost -p $PGPORT -U postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='$MATRIXDB_USER'" | grep -q 1 ||         psql -h localhost -p $PGPORT -U postgres -c "CREATE USER $MATRIXDB_USER SUPERUSER;"
    psql -h localhost -p $PGPORT -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='$MATRIXDB_DB'" | grep -q 1 ||         psql -h localhost -p $PGPORT -U postgres -c "CREATE DATABASE $MATRIXDB_DB OWNER $MATRIXDB_USER;"
fi

echo "MatrixDB ready on port $PGPORT."
tail -f /dev/null
