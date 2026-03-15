---
name: cron
description: Schedule reminders and recurring tasks.
---

# 定时任务技能

使用 `cron` 工具安排提醒或周期性任务。

## 三种模式

1. **提醒** - 消息直接发送给用户
2. **任务** - 消息为任务描述，agent 执行并发送结果
3. **一次性** - 在指定时间运行一次，然后自动删除

## 示例

固定提醒：
```
cron(action="add", message="该休息一下了！", every_seconds=1200)
```

动态任务（agent 每次执行）：
```
cron(action="add", message="检查 HKUDS/nanobot GitHub star 数并汇报", every_seconds=600)
```

一次性定时任务（根据当前时间计算 ISO 时间）：
```
cron(action="add", message="提醒我开会", at="<ISO datetime>")
```

列出/删除：
```
cron(action="list")
cron(action="remove", job_id="abc123")
```

## 时间表达式

| 用户说法 | 参数 |
|-----------|-----------|
| 每 20 分钟 | every_seconds: 1200 |
| 每小时 | every_seconds: 3600 |
| 每天 8 点 | cron_expr: "0 8 * * *" |
| 工作日 17 点 | cron_expr: "0 17 * * 1-5" |
| 指定时间 | at: ISO 时间字符串（根据当前时间计算） |
