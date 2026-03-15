---
name: clawwork-finance
description: ClawHub 金融分析技能包 - A股、美股、基金、外汇、财经新闻
metadata: {"nanobot":{"emoji":"📊","always":false}}
---

# ClawHub 金融分析技能

这是 ClawHub 的金融分析技能包，整合了 A 股、美股、基金、外汇和财经新闻分析能力。适合完成金融研究、市场分析、投资报告等任务。

## 工具概览

### 1. A股分析 (stock_*)

| 工具 | 功能 |
|------|------|
| `stock_realtime_quote` | 获取 A 股实时行情 |
| `stock_history` | 获取历史 K 线数据 |
| `stock_index` | 获取主要指数（上证、深证、创业板） |
| `stock_market_stats` | 获取市场统计（涨跌家数、成交额） |
| `stock_sector_ranking` | 获取板块涨跌排名 |
| `stock_money_flow` | 获取个股资金流向 |
| `stock_north_flow` | 获取北向资金数据 |
| `stock_indicators` | 计算技术指标（MA、MACD、KDJ、RSI） |
| `stock_search` | 搜索股票代码 |
| `stock_daily_report` | 生成 A 股每日报告 |

**常用 A 股代码：**
- 600519 贵州茅台 | 000001 平安银行 | 002594 比亚迪
- 600036 招商银行 | 601318 中国平安 | 300750 宁德时代

### 2. 美股/港股分析 (usstock_*)

| 工具 | 功能 |
|------|------|
| `usstock_quote` | 获取美股/港股实时行情 |
| `usstock_history` | 获取历史 K 线数据 |
| `usstock_company` | 获取公司基本信息 |
| `usstock_financials` | 获取财务数据（估值、盈利） |
| `usstock_indices` | 获取主要指数（标普、纳斯达克、恒生） |
| `usstock_search` | 搜索股票代码 |

**常用代码：**
- 美股: AAPL、MSFT、GOOGL、AMZN、NVDA、TSLA、META
- 港股: 0700.HK（腾讯）、9988.HK（阿里）、1810.HK（小米）

### 3. 基金分析 (fund_*)

| 工具 | 功能 |
|------|------|
| `fund_nav` | 获取基金最新净值 |
| `fund_nav_history` | 获取历史净值走势 |
| `fund_holdings` | 获取基金持仓（前十大重仓） |
| `fund_ranking` | 获取基金排名（按收益率） |
| `fund_search` | 搜索基金代码 |
| `fund_info` | 获取基金基本信息 |

**热门基金：**
- 005827 易方达蓝筹精选 | 161725 招商中证白酒
- 003095 中欧医疗健康 | 001938 中欧时代先锋

### 4. 外汇分析 (forex_*)

| 工具 | 功能 |
|------|------|
| `forex_rate` | 获取实时汇率 |
| `forex_major_rates` | 获取主要货币汇率 |
| `forex_convert` | 汇率换算 |
| `forex_history` | 获取历史汇率走势 |

**货币代码：** USD、EUR、GBP、JPY、HKD、AUD、CAD、CNY

### 5. 财经新闻 (news_*)

| 工具 | 功能 |
|------|------|
| `news_financial` | 获取财经要闻 |
| `news_stock` | 获取个股新闻 |
| `news_announcements` | 获取公司公告 |
| `news_research` | 获取券商研报 |
| `news_flash` | 获取财经快讯 |

---

## ClawHub 金融任务示例

### 任务 1: 市场日报

```
/clawwork 撰写今日 A 股市场日报，包括：
1. 大盘走势（三大指数）
2. 板块涨跌排名前五
3. 北向资金流向
4. 热点新闻解读
```

**执行步骤：**
1. 调用 `stock_index` 获取三大指数
2. 调用 `stock_market_stats` 获取市场统计
3. 调用 `stock_sector_ranking` 获取板块排名
4. 调用 `stock_north_flow` 获取北向资金
5. 调用 `news_financial` 获取财经要闻
6. 用 `write_file` 保存报告
7. 用 `submit_work` 提交

### 任务 2: 个股分析报告

```
/clawwork 分析贵州茅台（600519）的投资价值
```

**执行步骤：**
1. `stock_realtime_quote(code="600519")` 获取实时行情
2. `stock_history(code="600519", period="daily", count=60)` 获取近期走势
3. `stock_indicators(code="600519")` 计算技术指标
4. `stock_money_flow(code="600519")` 获取资金流向
5. `news_stock(stock_code="600519")` 获取相关新闻
6. 综合分析，撰写报告
7. `write_file` + `submit_work`

### 任务 3: 美股科技股对比

```
/clawwork 对比分析苹果、微软、英伟达三家公司的财务状况
```

**执行步骤：**
1. 分别调用 `usstock_company` 获取公司信息
2. 分别调用 `usstock_financials` 获取财务数据
3. 对比市盈率、利润率、增长率等指标
4. 撰写对比分析报告
5. `write_file` + `submit_work`

### 任务 4: 基金持仓分析

```
/clawwork 分析易方达蓝筹精选（005827）的持仓情况
```

**执行步骤：**
1. `fund_info(fund_code="005827")` 获取基金信息
2. `fund_nav(fund_code="005827")` 获取最新净值
3. `fund_holdings(fund_code="005827")` 获取前十大持仓
4. 对重仓股进行简要分析
5. `write_file` + `submit_work`

### 任务 5: 汇率分析报告

```
/clawwork 分析近期人民币汇率走势及影响因素
```

**执行步骤：**
1. `forex_major_rates()` 获取主要货币汇率
2. `forex_history(currency_pair="USD/CNY", days=30)` 获取近期走势
3. `news_financial()` 获取相关宏观新闻
4. 分析汇率变动原因
5. `write_file` + `submit_work`

---

## 报告格式模板

### 市场日报模板

```markdown
# 市场日报 - YYYY-MM-DD

## 一、市场概况

### 主要指数
| 指数 | 收盘 | 涨跌幅 | 成交额 |
|------|------|--------|--------|
| 上证指数 | xxxx | +x.xx% | xxxx亿 |

### 市场情绪
- 上涨家数: xxxx | 下跌家数: xxxx
- 涨停: xx | 跌停: xx

## 二、板块表现

### 领涨板块
1. xxx板块 +x.xx%
2. ...

### 领跌板块
1. xxx板块 -x.xx%
2. ...

## 三、资金流向

- 北向资金: +xx亿
- 主力资金: ...

## 四、热点解读

[新闻分析...]

---
数据来源: 东方财富/AKShare
```

### 个股分析模板

```markdown
# 个股分析报告 - [股票名称]（代码）

## 基本信息
- 当前价格: xx.xx
- 涨跌幅: +x.xx%
- 市值: xxxx亿

## 技术分析
- MA趋势: [多头/空头排列]
- MACD: [金叉/死叉]
- RSI: xx [超买/超卖/正常]

## 资金动向
- 主力净流入: xx亿
- 北向资金: ...

## 近期新闻
1. [标题] - 来源
2. ...

## 投资建议
[基于以上分析的结论]

---
免责声明: 本报告仅供参考，不构成投资建议。
```

---

## 注意事项

1. **数据延迟**: A 股数据来自 AKShare（东方财富），有一定延迟
2. **交易时间**:
   - A 股: 9:30-11:30, 13:00-15:00
   - 美股: 美东 9:30-16:00
3. **风险提示**: 所有分析仅供参考，不构成投资建议
4. **文件保存**: 报告应使用 `write_file` 保存后再用 `submit_work` 提交

## 依赖安装

```bash
pip install -e ".[finance]"
# 或单独安装
pip install akshare yfinance
```
