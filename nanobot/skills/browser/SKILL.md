---
name: browser
description: "Automate browser interactions using Playwright. Navigate pages, fill forms, click elements, take screenshots, download files, and scrape content."
metadata: {"nanobot":{"emoji":"🌐","requires":{"bins":["playwright"]},"install":[{"id":"pip","kind":"pip","package":"playwright","bins":["playwright"],"label":"Install Playwright (pip install playwright)"},{"id":"browsers","kind":"shell","command":"playwright install chromium","label":"Install Chromium browser"}]}}
---

# 浏览器技能

使用 Playwright 自动化浏览器交互。适用于网页抓取、表单填写、测试、文件下载以及与 JavaScript 密集型网站交互。

## 智能网站策略

系统会根据网站域名自动选择最佳的页面加载等待策略：

| 网站类型 | 等待策略 | 原因 |
|---------|---------|------|
| 金融网站 (eastmoney, 10jqka, sina, hexun, jrj, xueqiu 等) | `domcontentloaded` | 动态资源多，避免超时 |
| 电商网站 (taobao, jd, tmall) | `domcontentloaded` | 大量异步加载内容 |
| 社交媒体 (weibo, zhihu, bilibili, douyin) | `domcontentloaded` | SPA 应用，动态渲染 |
| 静态网站和其他 | `networkidle` | 等待所有资源加载完成 |

如果 `networkidle` 策略超时，系统会自动回退到 `domcontentloaded`。

你也可以手动指定 `wait_until` 参数覆盖自动策略：
- `networkidle`: 等待网络完全空闲（适合静态页面）
- `domcontentloaded`: DOM 加载完成即可（适合动态网站）
- `load`: 页面基本加载完成（折中方案）

## 可用工具

以下浏览器自动化工具可用：

| 工具 | 描述 |
|------|-------------|
| `browser_open` | 打开 URL 并获取页面内容（适用于 JS 渲染页面） |
| `browser_screenshot` | 对页面或元素截图 |
| `browser_click` | 点击页面元素（按钮、链接） |
| `browser_fill_form` | 填写表单字段 |
| `browser_login` | 执行登录并保存会话 |
| `browser_load_session` | 加载已保存会话以进行认证访问 |
| `browser_extract` | 从页面提取结构化数据 |
| `browser_download` | 下载文件（支持认证下载） |
| `browser_execute_js` | 执行 JavaScript 并获取结果 |
| `browser_wait` | 等待元素出现/消失 |

## 工具使用示例

### 打开页面并获取内容
```
browser_open(url="https://example.com")
```

### 截图
```
browser_screenshot(url="https://example.com", full_page=true)
```

### 登录并保存会话
```
browser_login(
    url="https://example.com/login",
    username_selector="input[name='email']",
    password_selector="input[name='password']",
    username="user@example.com",
    password="secret",
    submit_selector="button[type='submit']",
    save_session="my_site"
)
```

### 使用已保存会话
```
browser_load_session(url="https://example.com/dashboard", session_name="my_site")
```

### 提取数据
```
browser_extract(
    url="https://example.com/products",
    list_selector=".product-card",
    selectors={"name": ".title", "price": ".price"}
)
```

### 带认证下载
```
browser_download(
    url="https://example.com/download",
    click_selector=".download-btn",
    session_name="my_site"
)
```

## 下载目录

所有下载的文件应保存到：`nanobot/tmp/`

## 安装

```bash
pip install playwright
playwright install chromium
```

## 快速开始（Python）

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    print(page.title())
    browser.close()
```

## 常用操作

### 导航与获取内容

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")

    # Get page title
    title = page.title()

    # Get text content
    content = page.content()

    # Get specific element text
    text = page.locator("h1").text_content()

    browser.close()
```

### 截图

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")

    # Full page screenshot
    page.screenshot(path="screenshot.png", full_page=True)

    # Element screenshot
    page.locator("header").screenshot(path="header.png")

    browser.close()
```

### 填写表单与点击

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com/login")

    # Fill input fields
    page.fill('input[name="username"]', 'myuser')
    page.fill('input[name="password"]', 'mypass')

    # Click button
    page.click('button[type="submit"]')

    # Wait for navigation
    page.wait_for_load_state("networkidle")

    browser.close()
```

### 等待元素

```python
# Wait for element to appear
page.wait_for_selector(".result", timeout=10000)

# Wait for element to be visible
page.locator(".modal").wait_for(state="visible")

# Wait for navigation
page.wait_for_url("**/dashboard")
```

### 提取数据

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com/products")

    # Get all matching elements
    items = page.locator(".product-card").all()
    for item in items:
        name = item.locator(".name").text_content()
        price = item.locator(".price").text_content()
        print(f"{name}: {price}")

    # Get attribute
    links = page.locator("a").all()
    for link in links:
        href = link.get_attribute("href")
        print(href)

    browser.close()
