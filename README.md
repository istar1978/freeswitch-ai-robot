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
- **FreeSWITCH集成**：完整的ESL连接管理和拨号计划支持
- **连接监控**：自动检测和恢复FreeSWITCH连接
- **通话保护**：防止异常中断通话，优雅处理服务故障
- **自动重启**：服务异常退出时自动重启机制
- **HTTP API**：提供REST API接口用于呼叫控制
- **呼叫测试**：内置呼叫模拟测试工具，支持性能测试和录音
- **外呼功能**：支持从CSV文件读取联系人进行外呼活动
- **场景配置**：可配置的机器人行为，支持多场景切换

## 系统架构

项目采用模块化设计，主要组件包括：

- **clients/**: 外部服务客户端（ASR、LLM、TTS）
- **config/**: 配置管理
- **core/**: 核心业务逻辑（对话管理、状态机、健康检查）
- **freeswitch/**: FreeSWITCH集成（ESL处理、音频流、拨号计划）
- **storage/**: 数据存储（Redis客户端）
- **utils/**: 工具类（日志、助手函数）
- **api/**: HTTP API服务器（呼叫控制接口）
- **tests/**: 测试工具（呼叫模拟、性能测试）
- **outbound/**: 外呼管理（联系人管理、外呼活动）
- **scenarios/**: 场景配置（机器人行为配置、多场景支持）

## FreeSWITCH集成

### 拨号计划配置

项目自动生成FreeSWITCH拨号计划文件：

1. **XML拨号计划**：`freeswitch/dialplan_generator.py` 生成XML格式的拨号计划
2. **Lua脚本**：生成处理AI机器人呼叫的Lua脚本
3. **自动部署**：启动时自动保存到FreeSWITCH配置目录

### 连接管理

- **自动重连**：检测连接断开时自动重连FreeSWITCH
- **心跳监控**：定期检查ESL连接状态
- **连接保护**：确保通话过程中连接稳定

### API接口

提供HTTP API用于FreeSWITCH集成和功能扩展：

#### 基础呼叫接口
- `POST /call/start` - 开始呼叫处理
- `GET /call/status/{session_id}` - 查询呼叫状态
- `POST /call/end/{session_id}` - 结束呼叫

#### 测试接口
- `POST /test/simulate` - 模拟单个呼叫测试
- `POST /test/batch` - 批量运行测试
- `GET /test/metrics` - 获取测试指标

#### 外呼接口
- `POST /outbound/start` - 启动外呼活动
- `POST /outbound/stop` - 停止外呼活动
- `GET /outbound/status` - 获取外呼状态
- `POST /outbound/add-contact` - 添加联系人

#### 场景接口
- `GET /scenarios` - 获取场景列表
- `GET /scenarios/{scenario_id}` - 获取特定场景配置
- `POST /scenarios/{scenario_id}/activate` - 激活场景

#### 监控接口
- `GET /health` - 健康检查

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

### 测试配置
- `TEST_AUDIO_DIR`: 测试音频文件存储目录 (默认: ./test_audio)
- `TEST_METRICS_FILE`: 测试指标文件路径 (默认: ./test_metrics.json)

### 外呼配置
- `OUTBOUND_CONTACT_DIR`: 联系人文件目录 (默认: ./contacts)
- `OUTBOUND_MAX_CONCURRENT`: 最大并发外呼数 (默认: 5)
- `OUTBOUND_RETRY_ATTEMPTS`: 外呼重试次数 (默认: 3)

### 场景配置
- `SCENARIOS_DIR`: 场景配置文件目录 (默认: ./scenarios)
- `DEFAULT_SCENARIO`: 默认场景ID (默认: default)

## 运行

### 本地运行

1. 启动依赖服务（Redis、ASR、LLM、TTS、FreeSWITCH）
2. 设置环境变量
3. 运行主程序：

```bash
python main.py
```

应用将在8080端口启动HTTP API服务器。

### Docker运行

```bash
docker-compose up -d
```

### FreeSWITCH配置

1. 确保FreeSWITCH安装并运行
2. 运行应用时会自动生成拨号计划文件
3. 重载FreeSWITCH拨号计划：

```bash
fs_cli -x "reloadxml"
```

### API使用

#### 基础呼叫控制

```bash
# 开始呼叫
curl -X POST http://localhost:8080/call/start \
  -H "Content-Type: application/json" \
  -d '{"session_id": "call-123", "caller_id": "1001"}'

# 查询状态
curl http://localhost:8080/call/status/call-123

# 结束呼叫
curl -X POST http://localhost:8080/call/end/call-123
```

#### 测试功能

```bash
# 模拟单个呼叫测试
curl -X POST http://localhost:8080/test/simulate \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "default", "duration": 30, "record_audio": true}'

# 批量测试
curl -X POST http://localhost:8080/test/batch \
  -H "Content-Type: application/json" \
  -d '{"scenarios": ["default", "sales"], "iterations": 5, "concurrent": true}'

# 获取测试指标
curl http://localhost:8080/test/metrics
```

#### 外呼功能

```bash
# 启动外呼活动
curl -X POST http://localhost:8080/outbound/start \
  -H "Content-Type: application/json" \
  -d '{"campaign_name": "sales_campaign", "contact_file": "contacts.csv", "scenario_id": "sales"}'

# 停止外呼活动
curl -X POST http://localhost:8080/outbound/stop

# 获取外呼状态
curl http://localhost:8080/outbound/status

# 添加联系人
curl -X POST http://localhost:8080/outbound/add-contact \
  -H "Content-Type: application/json" \
  -d '{"contact": {"name": "John Doe", "phone": "1234567890", "priority": 1}}'
```

#### 场景管理

```bash
# 获取场景列表
curl http://localhost:8080/scenarios

# 获取特定场景配置
curl http://localhost:8080/scenarios/sales

# 激活场景
curl -X POST http://localhost:8080/scenarios/support/activate
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

## 故障恢复和监控

### 自动重启机制

- **异常检测**：监控应用运行状态，检测严重错误
- **自动重启**：异常退出时自动重启，最多重试5次
- **延迟重启**：重启间隔递增，避免频繁重启

### 通话保护

- **状态保持**：通话过程中保持连接状态
- **优雅降级**：服务故障时播放预设回复
- **中断处理**：正确处理用户打断和系统中断

### 健康监控

- **服务检查**：定期检查ASR、LLM、TTS、Redis服务状态
- **连接监控**：监控FreeSWITCH连接状态
- **告警通知**：检测到服务不健康时记录警告

### 日志和调试

- **结构化日志**：使用JSON格式日志，便于分析
- **轮转日志**：自动轮转日志文件，避免磁盘空间不足
- **多级别日志**：支持DEBUG、INFO、WARNING、ERROR级别

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
│   ├── esl_handler.py     # ESL连接管理
│   ├── audio_stream.py    # 音频流处理
│   └── dialplan_generator.py # 拨号计划生成
├── storage/               # 数据存储
├── utils/                 # 工具类
├── api/                   # HTTP API服务器
├── tests/                 # 测试工具
│   └── call_tester.py     # 呼叫模拟测试
├── outbound/              # 外呼管理
│   └── outbound_manager.py # 外呼活动管理
├── scenarios/             # 场景配置
│   └── scenario_manager.py # 场景配置管理
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