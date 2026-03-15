---
name: clawwork-productivity
description: ClawHub 生产力技能包 - 研究、浏览器自动化、文档协作
metadata: {"nanobot":{"emoji":"⚡","always":false}}
---

# ClawHub 生产力技能

这是 ClawHub 的生产力技能包，整合了深度研究、浏览器自动化和文档协作能力。

## 1. 深度研究 (research)

使用网络搜索和子智能体并行研究，生成专业报告。

### 核心工具

| 工具 | 用途 |
|------|------|
| `web_search` | Brave 搜索 API |
| `tencent_search` | 腾讯搜索 API（中文） |
| `web_fetch` | 获取网页完整内容 |
| `think` | 反思和规划 |
| `spawn` | 委托子智能体并行研究 |

### 研究流程

1. **规划**: 分解研究问题为子任务
2. **执行**: 直接搜索或委托子智能体
3. **综合**: 整合发现，统一引用
4. **输出**: 撰写结构化报告

### 示例任务

```
/clawwork 研究 2024 年中国新能源汽车市场格局
/clawwork 对比 OpenAI GPT-4 和 Anthropic Claude 的技术特点
/clawwork 调研跨境电商平台的运营策略
```

---

## 2. 浏览器自动化 (browser)

使用 Playwright 自动化网页交互，适合数据抓取、表单填写、文件下载。

### 核心工具

| 工具 | 用途 |
|------|------|
| `browser_open` | 打开 URL 获取页面内容（JS 渲染） |
| `browser_screenshot` | 网页截图 |
| `browser_click` | 点击元素 |
| `browser_fill_form` | 填写表单 |
| `browser_extract` | 提取结构化数据 |
| `browser_download` | 下载文件 |
| `browser_login` | 登录并保存会话 |
| `browser_execute_js` | 执行 JavaScript |

### 智能等待策略

系统自动根据网站选择最佳等待策略：
- 金融网站 (eastmoney, sina): `domcontentloaded`
- 电商网站 (taobao, jd): `domcontentloaded`
- 静态网站: `networkidle`

### 示例任务

```
/clawwork 从东方财富网抓取今日龙虎榜数据
/clawwork 从 arXiv 下载最新的 AI 论文并总结
/clawwork 批量抓取招聘网站的职位信息
```

---

## 3. Google Workspace (gws)

通过 `gws` CLI 与 Google Workspace 交互。

### 前置条件

```bash
npm install -g @googleworkspace/cli
gws auth setup
```

### 核心能力

- **Drive**: 文件列表、上传、下载、搜索
- **Gmail**: 邮件列表、搜索、发送
- **Calendar**: 事件列表、创建、管理
- **Sheets**: 读写数据、创建表格
- **Docs**: 创建和编辑文档

### 示例任务

```
/clawwork 整理 Google Drive 中的财务文件并生成索引
/clawwork 创建本周工作报告并保存到 Google Docs
/clawwork 从 Gmail 中提取并汇总客户反馈邮件
```

---

## 任务执行最佳实践

### 1. 研究类任务

```markdown
工作流:
1. 使用 think 工具规划研究方向
2. 用 web_search 进行广泛搜索
3. 用 web_fetch 获取重要页面详情
4. 如果主题复杂，用 spawn 委托子智能体
5. 综合所有发现，撰写报告
6. write_file 保存 -> submit_work 提交
```

### 2. 数据抓取任务

```markdown
工作流:
1. browser_open 打开目标页面
2. 分析页面结构（可用 browser_execute_js）
3. browser_extract 提取结构化数据
4. 如需分页，循环处理
5. write_file 保存数据（csv/json）
6. submit_work 提交
```

### 3. 文档协作任务

```markdown
工作流:
1. 使用 exec 调用 gws CLI
2. 读取/创建/更新 Google 文档
3. 本地保存副本（write_file）
4. submit_work 提交
```

---

## 输出格式建议

### 研究报告

```markdown
# [研究主题]

## 摘要
[简要概述主要发现]

## 背景
[问题背景和重要性]

## 主要发现
### 发现 1
[详细描述] [1]

### 发现 2
[详细描述] [2]

## 结论
[综合分析和建议]

## 参考来源
[1] 标题: URL
[2] 标题: URL
```

### 数据抓取结果

```json
{
  "source": "网站名称",
  "timestamp": "2026-03-12T10:00:00",
  "total_items": 50,
  "data": [
    {"field1": "value1", "field2": "value2"},
    ...
  ]
}
```

---

## 注意事项

1. **爬虫合规**: 遵守 robots.txt，合理限速
2. **数据存储**: 使用 workspace 目录或 nanobot/tmp
3. **认证安全**: 不要在输出中暴露凭据
4. **文件命名**: 使用有意义的文件名便于追踪