```

### 处理 JavaScript 密集型网站

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://spa-example.com")

    # Wait for dynamic content
    page.wait_for_selector(".dynamic-content")

    # Execute JavaScript
    result = page.evaluate("() => document.querySelector('.data').innerText")

    # Scroll to load more
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)  # Wait for lazy-loaded content

    browser.close()
```

### 下载文件

将文件下载到 `nanobot/tmp/` 目录进行分析。

```python
from playwright.sync_api import sync_playwright
from pathlib import Path

DOWNLOAD_DIR = Path(__file__).parent.parent / "tmp"  # nanobot/tmp/

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    page.goto("https://example.com/downloads")

    # Wait for download to start when clicking
    with page.expect_download() as download_info:
        page.click("a.download-link")

    download = download_info.value

    # Save to tmp directory
    save_path = DOWNLOAD_DIR / download.suggested_filename
    download.save_as(save_path)
    print(f"Downloaded: {save_path}")

    browser.close()
```

### 自定义文件名下载

```python
from playwright.sync_api import sync_playwright
from pathlib import Path
import time

DOWNLOAD_DIR = Path("nanobot/tmp")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    page.goto("https://example.com/report")

    with page.expect_download() as download_info:
        page.click("#export-pdf")

    download = download_info.value

    # Custom filename with timestamp
    filename = f"report_{int(time.time())}.pdf"
    save_path = DOWNLOAD_DIR / filename
    download.save_as(save_path)

    browser.close()
```

### 直接 URL 下载

```python
from playwright.sync_api import sync_playwright
from pathlib import Path

DOWNLOAD_DIR = Path("nanobot/tmp")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    # For direct file URLs
    url = "https://example.com/files/data.csv"

    with page.expect_download() as download_info:
        page.goto(url)

    download = download_info.value
    save_path = DOWNLOAD_DIR / "data.csv"
    download.save_as(save_path)

    browser.close()
```

### 分析已下载文件

下载后，使用 Python 分析文件：

```python
from pathlib import Path
import json
import csv

DOWNLOAD_DIR = Path("nanobot/tmp")

# Read text/CSV file
csv_path = DOWNLOAD_DIR / "data.csv"
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row)

# Read JSON file
json_path = DOWNLOAD_DIR / "data.json"
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    print(json.dumps(data, indent=2))

# Read Excel file (requires openpyxl)
# pip install openpyxl
import openpyxl
xlsx_path = DOWNLOAD_DIR / "report.xlsx"
wb = openpyxl.load_workbook(xlsx_path)
sheet = wb.active
for row in sheet.iter_rows(values_only=True):
    print(row)

# Read PDF file (requires PyPDF2 or pdfplumber)
# pip install pdfplumber
import pdfplumber
pdf_path = DOWNLOAD_DIR / "document.pdf"
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

### 批量下载文件

```python
from playwright.sync_api import sync_playwright
from pathlib import Path

DOWNLOAD_DIR = Path("nanobot/tmp")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    page.goto("https://example.com/files")

    # Get all download links
    links = page.locator("a[href$='.pdf']").all()

    for i, link in enumerate(links):
        with page.expect_download() as download_info:
            link.click()
        download = download_info.value
        save_path = DOWNLOAD_DIR / f"file_{i}_{download.suggested_filename}"
        download.save_as(save_path)
        print(f"Downloaded: {save_path}")

    browser.close()
```

### 下载前进行认证

```python
from playwright.sync_api import sync_playwright
from pathlib import Path

DOWNLOAD_DIR = Path("nanobot/tmp")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    # Login first
    page.goto("https://example.com/login")
    page.fill('input[name="username"]', 'user')
    page.fill('input[name="password"]', 'pass')
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard")

    # Now download protected file
    page.goto("https://example.com/protected/files")

    with page.expect_download() as download_info:
        page.click(".download-btn")

    download = download_info.value
    save_path = DOWNLOAD_DIR / download.suggested_filename
    download.save_as(save_path)

    browser.close()
```

## CLI 使用

Playwright 也提供 CLI 工具：

```bash
# Open browser in headed mode for debugging
playwright open https://example.com

# Generate code by recording actions
playwright codegen https://example.com

# Take screenshot from CLI
playwright screenshot https://example.com screenshot.png

# Generate PDF
playwright pdf https://example.com page.pdf
```

## 调试技巧

1. **使用 headed 模式**进行调试：
   ```python
   browser = p.chromium.launch(headless=False, slow_mo=500)
   ```

2. **启用 tracing** 记录操作：
   ```python
   context.tracing.start(screenshots=True, snapshots=True)
   # ... do stuff ...
   context.tracing.stop(path="trace.zip")
   # View with: playwright show-trace trace.zip
   ```

3. **使用 pause** 进行交互式调试：
   ```python
   page.pause()  # Opens inspector
   ```

## 论文下载与分析

浏览器技能包含用于下载和分析学术论文的脚本。

### 快速使用

```bash
# Search for papers about 豆包 (Doubao)
python nanobot/skills/browser/scripts/download_paper.py "豆包"

