FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY . .

# 创建日志目录
RUN mkdir -p /var/log/ai-robot

# 暴露API端口和WebUI端口
EXPOSE 8080 8081

CMD ["python", "main.py"]
