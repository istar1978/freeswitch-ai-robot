FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    mariadb-client-compat \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY . .

# 创建日志目录和数据目录
RUN mkdir -p /var/log/ai-robot /app/data /app/logs

# 设置数据目录权限
RUN chmod 755 /app/data /app/logs

# 设置启动脚本权限
RUN chmod +x scripts/docker-entrypoint.sh

# 暴露API端口和WebUI端口
EXPOSE 8080 8081

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8081/health', timeout=5)" || exit 1

# 使用自定义entrypoint
ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
