---
name: Aware Triggers
description: 增强触发器系统，支持 HTTP 轮询、Webhook 接收、智能心跳、Observation 记录。借鉴 Clawith/OpenClaw 的 Aware 自主意识引擎。
---

# Aware Triggers — 自主意识触发器系统

借鉴 Clawith/OpenClaw 的 Aware 引擎，为 nanobot 增加自主感知能力。

## 核心能力

### 1. HTTP 轮询触发器 (Poll Trigger)
监控指定 URL，检测变化时自动通知。

```bash
python3 scripts/poll_trigger.py \
  --url "https://api.example.com/status" \
  --json-path "$.status" \
  --fire-on change \
  --webhook "$FEISHU_WEBHOOK"
```

### 2. Webhook 接收器 (Webhook Trigger)
启动本地 HTTP 服务器，接收外部 POST 请求并触发动作。

```bash
python3 scripts/webhook_server.py --port 8765
```

### 3. 智能心跳 v2 (Enhanced Heartbeat)
学自 OpenClaw 的心跳系统，支持智能调度、安静时间、状态追踪。

```bash
# 标准心跳
python3 scripts/heartbeat_v2.py

# 忽略安静时间
python3 scripts/heartbeat_v2.py --force

# 有事时推送飞书
python3 scripts/heartbeat_v2.py --notify

# 全量检查（忽略间隔）
python3 scripts/heartbeat_v2.py --full
```

**智能特性：**
- 🕐 不同检查项有不同频率（focus 30min, memory 24h, triggers 1h）
- 🌙 安静时间 23:00-08:00 不主动打扰
- 📊 状态追踪 heartbeat_state.json
- 📦 已完成项超过 5 个自动归档
- 📌 支持 HEARTBEAT.md 用户自定义 checklist

### 4. Observation 记录系统 (学自 OpenClaw claude-mem)
自动记录重要操作，支持搜索和上下文注入。

```bash
# 记录
python3 scripts/observation.py add -t "部署飞书日报" -d "推送成功" -c "task"

# 搜索
python3 scripts/observation.py search "飞书"

# 最近记录
python3 scripts/observation.py recent -n 10

# 今日记录
python3 scripts/observation.py today

# 生成可注入上下文（用于 system prompt）
python3 scripts/observation.py inject -n 20

# 统计
python3 scripts/observation.py stats

# 清理 30 天前的记录
python3 scripts/observation.py cleanup --days 30
```

**数据库：** `memory/observations.db` (SQLite)

## 触发器配置

配置文件：`config/triggers.json`
心跳状态：`config/heartbeat_state.json`

## Focus-Trigger 绑定规则

1. 创建任务触发器前，**必须先在 focus.md 添加对应 checklist 项**
2. 触发器的 `focus_ref` 关联 focus.md 中的标识符
3. 任务完成时，同时取消触发器和更新 focus

## 自治权限等级

| 等级 | 行为 | 适用操作 |
|------|------|---------|
| L1 | 静默执行 | 读文件、查行情、搜索 |
| L2 | 执行并通知 | 写文件、推送飞书、创建文档 |
| L3 | **必须确认** | 删文件、发外部消息、金融操作 |

## 工具使用铁律（学自 Clawith）

1. **永远不要假装执行了工具** — 必须真正调用并获得结果
2. **永远不要凭记忆编造文件内容** — 即使之前看过也要重新 read_file
3. **复杂任务进行中主动保存进度**到 focus.md
4. **触发器 reason 要详细** — 给未来自己的指令手册
5. **渐进式技能加载** — 需要 Skill 时先 read_file，不凭记忆猜测

## 文件结构

```
aware-triggers/
├── SKILL.md              ← 本文件
├── config/
│   ├── triggers.json     ← 触发器配置
│   └── heartbeat_state.json ← 心跳状态追踪
├── scripts/
│   ├── poll_trigger.py   ← HTTP 轮询
│   ├── webhook_server.py ← Webhook 接收
│   ├── heartbeat.py      ← 心跳 v1（保留）
│   ├── heartbeat_v2.py   ← 心跳 v2（推荐）
│   └── observation.py    ← Observation 记录
└── state/
    ├── heartbeat.log     ← v1 心跳日志
    └── heartbeat_v2.log  ← v2 心跳日志
```
