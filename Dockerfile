FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

COPY . .

# 创建日志目录
RUN mkdir -p /var/log/ai-robot

CMD ["python", "main.py"]
