---
name: gws
description: "Interact with Google Workspace using the `gws` CLI. Manage Drive, Gmail, Calendar, Sheets, Docs, and all Workspace APIs with structured JSON output."
metadata: {"nanobot":{"emoji":"📊","requires":{"bins":["gws"]},"install":[{"id":"npm","kind":"npm","package":"@googleworkspace/cli","bins":["gws"],"label":"Install Google Workspace CLI (npm)"}]}}
---

# Google Workspace 技能

使用 `gws` CLI 与 Google Workspace 交互。支持 Drive、Gmail、Calendar、Sheets、Docs 等所有 Workspace API。

## 认证

首次使用需要设置认证：

```bash
# 交互式设置（需要 gcloud CLI）
gws auth setup

# 后续登录
gws auth login

# 指定特定服务的 scope
gws auth login -s drive,gmail,sheets
```

## Google Drive

列出文件：
```bash
gws drive files list --params '{"pageSize": 10}'
```

搜索文件：
```bash
gws drive files list --params '{"q": "name contains '\''report'\'' and mimeType = '\''application/pdf'\''", "pageSize": 10}'
```

上传文件：
```bash
gws drive files create --json '{"name": "report.pdf"}' --upload ./report.pdf
```

下载文件：
```bash
gws drive files get --params '{"fileId": "FILE_ID", "alt": "media"}' --output ./downloaded.pdf
```

创建文件夹：
```bash
gws drive files create --json '{"name": "My Folder", "mimeType": "application/vnd.google-apps.folder"}'
```

## Gmail

列出邮件：
```bash
gws gmail users messages list --params '{"userId": "me", "maxResults": 10}'
```

搜索邮件：
```bash
gws gmail users messages list --params '{"userId": "me", "q": "from:sender@example.com subject:report"}'
```

获取邮件详情：
```bash
gws gmail users messages get --params '{"userId": "me", "id": "MESSAGE_ID"}'
```

发送邮件（需要 Base64 编码的 RFC 2822 消息）：
```bash
gws gmail users messages send --params '{"userId": "me"}' --json '{"raw": "BASE64_ENCODED_EMAIL"}'
```

## Google Calendar

列出日历：
```bash
gws calendar calendarList list
```

获取近期事件：
```bash
gws calendar events list --params '{"calendarId": "primary", "maxResults": 10, "timeMin": "2026-03-01T00:00:00Z", "orderBy": "startTime", "singleEvents": true}'
```

创建事件：
```bash
gws calendar events insert --params '{"calendarId": "primary"}' --json '{
  "summary": "Team Meeting",
  "start": {"dateTime": "2026-03-10T10:00:00+08:00"},
  "end": {"dateTime": "2026-03-10T11:00:00+08:00"},
  "attendees": [{"email": "colleague@example.com"}]
}'
```

## Google Sheets

读取数据：
```bash
gws sheets spreadsheets values get \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1:C10"}'
```

写入数据：
```bash
gws sheets spreadsheets values update \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Name", "Score"], ["Alice", 95], ["Bob", 87]]}'
```

追加数据：
```bash
gws sheets spreadsheets values append \
  --params '{"spreadsheetId": "SPREADSHEET_ID", "range": "Sheet1!A1", "valueInputOption": "USER_ENTERED"}' \
  --json '{"values": [["Charlie", 92]]}'
```

创建新表格：
```bash
gws sheets spreadsheets create --json '{"properties": {"title": "Q1 Budget"}}'
```

## Google Docs

创建文档：
```bash
gws docs documents create --json '{"title": "Meeting Notes"}'
```

获取文档内容：
```bash
gws docs documents get --params '{"documentId": "DOCUMENT_ID"}'
```

## 高级用法

### 分页

自动分页获取所有结果：
```bash
gws drive files list --params '{"pageSize": 100}' --page-all
```

限制分页数量：
```bash
gws drive files list --params '{"pageSize": 100}' --page-all --page-limit 5
```

### 查看 API Schema

查看任意方法的请求/响应 schema：
```bash
gws schema drive.files.list
gws schema gmail.users.messages.send
```

### 预览请求

使用 `--dry-run` 预览而不执行：
```bash
gws drive files create --json '{"name": "test.txt"}' --dry-run
```

### JSON 输出

所有命令默认输出结构化 JSON，可配合 `jq` 处理：
```bash
gws drive files list --params '{"pageSize": 5}' | jq '.files[].name'
```

## MCP Server

将 gws 作为 MCP Server 暴露给其他 AI 工具：

```bash
# 暴露特定服务
gws mcp -s drive,gmail,calendar

# 暴露所有服务（工具数量较多）
gws mcp -s all
```

MCP 客户端配置示例：
```json
{
  "mcpServers": {
    "gws": {
      "command": "gws",
      "args": ["mcp", "-s", "drive,gmail,calendar"]
    }
  }
}
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `GOOGLE_WORKSPACE_CLI_TOKEN` | 预获取的 OAuth2 访问令牌 |
| `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE` | OAuth 凭据 JSON 文件路径 |
| `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` | 配置目录（默认 `~/.config/gws`） |

## 服务账号认证

用于服务器端自动化：

```bash
export GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE=/path/to/service-account.json
gws drive files list
```

## 常见问题

### Shell 转义

Sheets 范围使用 `!`，需要用单引号包裹：
```bash
# 正确
gws sheets spreadsheets values get --params '{"range": "Sheet1!A1:C10"}'
```

### Scope 限制

OAuth 测试模式下 scope 数量有限制（约 25 个），建议按需选择服务：
```bash
gws auth login -s drive,gmail,sheets
```
