#!/bin/bash
# 快速启动脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FreeSWITCH AI Robot - 快速启动${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查必要的工具
echo -e "\n${YELLOW}检查环境...${NC}"
for cmd in docker docker-compose; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}错误: $cmd 未安装${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓ 环境检查通过${NC}"

# 创建必要的目录
echo -e "\n${YELLOW}创建必要的目录...${NC}"
mkdir -p logs data scenarios contacts
echo -e "${GREEN}✓ 目录创建完成${NC}"

# 检查.env文件
if [ ! -f .env ]; then
    echo -e "\n${YELLOW}创建配置文件...${NC}"
    if [ -f .env.production ]; then
        cp .env.production .env
        echo -e "${GREEN}✓ 已从.env.production创建.env${NC}"
    else
        echo -e "${YELLOW}警告: 未找到.env.production，将使用默认配置${NC}"
    fi
fi

# 启动服务
echo -e "\n${YELLOW}启动服务...${NC}"
echo -e "${YELLOW}注意：首次启动时，FunASR和CosyVoice会自动下载模型（约15-20GB），可能需要30-60分钟${NC}"
echo -e "${YELLOW}请耐心等待模型下载完成...${NC}"
docker-compose up -d

# 等待服务启动
echo -e "\n${YELLOW}等待服务启动...${NC}"
sleep 5

# 检查服务状态
echo -e "\n${YELLOW}检查服务状态...${NC}"
docker-compose ps

# 显示日志
echo -e "\n${YELLOW}查看启动日志...${NC}"
docker-compose logs --tail=20 ai-robot

echo -e "\n${YELLOW}检查AI服务状态（FunASR和CosyVoice可能需要较长时间下载模型）...${NC}"
echo -e "${YELLOW}查看FunASR日志: docker-compose logs -f funasr${NC}"
echo -e "${YELLOW}查看CosyVoice日志: docker-compose logs -f cosyvoice${NC}"

# 显示访问信息
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}服务启动成功！${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${GREEN}访问地址:${NC}"
echo -e "  WebUI: http://localhost:8081"
echo -e "  API: http://localhost:8080"
echo -e "\n${GREEN}默认登录信息:${NC}"
echo -e "  用户名: admin"
echo -e "  密码: admin123"
echo -e "\n${YELLOW}常用命令:${NC}"
echo -e "  查看日志: docker-compose logs -f"
echo -e "  停止服务: docker-compose down"
echo -e "  重启服务: docker-compose restart"
echo -e "\n${GREEN}========================================${NC}"
