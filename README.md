# FreeSWITCH AI Robot

一个基于FreeSWITCH的AI语音机器人项目，支持实时语音识别、语言模型对话和文本到语音合成。

## 项目描述

FreeSWITCH AI Robot 是一个集成语音交互能力的AI机器人应用。它通过FreeSWITCH处理电话呼叫，使用ASR（自动语音识别）将语音转换为文本，LLM（大语言模型）进行智能对话处理，最后通过TTS（文本到语音）将回复转换为语音输出。

## 功能特性

- **实时语音识别**：集成FunASR，支持实时语音转文本
- **智能对话**：支持多种LLM模型，如DeepSeek等
- **语音合成**：集成TTS服务，提供自然语音输出
- **状态管理**：基于状态机的对话流程控制
- **健康监控**：内置健康检查和监控功能
- **Redis存储**：使用Redis进行会话数据存储
- **Docker部署**：支持容器化部署和编排

## 系统架构

项目采用模块化设计，主要组件包括：

- **clients/**: 外部服务客户端（ASR、LLM、TTS）
- **config/**: 配置管理
- **core/**: 核心业务逻辑（对话管理、状态机、健康检查）
- **freeswitch/**: FreeSWITCH集成（ESL处理、音频流）
- **storage/**: 数据存储（Redis客户端）
- **utils/**: 工具类（日志、助手函数）

## 安装

### 环境要求

- Python 3.10+
- Docker & Docker Compose
- FreeSWITCH服务器
- Redis数据库

### 依赖安装

```bash
pip install -r requirements.txt
```

### Docker构建

```bash
docker-compose build
```

## 配置

项目使用环境变量进行配置，主要配置项包括：

### ASR配置
- `ASR_WS_URL`: ASR服务WebSocket地址 (默认: ws://localhost:10095)

### LLM配置
- `LLM_API_URL`: LLM API地址 (默认: http://localhost:8080/v1/chat/completions)
- `LLM_MODEL`: 使用的模型名称 (默认: deepseek-chat)

### TTS配置
- `TTS_API_URL`: TTS服务地址 (默认: http://localhost:8000/tts)

### Redis配置
- `REDIS_HOST`: Redis主机 (默认: localhost)
- `REDIS_PORT`: Redis端口 (默认: 6379)

### FreeSWITCH配置
- `FS_HOST`: FreeSWITCH主机 (默认: localhost)
- `FS_PASSWORD`: FreeSWITCH密码 (默认: ClueCon)

## 运行

### 本地运行

1. 启动依赖服务（Redis、ASR、LLM、TTS、FreeSWITCH）
2. 设置环境变量
3. 运行主程序：

```bash
python main.py
```

### Docker运行

```bash
docker-compose up -d
```

## 部署

项目支持完整的Docker容器化部署：

1. 构建镜像：
```bash
docker-compose build
```

2. 启动服务：
```bash
docker-compose up -d
```

3. 查看日志：
```bash
docker-compose logs -f ai-robot
```

## 脚本

- `scripts/deploy.sh`: 部署脚本
- `scripts/health_check.py`: 健康检查脚本

## 开发

### 项目结构

```
freeswitch-ai-robot/
├── main.py                 # 应用入口
├── requirements.txt        # Python依赖
├── Dockerfile             # Docker镜像构建
├── docker-compose.yml     # Docker编排
├── clients/               # 外部服务客户端
├── config/                # 配置管理
├── core/                  # 核心业务逻辑
├── freeswitch/            # FreeSWITCH集成
├── storage/               # 数据存储
├── utils/                 # 工具类
└── scripts/               # 部署脚本
```

### 状态机

对话流程通过状态机管理：

- IDLE: 空闲状态
- ASR_LISTENING: 语音识别中
- LLM_PROCESSING: 语言模型处理中
- TTS_PLAYING: 语音播放中
- WAITING_USER: 等待用户输入
- ERROR: 错误状态

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

[MIT License](LICENSE)