#!/bin/bash
set -e

# 启动 sshd
/usr/sbin/sshd

# 切换到 mxadmin 执行初始化
su - mxadmin -c "
source /opt/ymatrix/matrixdb5/greenplum_path.sh
# 如果尚未初始化，执行 gpinitsystem
if [ ! -f /data/master/gpseg-1/postgresql.conf ]; then
    gpinitsystem -c /home/mxadmin/gpinitsystem_config -h /home/mxadmin/hostfile <<< y
    # 修复 pg_hba.conf
    echo 'host all all 127.0.0.1/32 trust' >> /data/master/gpseg-1/pg_hba.conf
    echo 'host all all ::1/128 trust' >> /data/master/gpseg-1/pg_hba.conf
    gpstart -a
else
    gpstart -a
fi
"

# 保持容器运行
tail -f /dev/null