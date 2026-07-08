FROM centos:centos7.9.2009

# 1. 替换 yum 源为 vault（CentOS 7 EOL）
RUN sed -i 's/mirrorlist/#mirrorlist/g' /etc/yum.repos.d/CentOS-*.repo && \
    sed -i 's|#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|g' /etc/yum.repos.d/CentOS-*.repo && \
    yum clean all && yum makecache

# 2. 安装基础依赖和 SSH
RUN yum install -y epel-release && \
    yum install -y openssh-server openssh-clients supervisor net-tools && \
    ssh-keygen -A && \
    yum clean all

# 3. 复制 RPM 包并安装
COPY matrixdb5-5.2.1+community-1.el7.x86_64.rpm /tmp/
RUN yum localinstall -y /tmp/matrixdb5-5.2.1+community-1.el7.x86_64.rpm --nogpgcheck && \
    rm -f /tmp/matrixdb5-*.rpm

# 4. 配置 SSH 免密登录（root 和 mxadmin）
RUN ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa && \
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && \
    chmod 600 /root/.ssh/authorized_keys && \
    /usr/sbin/sshd

# 5. 创建 mxadmin 用户并配置 SSH
RUN groupadd mxadmin && \
    useradd -g mxadmin mxadmin && \
    echo "mxadmin:mxadmin" | chpasswd && \
    mkdir -p /home/mxadmin/.ssh && \
    ssh-keygen -t rsa -N "" -f /home/mxadmin/.ssh/id_rsa && \
    cat /home/mxadmin/.ssh/id_rsa.pub >> /home/mxadmin/.ssh/authorized_keys && \
    chmod 600 /home/mxadmin/.ssh/authorized_keys && \
    chown -R mxadmin:mxadmin /home/mxadmin/.ssh

# 6. 创建数据目录并授权
RUN mkdir -p /data/master /data/primary && \
    chown -R mxadmin:mxadmin /data

# 7. 准备 gpinitsystem 配置文件
RUN cat > /home/mxadmin/gpinitsystem_config <<EOF && \
    ARRAY_NAME="YMatrix DB Cluster" && \
    SEG_PREFIX=gpseg && \
    PORT_BASE=6000 && \
    declare -a DATA_DIRECTORY=(/data/primary) && \
    MASTER_HOSTNAME=localhost && \
    MASTER_DIRECTORY=/data/master && \
    MASTER_PORT=5432 && \
    TRUSTED_SHELL=ssh && \
    CHECK_POINT_SEGMENTS=8 && \
    ENCODING=UNICODE && \
    MACHINE_LIST_FILE=/home/mxadmin/hostfile && \
    EOF && \
    echo "localhost" > /home/mxadmin/hostfile && \
    chown mxadmin:mxadmin /home/mxadmin/gpinitsystem_config /home/mxadmin/hostfile

# 8. 初始化数据库（在构建时执行，但需要运行 sshd，所以改为启动脚本）
# 我们将在入口脚本中完成初始化，因为构建时无法启动 sshd 服务
COPY init_db.sh /init_db.sh
RUN chmod +x /init_db.sh

# 9. 暴露端口
EXPOSE 5432 8240 4617

# 10. 启动脚本（完成初始化并启动数据库）
CMD ["/init_db.sh"]