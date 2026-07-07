#!/bin/bash
set -e

# 启动 SSH（Greenplum 需要）
/usr/sbin/sshd || true

# 加载环境
source /opt/ymatrix/matrixdb5/greenplum_path.sh
export MASTER_DATA_DIRECTORY=/data/master/gpseg-1

# 检查数据库是否已初始化（镜像内已有数据）
if [ -f "$MASTER_DATA_DIRECTORY/postgresql.conf" ]; then
    echo "✅ 检测到已有数据库，直接启动..."
else
    echo "❌ 未找到数据库，请确保使用正确的镜像！"
    exit 1
fi

# 启动数据库（如果未运行）
su - mxadmin -c "
    source /opt/ymatrix/matrixdb5/greenplum_path.sh
    export MASTER_DATA_DIRECTORY=/data/master/gpseg-1
    gpstate -s | grep -q 'Master is running' || gpstart -a
"

# 创建环境变量指定的数据库（如果不存在）
if [ -n "$MATRIXDB_DB" ]; then
    su - mxadmin -c "psql -p 5432 -d postgres -c \"CREATE DATABASE $MATRIXDB_DB;\" 2>/dev/null || true"
fi

# 设置用户密码（如果提供了）
if [ -n "$MATRIXDB_USER" ] && [ -n "$MATRIXDB_PASSWORD" ]; then
    su - mxadmin -c "psql -p 5432 -d postgres -c \"ALTER USER $MATRIXDB_USER WITH PASSWORD '$MATRIXDB_PASSWORD';\" 2>/dev/null || true"
fi

echo "✅ MatrixDB 已就绪！"

# 保持容器运行
tail -f /dev/null