#!/bin/bash

set -e

echo "开始部署AI语音机器人..."

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker未安装"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: docker-compose未安装"
    exit 1
fi

# 创建环境文件
if [ ! -f .env ]; then
    cat > .env << EOF
# ASR配置
ASR_WS_URL=ws://your-asr-service:10095

# LLM配置
LLM_API_URL=http://your-llm-service:8080/v1/chat/completions
LLM_MODEL=deepseek-chat

# TTS配置
TTS_API_URL=http://your-tts-service:8000/tts

# Redis配置
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# FreeSWITCH配置
FS_HOST=freeswitch
FS_PORT=8021
FS_PASSWORD=ClueCon
EOF
    echo "已创建.env文件，请配置服务地址"
fi

# 构建和启动服务
echo "启动服务..."
docker-compose up -d --build

echo "部署完成！"
echo "查看日志: docker-compose logs -f ai-robot"
