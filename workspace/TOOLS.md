# 可用工具

本文档描述 nanobot 可用的工具。

## 文件操作

### read_file
读取文件内容。
```
read_file(path: str) -> str
```

### write_file
将内容写入文件（如需要会创建父目录）。
```
write_file(path: str, content: str) -> str
```

### edit_file
通过替换指定文本来编辑文件。
```
edit_file(path: str, old_text: str, new_text: str) -> str
```

### list_dir
列出目录内容。
```
list_dir(path: str) -> str
```

## Shell 执行

### exec
执行 shell 命令并返回输出。
```
exec(command: str, working_dir: str = None) -> str
```

**安全说明：**
- 命令有可配置的超时时间（默认 60 秒）
- 危险命令会被阻止（rm -rf、format、dd、shutdown 等）
- 输出在 10,000 字符处截断
- 可选 `restrictToWorkspace` 配置以限制路径

## 网络访问

### web_search
使用 Brave Search API 搜索网络。
```
web_search(query: str, count: int = 5) -> str
```

返回包含标题、URL 和摘要的搜索结果。需要在配置中设置 `tools.web.search.apiKey`。

### web_fetch
抓取并提取 URL 的主要内容。
```
web_fetch(url: str, extractMode: str = "markdown", maxChars: int = 50000) -> str
```

**说明：**
- 使用 readability 提取内容
- 支持 markdown 或纯文本提取
- 默认在 50,000 字符处截断输出

## 通信

### message
向用户发送消息（内部使用）。
```
message(content: str, channel: str = None, chat_id: str = None) -> str
```

## 后台任务

### spawn
启动子智能体在后台处理任务。
```
spawn(task: str, label: str = None) -> str
```

用于可独立运行的复杂或耗时任务。子智能体将完成任务并在完成后汇报。

## 浏览器自动化

使用 Playwright 进行浏览器自动化。系统会根据网站自动选择最佳等待策略。

### browser_open
打开 URL 并获取页面内容。
```
browser_open(url: str, wait_until: str = None, timeout: int = None) -> dict
```

### browser_screenshot
对网页进行截图。
```
browser_screenshot(url: str, full_page: bool = True, selector: str = None, filename: str = None) -> dict
```

### browser_click
点击页面元素。
```
browser_click(url: str, selector: str, wait_after: int = 2000) -> dict
```

### browser_fill_form
填写表单字段。
```
browser_fill_form(url: str, fields: dict, submit_selector: str = None) -> dict
```

### browser_extract
从页面提取结构化数据。
```
browser_extract(url: str, selectors: dict, list_selector: str = None, limit: int = 50) -> dict
```

### browser_download
下载文件。
```
browser_download(url: str, click_selector: str = None, filename: str = None, session_name: str = None) -> dict
```

### browser_login / browser_load_session
登录网站并保存/加载会话。

**智能网站策略**：
- 金融网站 (eastmoney, sina, 10jqka 等) → 使用 `domcontentloaded`
- 电商/社交 (taobao, zhihu, bilibili 等) → 使用 `domcontentloaded`
- 其他网站 → 使用 `networkidle`

如果 `networkidle` 超时，系统会自动回退到 `domcontentloaded`。

## 定时提醒（Cron）

使用 `exec` 工具通过 `nanobot cron add` 创建定时提醒：

### 设置重复提醒
```bash
# 每天上午 9 点
nanobot cron add --name "morning" --message "早上好！☀️" --cron "0 9 * * *"

# 每 2 小时
nanobot cron add --name "water" --message "喝水啦！💧" --every 7200
```

### 设置一次性提醒
```bash
# 在指定时间（ISO 格式）
nanobot cron add --name "meeting" --message "会议开始了！" --at "2025-01-31T15:00:00"
```

### 管理提醒
```bash
nanobot cron list              # 列出所有任务
nanobot cron remove <job_id>   # 删除任务
```

## 心跳任务管理

工作区中的 `HEARTBEAT.md` 文件每 30 分钟检查一次。
使用文件操作管理周期性任务：

### 添加定时任务
```python
# 追加新任务
edit_file(
    path="HEARTBEAT.md",
    old_text="## 示例任务",
    new_text="- [ ] 新的周期性任务\n\n## 示例任务"
)
```

### 删除心跳任务
```python
# 删除指定任务
edit_file(
    path="HEARTBEAT.md",
    old_text="- [ ] 要删除的任务\n",
    new_text=""
)
```

### 重写所有任务
```python
# 替换整个文件
write_file(
    path="HEARTBEAT.md",
    content="# 心跳任务\n\n- [ ] 任务 1\n- [ ] 任务 2\n"
)
```

---

## 添加自定义工具

要添加自定义工具：
1. 在 `nanobot/agent/tools/` 中创建继承 `Tool` 的类
2. 实现 `name`、`description`、`parameters` 和 `execute`
3. 在 `AgentLoop._register_default_tools()` 中注册
