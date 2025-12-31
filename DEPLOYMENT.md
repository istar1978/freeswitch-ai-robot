# FreeSWITCH AI Robot 部署指南

## 部署方式

本项目支持三种部署方式：
1. **Docker Compose** - 推荐用于开发和测试环境
2. **Kubernetes** - 推荐用于生产环境
3. **直接部署** - 用于本地开发

---

## 1. Docker Compose 部署

### 前提条件
- Docker 20.10+
- Docker Compose 2.0+

### 快速开始

```bash
# 1. 克隆项目
git clone <repository-url>
cd freeswitch-ai-robot

# 2. 创建环境变量文件
cp .env.production .env
# 编辑 .env 文件，修改必要的配置

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f ai-robot

# 5. 访问WebUI
# http://localhost:8081
# 默认用户名: admin
# 默认密码: admin123
```

**重要提示**：
- 首次启动时，FunASR和CosyVoice服务会自动下载模型文件
- FunASR模型约 **3-5GB**，下载需要 **10-30分钟**（取决于网络速度）
- CosyVoice模型约 **8-12GB**，下载需要 **20-60分钟**（取决于网络速度）
- 模型下载完成后会持久化存储，下次启动不需要重新下载
- 建议首次部署时预留足够的时间和磁盘空间（至少20GB）

查看模型下载进度：
```bash
# 查看FunASR日志
docker-compose logs -f funasr

# 查看CosyVoice日志
docker-compose logs -f cosyvoice
```

### 服务说明

- **ai-robot**: AI机器人主服务
  - API端口: 8080
  - WebUI端口: 8081
  
- **mysql**: MySQL 8.0 数据库
  - 端口: 3306
  - 数据持久化: mysql_data volume
  
- **redis**: Redis 7 缓存
  - 端口: 6379
  - 数据持久化: redis_data volume

- **funasr**: FunASR语音识别服务
  - 端口: 10095 (WebSocket)
  - 官方镜像: registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.10
  - 模型持久化: funasr_models volume
  - 首次启动会自动下载模型，需要较长时间

- **cosyvoice**: CosyVoice语音合成服务
  - 端口: 50000 (HTTP API)
  - 官方镜像: registry.cn-hangzhou.aliyuncs.com/modelscope-repo/cosyvoice:v1.0
  - 模型持久化: cosyvoice_models volume
  - 首次启动会自动下载模型，需要较长时间

### 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f [service_name]

# 进入容器
docker-compose exec ai-robot bash
docker-compose exec mysql mysql -uroot -p

# 重建镜像
docker-compose build --no-cache

# 清理所有数据（谨慎使用）
docker-compose down -v
```

### 数据备份

```bash
# 备份MySQL数据
docker-compose exec mysql mysqldump -uroot -p aibot > backup.sql

# 恢复MySQL数据
docker-compose exec -T mysql mysql -uroot -p aibot < backup.sql

# 备份Redis数据
docker-compose exec redis redis-cli SAVE
docker cp ai-robot-redis:/data/dump.rdb ./redis-backup.rdb

# 备份FunASR模型（首次下载后备份）
docker cp ai-robot-funasr:/workspace/models ./funasr-models-backup

# 备份CosyVoice模型（首次下载后备份）
docker cp ai-robot-cosyvoice:/workspace/models ./cosyvoice-models-backup
```

---

## 2. Kubernetes 部署

### 前提条件
- Kubernetes 1.20+
- kubectl 配置完成
- StorageClass 已配置（默认使用 standard）
- Ingress Controller（可选，用于外部访问）

### 部署步骤

```bash
# 1. 创建命名空间
kubectl apply -f - <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ai-robot
EOF

# 2. 创建MySQL初始化SQL ConfigMap
kubectl create configmap mysql-init-sql \
  --from-file=init.sql=./storage/init_database.sql \
  -n ai-robot

# 3. 部署所有资源
kubectl apply -f k8s-deployment.yml

# 4. 查看部署状态
kubectl get pods -n ai-robot -w

# 5. 查看服务
kubectl get svc -n ai-robot

# 6. 查看日志
kubectl logs -f deployment/ai-robot -n ai-robot
```

### 访问应用

#### 通过LoadBalancer（如果支持）
```bash
# 获取LoadBalancer IP
kubectl get svc ai-robot-service -n ai-robot

# 访问
# WebUI: http://<EXTERNAL-IP>:8081
# API: http://<EXTERNAL-IP>:8080
```

#### 通过Ingress
```bash
# 1. 修改 k8s-deployment.yml 中的域名
# 2. 配置DNS解析到Ingress Controller
# 3. 访问 http://ai-robot.example.com
```

#### 通过Port Forward（开发测试）
```bash
kubectl port-forward svc/ai-robot-service 8081:8081 -n ai-robot
# 访问 http://localhost:8081
```

### K8s常用命令

```bash
# 查看所有资源
kubectl get all -n ai-robot

# 查看Pod详情
kubectl describe pod <pod-name> -n ai-robot