# Download and summarize the first matching paper
python nanobot/skills/browser/scripts/download_paper.py "豆包" -d -o doubao_summary.md

# Search ByteDance papers
python nanobot/skills/browser/scripts/download_paper.py "ByteDance large language model" -d
```

### Example: 总结豆包最新论文

```python
from playwright.sync_api import sync_playwright
from pathlib import Path
import re

DOWNLOAD_DIR = Path("nanobot/tmp")

def search_and_download_doubao_paper():
    """搜索并下载豆包/ByteDance 最新论文"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # 搜索 arxiv
        page.goto("https://arxiv.org/search/?query=ByteDance+Doubao&searchtype=all")
        page.wait_for_load_state("networkidle")

        # 获取第一篇论文
        first_paper = page.locator("li.arxiv-result").first

        # 提取论文信息
        title = first_paper.locator("p.title").text_content().strip()
        abstract = first_paper.locator("span.abstract-full").text_content().strip()
        abstract = re.sub(r'\s*△ Less\s*$', '', abstract)

        # 获取 PDF 链接
        arxiv_link = first_paper.locator("p.list-title a").first.get_attribute("href")
        arxiv_id = arxiv_link.split("/")[-1]
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        print(f"论文标题: {title}")
        print(f"摘要: {abstract[:200]}...")

        # 下载 PDF
        with page.expect_download() as download_info:
            page.goto(pdf_url)

        download = download_info.value
        pdf_path = DOWNLOAD_DIR / f"{arxiv_id.replace('/', '_')}.pdf"
        download.save_as(pdf_path)

        print(f"PDF 已下载到: {pdf_path}")

        browser.close()

        return {
            "title": title,
            "abstract": abstract,
            "arxiv_id": arxiv_id,
            "pdf_path": str(pdf_path)
        }

# 运行
paper_info = search_and_download_doubao_paper()
```

### 分析已下载的 PDF

```python
import pdfplumber
from pathlib import Path

DOWNLOAD_DIR = Path("nanobot/tmp")

def analyze_paper(pdf_path: Path) -> dict:
    """分析论文 PDF 并提取关键信息"""
    result = {
        "total_pages": 0,
        "sections": [],
        "key_findings": []
    }

    with pdfplumber.open(pdf_path) as pdf:
        result["total_pages"] = len(pdf.pages)

        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        # 提取章节
        section_pattern = r'\n(\d+\.?\s*(?:Introduction|Method|Results|Conclusion|Discussion|Experiments|Related Work))\s*\n'
        sections = re.findall(section_pattern, full_text, re.IGNORECASE)
        result["sections"] = sections

        # 提取摘要
        abstract_match = re.search(r'Abstract[:\s]*([\s\S]{100,1000}?)(?=\n\s*\d+\.?\s*Introduction|\n\s*Keywords)', full_text, re.IGNORECASE)
        if abstract_match:
            result["abstract"] = abstract_match.group(1).strip()

    return result

# 使用
pdf_path = DOWNLOAD_DIR / "2401.12345.pdf"
analysis = analyze_paper(pdf_path)
print(f"页数: {analysis['total_pages']}")
print(f"章节: {analysis['sections']}")
```

### 生成总结报告

```python
from datetime import datetime
from pathlib import Path

DOWNLOAD_DIR = Path("nanobot/tmp")

def generate_paper_summary(paper_info: dict, analysis: dict) -> str:
    """生成论文总结报告"""
    summary = f"""# 论文总结

**生成时间:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 基本信息

- **标题:** {paper_info.get('title', 'N/A')}
- **ArXiv ID:** {paper_info.get('arxiv_id', 'N/A')}
- **总页数:** {analysis.get('total_pages', 'N/A')}

## 摘要

{paper_info.get('abstract', analysis.get('abstract', '无摘要'))}

## 论文结构

{chr(10).join(f'- {s}' for s in analysis.get('sections', []))}

## 本地文件

PDF: `{paper_info.get('pdf_path', 'N/A')}`
"""
    return summary

# 保存总结
summary = generate_paper_summary(paper_info, analysis)
summary_path = DOWNLOAD_DIR / "doubao_paper_summary.md"
summary_path.write_text(summary, encoding="utf-8")
print(f"总结已保存到: {summary_path}")
```

## 最佳实践

- 生产/自动化环境始终使用 `headless=True`
- 对慢速页面设置合适的超时
- 优先使用具体选择器（id、data-testid）而非通用选择器
- 如需要，处理 cookie 同意横幅
- 抓取时遵守 robots.txt 和限流
- 完成后关闭浏览器以释放资源
- 论文下载需安装 `pdfplumber` 提取 PDF 文本：`pip install pdfplumber`
