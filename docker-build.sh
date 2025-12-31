#!/bin/bash
# Docker构建和发布脚本

set -e

# 配置
IMAGE_NAME="ai-robot"
VERSION=${1:-latest}
REGISTRY=${REGISTRY:-""}  # 设置你的镜像仓库地址，例如：docker.io/username

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FreeSWITCH AI Robot - Docker Build${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker未安装${NC}"
    exit 1
fi

# 构建镜像
echo -e "\n${YELLOW}[1/4] 构建Docker镜像...${NC}"
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${VERSION}"
else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${VERSION}"
fi

docker build -t ${FULL_IMAGE_NAME} .
docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:latest

echo -e "${GREEN}✓ 镜像构建完成: ${FULL_IMAGE_NAME}${NC}"

# 显示镜像信息
echo -e "\n${YELLOW}[2/4] 镜像信息:${NC}"
docker images | grep ${IMAGE_NAME}

# 询问是否推送到仓库
if [ -n "$REGISTRY" ]; then
    echo -e "\n${YELLOW}[3/4] 是否推送镜像到仓库？ (y/n)${NC}"
    read -r PUSH_CONFIRM
    if [ "$PUSH_CONFIRM" = "y" ] || [ "$PUSH_CONFIRM" = "Y" ]; then
        echo -e "${YELLOW}推送镜像中...${NC}"
        docker push ${FULL_IMAGE_NAME}
        docker push ${IMAGE_NAME}:latest
        echo -e "${GREEN}✓ 镜像推送完成${NC}"
    fi
else
    echo -e "\n${YELLOW}[3/4] 跳过推送（未配置镜像仓库）${NC}"
fi

# 询问是否启动服务
echo -e "\n${YELLOW}[4/4] 是否启动服务？ (y/n)${NC}"
read -r START_CONFIRM
if [ "$START_CONFIRM" = "y" ] || [ "$START_CONFIRM" = "Y" ]; then
    echo -e "${YELLOW}启动服务中...${NC}"
    docker-compose down
    docker-compose up -d
    echo -e "${GREEN}✓ 服务已启动${NC}"
    echo -e "\n${GREEN}访问地址:${NC}"
    echo -e "  WebUI: http://localhost:8081"
    echo -e "  API: http://localhost:8080"
    echo -e "\n${GREEN}默认登录信息:${NC}"
    echo -e "  用户名: admin"
    echo -e "  密码: admin123"
fi

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}构建完成！${NC}"
echo -e "${GREEN}========================================${NC}"