# 查看日志
kubectl logs -f deployment/ai-robot -n ai-robot

# 进入容器
kubectl exec -it deployment/ai-robot -n ai-robot -- bash

# 扩缩容
kubectl scale deployment ai-robot --replicas=3 -n ai-robot

# 滚动更新
kubectl set image deployment/ai-robot ai-robot=ai-robot:v2 -n ai-robot
kubectl rollout status deployment/ai-robot -n ai-robot

# 回滚
kubectl rollout undo deployment/ai-robot -n ai-robot

# 删除所有资源
kubectl delete namespace ai-robot
```

### 生产环境建议

1. **资源限制**：根据实际负载调整resources配置
2. **副本数**：建议最少2个副本保证高可用
3. **存储类**：使用高性能SSD存储类
4. **监控告警**：集成Prometheus监控
5. **日志收集**：使用ELK或Loki收集日志
6. **备份策略**：定期备份MySQL和Redis数据

---

## 3. 直接部署

### 前提条件
- Python 3.11+
- MySQL 8.0+
- Redis 7+
- FreeSWITCH（可选）

### 安装步骤

```bash
# 1. 安装Python依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.production .env
# 编辑.env文件

# 3. 初始化数据库
mysql -u root -p < storage/init_database.sql

# 4. 启动服务
python main.py
```

---

## 配置说明

### 必需配置

1. **数据库配置**
```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=aibot
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=aibot
```

2. **认证配置**
```bash
AUTH_ADMIN_USERNAME=admin
AUTH_ADMIN_PASSWORD=your_password
AUTH_JWT_SECRET=your_secret_key  # 生产环境必须修改
```

### 可选配置

1. **FreeSWITCH配置**
```bash
FREESWITCH_ENABLED=true
FREESWITCH_HOST=freeswitch_server
FREESWITCH_PORT=8021
FREESWITCH_PASSWORD=ClueCon
```

2. **ASR/LLM/TTS配置**
```bash
# FunASR语音识别（已默认启用）
ASR_ENABLED=true
ASR_PROVIDER=funasr
ASR_WS_URL=ws://funasr:10095  # Docker Compose环境
# ASR_WS_URL=ws://funasr-service:10095  # K8s环境

# CosyVoice语音合成（已默认启用）
TTS_ENABLED=true
TTS_PROVIDER=cosyvoice
TTS_API_URL=http://cosyvoice:50000/tts  # Docker Compose环境
# TTS_API_URL=http://cosyvoice-service:50000/tts  # K8s环境

# LLM大模型（需要单独配置）
LLM_ENABLED=false
LLM_API_URL=http://your-llm-server:8000/v1/chat/completions
```

---

## 健康检查

### Docker Compose
```bash
# 查看健康状态
docker-compose ps

# 手动健康检查
curl http://localhost:8081/
```

### Kubernetes
```bash
# 查看Pod健康状态
kubectl get pods -n ai-robot

# 查看详细健康检查信息
kubectl describe pod <pod-name> -n ai-robot
```

---

## 故障排查

### 常见问题

1. **容器启动失败**
```bash
# 查看日志
docker-compose logs ai-robot
# 或
kubectl logs -f deployment/ai-robot -n ai-robot
```

2. **数据库连接失败**
- 检查数据库是否已启动
- 检查用户名密码是否正确
- 检查网络连接

3. **WebUI无法访问**
- 检查端口是否暴露
- 检查防火墙设置
- 检查服务是否正常运行

4. **内存不足**
- 增加容器内存限制
- 优化应用配置
- 使用分布式部署

### 日志位置

- **Docker**: `./logs/` 目录
- **Kubernetes**: 通过kubectl logs查看
- **直接部署**: `/var/log/ai-robot/app.log`

---

## 性能优化

### Docker Compose

1. **使用生产级镜像**
```dockerfile
FROM python:3.11-slim
# 使用slim镜像减小体积
```

2. **优化资源限制**
```yaml
services:
  ai-robot:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Kubernetes

1. **配置HPA自动扩缩容**（已包含在配置中）
2. **使用节点亲和性**优化调度
3. **配置资源请求和限制**
4. **使用高性能存储类**

---

## 安全建议

1. **修改默认密码**
   - 管理员密码
   - 数据库密码
   - JWT密钥

2. **网络隔离**
   - 使用独立网络
   - 限制端口暴露
   - 配置防火墙规则

3. **使用HTTPS**
   - 配置SSL证书
   - 强制HTTPS访问

4. **定期更新**
   - 更新依赖包
   - 更新基础镜像
   - 应用安全补丁

---

## 监控和维护

### 推荐监控指标

- CPU使用率
- 内存使用率
- 网络流量
- API响应时间
- 数据库连接数
- Redis内存使用

### 定期维护

- 数据库优化和备份
- 日志清理和归档
- 资源使用分析
- 性能调优

---

## 支持和帮助

- 查看日志文件
- 检查系统资源
- 联系技术支持
- 提交Issue
