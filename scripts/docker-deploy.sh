#!/bin/bash

set -e

echo "开始部署FreeSWITCH AI机器人..."

# 检查Docker是否安装
#if ! command -v docker &> /dev/null; then
#    echo "错误: Docker未安装"
#    exit 1
#fi

# 检查docker-compose是否安装
#if ! command -v docker-compose &> /dev/null; then
#    echo "错误: docker-compose未安装"
#    exit 1
#fi

# 创建环境文件（如果不存在）
if [ ! -f .env ]; then
    cp config/.env.example .env
    echo "已从config/.env.example复制.env文件，请根据需要修改配置"
fi

# 创建必要的目录
mkdir -p logs data contacts scenarios

# 停止可能存在的旧容器
echo "停止旧容器..."
docker-compose down

# 构建和启动服务
echo "构建并启动服务..."
docker-compose up -d --build

# 等待MySQL启动
echo "等待MySQL启动..."
sleep 30

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

# 显示日志
echo "服务启动完成！"
echo "WebUI地址: http://localhost:8081"
echo "API地址: http://localhost:8080"
echo "MySQL地址: localhost:3306"
echo "Redis地址: localhost:6379"
echo ""
echo "查看所有服务日志: docker-compose logs -f"
echo "查看AI机器人日志: docker-compose logs -f ai-robot"
echo "停止服务: docker-compose down"
