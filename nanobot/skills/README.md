# nanobot 技能

本目录包含扩展 nanobot 能力的内置技能。

## 技能格式

每个技能是一个包含 `SKILL.md` 文件的目录，内容包括：
- YAML 前置元数据（name、description、metadata）
- 面向 agent 的 Markdown 指令

## 致谢

这些技能改编自 [OpenClaw](https://github.com/openclaw/openclaw) 的技能系统。
技能格式和元数据结构遵循 OpenClaw 的约定以保持兼容性。

## 可用技能

| 技能 | 描述 |
|-------|-------------|
| `browser` | 使用 Playwright 自动化浏览器交互 |
| `github` | 使用 `gh` CLI 与 GitHub 交互 |
| `weather` | 使用 wttr.in 和 Open-Meteo 获取天气信息 |
| `summarize` | 总结 URL、文件和 YouTube 视频 |
| `tmux` | 远程控制 tmux 会话 |
| `skill-creator` | 创建新技能 |

## 使用示例

### 浏览器技能

使用浏览器技能自动化网页交互、抓取内容、处理 JavaScript 密集型网站。

**安装：**
```bash
pip install playwright
playwright install chromium
```

**示例：网页截图**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    page.screenshot(path="screenshot.png", full_page=True)
    browser.close()
```

**示例：从页面抓取数据**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://news.ycombinator.com")

    titles = page.locator(".titleline > a").all()
    for title in titles[:5]:
        print(title.text_content())

    browser.close()
```

**示例：填写表单并提交**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com/search")
    page.fill('input[name="q"]', 'nanobot')
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    print(page.content())
    browser.close()
```

**示例：下载文件并分析**
```python
from playwright.sync_api import sync_playwright
from pathlib import Path
import csv

DOWNLOAD_DIR = Path("nanobot/tmp")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(accept_downloads=True)
    page = context.new_page()

    page.goto("https://example.com/export")

    with page.expect_download() as download_info:
        page.click("#download-csv")

    download = download_info.value
    save_path = DOWNLOAD_DIR / download.suggested_filename
    download.save_as(save_path)

    # 分析下载的 CSV
    with open(save_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(row)

    browser.close()
```

### GitHub 技能

```bash
# 检查 PR CI 状态
gh pr checks 55 --repo owner/repo

# 查看失败的 CI 日志
gh run view <run-id> --repo owner/repo --log-failed
```

### Tmux 技能

```bash
# 启动新的 tmux 会话
SOCKET="${TMPDIR:-/tmp}/nanobot.sock"
tmux -S "$SOCKET" new -d -s mysession

# 向会话发送命令
tmux -S "$SOCKET" send-keys -t mysession 'echo hello' Enter

# 捕获输出
tmux -S "$SOCKET" capture-pane -p -t mysession
```
