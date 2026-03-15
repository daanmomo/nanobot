---
name: summarize
description: Summarize or extract text/transcripts from URLs, podcasts, and local files (great fallback for "transcribe this YouTube/video").
homepage: https://summarize.sh
metadata: {"nanobot":{"emoji":"🧾","requires":{"bins":["summarize"]},"install":[{"id":"brew","kind":"brew","formula":"steipete/tap/summarize","bins":["summarize"],"label":"Install summarize (brew)"}]}}
---

# 总结技能

快速 CLI 工具，用于总结 URL、本地文件和 YouTube 链接。

## 使用时机（触发短语）

当用户提出以下任一请求时立即使用此技能：
- "使用 summarize.sh"
- "这个链接/视频讲的是什么？"
- "总结这个 URL/文章"
- "转录这个 YouTube/视频"（尽力提取字幕；无需 `yt-dlp`）

## 快速开始

```bash
summarize "https://example.com" --model google/gemini-3-flash-preview
summarize "/path/to/file.pdf" --model google/gemini-3-flash-preview
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto
```

## YouTube：总结 vs 转录

尽力提取转录（仅限 URL）：

```bash
summarize "https://youtu.be/dQw4w9WgXcQ" --youtube auto --extract-only
```

若用户要求转录但内容过长，先返回精简总结，再询问要展开哪部分/时间范围。

## 模型与密钥

为所选 provider 设置 API 密钥：
- OpenAI: `OPENAI_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- xAI: `XAI_API_KEY`
- Google: `GEMINI_API_KEY`（别名：`GOOGLE_GENERATIVE_AI_API_KEY`、`GOOGLE_API_KEY`）

未设置时默认模型为 `google/gemini-3-flash-preview`。

## 常用参数

- `--length short|medium|long|xl|xxl|<chars>`
- `--max-output-tokens <count>`
- `--extract-only`（仅 URL）
- `--json`（机器可读）
- `--firecrawl auto|off|always`（备用提取）
- `--youtube auto`（若设置 `APIFY_API_TOKEN` 则使用 Apify 备用）

## 配置

可选配置文件：`~/.summarize/config.json`

```json
{ "model": "openai/gpt-5.2" }
```

可选服务：
- `FIRECRAWL_API_KEY` 用于被屏蔽的网站
- `APIFY_API_TOKEN` 用于 YouTube 备用
