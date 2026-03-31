---
name: openbb
description: OpenBB 金融数据平台 - 股票、加密货币、外汇、宏观经济数据查询与分析
metadata: '{"nanobot": {"requires": {"bins": []}, "always": false}}'
---

# OpenBB 金融数据平台

你具备通过 OpenBB 数据平台获取全面金融数据的能力，覆盖股票、加密货币、外汇和宏观经济数据。

## 功能概述

### 1. 股票行情与历史数据
- 获取股票实时行情（价格、涨跌幅、成交量、市值）
- 获取历史K线数据（日线、周线、月线）
- 支持多数据源切换（yfinance, fmp, intrinio 等）

### 2. 公司分析
- 公司基本信息（行业、简介、员工数）
- 财务报表（利润表、资产负债表、现金流量表）
- 关键估值指标（PE/PB/PS/ROE/ROA/负债率）

### 3. 市场新闻
- 全球市场新闻
- 特定股票相关新闻

### 4. 加密货币
- 加密货币实时价格（BTC, ETH, SOL 等）

### 5. 外汇汇率
- 主要货币对汇率（EUR/USD, USD/JPY, USD/CNY 等）

### 6. 宏观经济
- 经济日历事件（CPI、GDP、非农等）

### 7. 股票搜索
- 按名称或代码搜索股票

## 可用工具

- `openbb_equity_quote` - 获取股票实时行情
- `openbb_equity_history` - 获取股票历史K线
- `openbb_company_profile` - 获取公司基本信息
- `openbb_financials` - 获取公司财务报表
- `openbb_metrics` - 获取估值指标
- `openbb_news` - 获取市场新闻
- `openbb_crypto` - 获取加密货币价格
- `openbb_currency` - 获取外汇汇率
- `openbb_economy` - 获取经济日历
- `openbb_search` - 搜索股票

## 使用示例

### 查询股票行情
```
用户: 查看苹果公司的股价
助手: [调用 openbb_equity_quote，symbol="AAPL"]
```

### 公司财务分析
```
用户: 分析微软的利润表
助手: [调用 openbb_financials，symbol="MSFT", statement="income"]
```

### 加密货币
```
用户: 比特币现在多少钱？
助手: [调用 openbb_crypto，symbol="BTC-USD"]
```

### 外汇汇率
```
用户: 美元兑人民币汇率
助手: [调用 openbb_currency，symbol="USDCNY"]
```

### 市场新闻
```
用户: 最近有什么财经新闻？
助手: [调用 openbb_news]
```

### 经济日历
```
用户: 这周有什么重要经济数据？
助手: [调用 openbb_economy]
```

## 数据源说明

OpenBB 支持多种数据源，工具默认使用 yfinance（免费），可通过 provider 参数切换：

| 数据源 | 特点 | 需要 API Key |
|--------|------|-------------|
| yfinance | 免费，覆盖广 | 否 |
| fmp | 数据质量高 | 是 |
| intrinio | 机构级数据 | 是 |
| polygon | 实时数据 | 是 |
| sec | SEC 官方数据 | 否 |

## 注意事项

1. **数据延迟**: 免费数据源有一定延迟，非实时交易数据
2. **安装要求**: 需要安装 openbb 包 (`pip install openbb`)
3. **风险提示**: 数据仅供参考，不构成投资建议
