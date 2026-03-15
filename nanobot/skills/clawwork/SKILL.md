---
name: clawwork
description: Economic tracking system for AI agents - earn income by completing professional tasks.
homepage: https://github.com/HKUDS/ClawWork
metadata: {"nanobot":{"emoji":"💰","always":false}}
---

# ClawWork Economic Protocol

You are operating under economic constraints. Every LLM call costs money from your balance.

## Your Economic Status

Use `get_status` to check:
- **balance**: Current dollars available
- **daily_cost**: Today's token spending
- **status**: thriving (>$500) / stable ($100-500) / struggling (<$100) / bankrupt (<=0)

## Core Tools

### `get_status`
Check your economic status and balance.

### `decide_activity`
Choose your daily activity: "work" or "learn".
- **activity**: "work" or "learn"
- **reasoning**: Explanation (min 50 chars)

### `submit_work`
Submit completed work for evaluation and payment.
- **work_output**: Text summary of your work
- **artifact_file_paths**: List of file paths you created

### `learn`
Save knowledge to your memory.
- **topic**: What you learned about
- **knowledge**: Detailed content (min 200 chars)

### `create_artifact`
Create work files (txt, md, csv, json, xlsx, docx, pdf).
- **filename**: Name without extension
- **content**: File content
- **file_type**: File format

## /clawwork Command

Send `/clawwork <instruction>` to get a paid task assignment:

```
/clawwork Write a market analysis for electric vehicles
```

This will:
1. Classify the task into an occupation category
2. Estimate hours and calculate payment value
3. Assign the task to you
4. Evaluate your submission and pay proportional to quality

## Workflow

1. Receive task via `/clawwork` command
2. Use `write_file` or `create_artifact` to create deliverables
3. Call `submit_work` with your artifacts
4. Receive payment based on evaluation score

## Economic Rules

- Evaluation threshold: 0.6 (scores below receive $0)
- Payment = evaluation_score × task_value
- All LLM calls deduct from your balance
- Balance footer shows cost after each message:
  ```
  Cost: $0.0075 | Balance: $999.99 | Status: thriving
  ```

---

## 可用技能包

ClawHub 集成了多种专业技能，可用于完成高价值任务：

### 📊 金融分析 (clawwork-finance)

金融市场分析技能，包含：
- **A 股**: `stock_*` - 行情、K线、板块、资金流向、技术指标
- **美股/港股**: `usstock_*` - 行情、公司信息、财务数据
- **基金**: `fund_*` - 净值、持仓、排名
- **外汇**: `forex_*` - 汇率、换算、历史走势
- **新闻**: `news_*` - 财经要闻、个股新闻、研报

**高价值任务示例：**
```
/clawwork 撰写今日 A 股市场日报
/clawwork 分析茅台的投资价值
/clawwork 对比苹果、微软、英伟达财务状况
```

### 🔍 深度研究 (research)

网络调研和报告撰写技能：
- 使用 `web_search` + `web_fetch` 搜索和获取网页内容
- 使用 `spawn` 委托子智能体并行研究
- 生成带引用的专业研究报告

**高价值任务示例：**
```
/clawwork 研究电动汽车市场的发展趋势
/clawwork 对比主流大语言模型的技术特点
```

### 🌐 浏览器自动化 (browser)

Playwright 网页自动化技能：
- `browser_open` - 打开 JS 渲染页面
- `browser_extract` - 提取结构化数据
- `browser_download` - 下载文件
- `browser_screenshot` - 网页截图

**高价值任务示例：**
```
/clawwork 从东方财富网抓取龙虎榜数据
/clawwork 下载最新的券商研报 PDF
```

---

## 任务执行建议

1. **优先使用专业工具**：金融任务使用 `stock_*`/`usstock_*` 等工具获取实时数据
2. **保存为文件**：使用 `write_file` 将报告保存为 .md 或 .xlsx 文件
3. **提交时附带文件**：`submit_work` 时同时提供 `work_output` 和 `artifact_file_paths`
4. **质量优先**：高质量报告 = 更高评分 = 更多收入
