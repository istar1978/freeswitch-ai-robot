FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    mariadb-client-compat \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY . .

# 创建必要的目录
RUN mkdir -p /var/log/ai-robot /app/data /app/logs /app/scenarios /app/contacts

# 设置目录权限
RUN chmod 755 /app/data /app/logs /var/log/ai-robot

# 设置启动脚本权限
RUN chmod +x scripts/docker-entrypoint.sh

# 暴露端口
EXPOSE 8080 8081

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8081/ || exit 1

# 使用entrypoint脚本
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
