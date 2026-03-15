"""CLI commands for nanobot."""

import asyncio
import os
import select
import signal
import sys
from pathlib import Path

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from nanobot import __logo__, __version__

app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response with consistent terminal styling."""
    content = response or ""
    body = Markdown(content) if render_markdown else Text(content)
    console.print()
    console.print(f"[cyan]{__logo__} nanobot[/cyan]")
    console.print(body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Read user input using prompt_toolkit (handles paste, history, display).

    prompt_toolkit natively handles:
    - Multiline paste (bracketed paste mode)
    - History navigation (up/down arrows)
    - Clean display (no ghost characters or artifacts)
    """
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """nanobot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path

    config_path = get_config_path()

    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()

    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")

    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")

    # Create default bootstrap files
    _create_workspace_templates(workspace)

    console.print(f"\n{__logo__} nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# 智能体指令

你是一个有用的 AI 助手。请保持简洁、准确、友好。

## 行为准则

- 在执行操作前先说明你要做什么
- 当请求不明确时主动询问澄清
- 使用工具帮助完成任务
- 将重要信息记录到记忆文件中

## 可用工具

你可以使用：
- 文件操作（读取、写入、编辑、列表）
- Shell 命令（exec）
- 网络访问（搜索、抓取）
- 浏览器自动化（打开页面、截图、点击、填表、提取数据、下载）
- 消息发送（message）
- 后台任务（spawn）

## 浏览器使用

当需要访问 JavaScript 渲染的页面或进行网页自动化时，使用浏览器工具：

```
browser_open(url="https://example.com")  # 打开并获取内容
browser_screenshot(url="https://example.com")  # 截图
browser_extract(url="...", selectors={"title": "h1"})  # 提取数据
```

**自动策略**：系统会根据网站类型自动选择等待策略，无需手动配置。

## 记忆

- 使用 `memory/` 目录存放每日笔记
- 使用 `MEMORY.md` 存放长期信息

## 定时提醒

使用 `exec` 运行 `nanobot cron add` 创建提醒：
```
nanobot cron add --name "reminder" --message "消息" --at "YYYY-MM-DDTHH:MM:SS"
```

## 心跳任务

`HEARTBEAT.md` 每 30 分钟检查一次。编辑此文件管理周期性任务。
""",
        "SOUL.md": """# 灵魂

我是 nanobot，你的个人 AI 助手。

## 性格

- 乐于助人、友好
- 简洁、切中要点
- 好奇、乐于学习

## 价值观

- 准确优先于速度
- 用户隐私与安全
- 行为透明
""",
        "USER.md": """# 用户档案

关于用户的信息，用于个性化交互。

## 基本信息

- **姓名**：（你的名字）
- **时区**：（你的时区，例如 UTC+8）
- **语言**：（首选语言）

## 偏好设置

- 沟通风格：随意 / 专业 / 技术向
- 回复长度：简短精炼 / 详细解释 / 自适应
""",
        "HEARTBEAT.md": """# 心跳任务

此文件每 30 分钟检查一次。
在下方添加你希望智能体定期执行的任务。

如果此文件没有任务（仅有标题和注释），智能体将跳过心跳检查。

## 进行中的任务

<!-- 在此行下方添加你的周期性任务 -->


## 已完成

<!-- 将已完成的任务移到这里或删除 -->
""",
    }

    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")

    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# 长期记忆

本文件存储应在多次会话间持久保存的重要信息。

## 用户信息

（关于用户的重要信息）

## 偏好设置

（随时间学习到的用户偏好）

## 项目上下文

（关于进行中项目的信息）

## 重要备注

（需要记住的事项）

---

*当 nanobot 需要记住重要信息时，会自动更新此文件。*
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")

    # Create skills directory for custom user skills
    skills_dir = workspace / "skills"
    skills_dir.mkdir(exist_ok=True)


def _make_provider(config):
    """Create LiteLLMProvider from config. Exits if no API key found."""
    import os

    from nanobot.providers.litellm_provider import LiteLLMProvider

    # Check if custom provider is enabled
    custom = config.providers.custom
    if custom.enabled and custom.api_key:
        api_base = custom.api_base or None
        model = custom.model or config.agents.defaults.model

        # For Anthropic-compatible endpoints, set env vars
        if api_base and "anthropic" in api_base.lower():
            base_url = api_base.rstrip("/")
            os.environ["ANTHROPIC_API_KEY"] = custom.api_key
            os.environ["ANTHROPIC_API_BASE"] = base_url
            # Prefix model with anthropic/ for LiteLLM
            if not model.startswith("anthropic/"):
                model = f"anthropic/{model}"

        return LiteLLMProvider(
            api_key=custom.api_key,
            api_base=None if "anthropic" in (api_base or "").lower() else api_base,
            default_model=model,
        )

    # Standard provider flow
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=config.get_provider_name(),
    )


# ============================================================================
# Gateway / Server
# ============================================================================


def _clear_proxy_env() -> None:
    """Clear proxy environment variables to avoid connection issues."""
    for proxy_var in (
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
        "ALL_PROXY", "all_proxy",
    ):
        if proxy_var in os.environ:
            del os.environ[proxy_var]


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the nanobot gateway."""
    # Clear proxy env vars FIRST before importing any SDK
    _clear_proxy_env()

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.session.manager import SessionManager

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    console.print(f"{__logo__} Starting nanobot gateway on port {port}...")

    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)

    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Use provider's default model (respects custom provider config)
    model = provider.default_model

    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        tencent_config=config.tools.web.tencent,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")

    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )

    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)

    # 设置飞书流式回调
    feishu_channel = channels.get_channel("feishu")
    if feishu_channel:
        async def on_stream(channel: str, chat_id: str, content: str, is_final: bool) -> bool:
            """流式输出回调，更新飞书卡片。返回 True 表示已发送最终消息。"""
            if channel != "feishu":
                return False
            from nanobot.channels.feishu import FeishuChannel
            if not isinstance(feishu_channel, FeishuChannel):
                return False
            if is_final:
                await feishu_channel.stream_end(chat_id, content)
                return True  # 飞书流式结束，已发送最终消息
            else:
                # 如果还没开始，先创建占位卡片
                if chat_id not in feishu_channel._stream_states:
                    await feishu_channel.stream_start(chat_id)
                await feishu_channel.stream_update(chat_id, content)
                return False

        agent.set_stream_callback(on_stream)
        console.print("[green]✓[/green] Feishu streaming enabled")

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print("[green]✓[/green] Heartbeat: every 30m")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during chat"),
):
    """Interact with the agent directly."""
    # Clear proxy env vars FIRST before importing any SDK
    _clear_proxy_env()

    from loguru import logger

    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus
    from nanobot.config.loader import load_config

    config = load_config()

    bus = MessageBus()
    provider = _make_provider(config)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        tencent_config=config.tools.web.tencent,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )

    # Show spinner when logs are off (no output to miss); skip when logs are on
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        # Animated spinner is safe to use with prompt_toolkit input handling
        return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

    if message:
        # Single message mode
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id)
            _print_agent_response(response, render_markdown=markdown)

        asyncio.run(run_once())
    else:
        # Interactive mode
        _init_prompt_session()
        console.print(f"{__logo__} Interactive mode (type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit)\n")

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    command = user_input.strip()
                    if not command:
                        continue

                    if _is_exit_command(command):
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break

                    with _thinking_ctx():
                        response = await agent_loop.process_direct(user_input, session_id)
                    _print_agent_response(response, render_markdown=markdown)
                except KeyboardInterrupt:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
                except EOFError:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )

    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess

    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"

    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge

    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)

    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)

    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge

    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)

    console.print(f"{__logo__} Setting up bridge...")

    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))

    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)

        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)

        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)

    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess

    bridge_dir = _get_bridge_dir()

    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")

    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"

        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time

        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"

        table.add_row(job.id, job.name, sched, status, next_run)

    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )

    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print("[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# ClawWork Commands (Economic Tracking)
# ============================================================================

clawwork_app = typer.Typer(help="ClawWork economic tracking mode")
app.add_typer(clawwork_app, name="clawwork")


def _check_clawwork_enabled(config) -> None:
    """Exit with error if ClawWork is not enabled."""
    if not config.agents.clawwork.enabled:
        console.print("[red]Error: ClawWork is not enabled.[/red]")
        console.print("Set agents.clawwork.enabled = true in ~/.nanobot/config.json")
        raise typer.Exit(1)


def _build_clawwork_state(config):
    """Build ClawWorkState from config."""
    from pathlib import Path

    from nanobot.clawwork import ClawWorkState, EconomicTracker

    cw = config.agents.clawwork

    # Derive signature from config or fall back to model name
    sig = cw.signature or config.agents.defaults.model.replace("/", "-")
    data_path = str(Path(cw.data_path) / sig) if cw.data_path else str(
        Path("./data/clawwork") / sig
    )

    # EconomicTracker
    tracker = EconomicTracker(
        signature=sig,
        initial_balance=cw.initial_balance,
        input_token_price=cw.token_pricing.input_price,
        output_token_price=cw.token_pricing.output_price,
        data_path=str(Path(data_path) / "economic"),
    )
    tracker.initialize()

    state = ClawWorkState(
        economic_tracker=tracker,
        task_manager=None,  # Optional, can be extended
        evaluator=None,  # Optional, can be extended
        signature=sig,
        data_path=data_path,
        enable_file_reading=cw.enable_file_reading,
    )
    return state


@clawwork_app.command("agent")
def clawwork_agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send"),
    session_id: str = typer.Option("cli:clawwork", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show runtime logs"),
):
    """Chat with agent in ClawWork economic mode.

    Every message is cost-tracked and /clawwork command is available.

    Examples:
        nanobot clawwork agent
        nanobot clawwork agent -m "/clawwork Write a market analysis"
        nanobot clawwork agent -m "What is my balance?"
    """
    from loguru import logger

    from nanobot.bus.queue import MessageBus
    from nanobot.clawwork import ClawWorkAgentLoop
    from nanobot.config.loader import load_config

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    config = load_config()
    _check_clawwork_enabled(config)

    bus = MessageBus()
    provider = _make_provider(config)
    state = _build_clawwork_state(config)

    agent_loop = ClawWorkAgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        tencent_config=config.tools.web.tencent,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        clawwork_state=state,
    )

    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return console.status("[dim]clawwork is thinking...[/dim]", spinner="dots")

    balance = state.economic_tracker.get_balance()
    console.print(
        f"[bold cyan]ClawWork[/bold cyan] | {state.signature} | "
        f"balance: ${balance:.2f} | status: {state.economic_tracker.get_survival_status()}\n"
    )

    if message:
        # Single message mode
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id)
            _print_agent_response(response, render_markdown=markdown)

        asyncio.run(run_once())
    else:
        # Interactive mode
        _init_prompt_session()
        console.print(
            "Interactive mode - type [bold]exit[/bold] or [bold]Ctrl+C[/bold] to quit\n"
            "Use [bold]/clawwork <instruction>[/bold] to assign a paid task\n"
        )

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    command = user_input.strip()
                    if not command:
                        continue

                    if _is_exit_command(command):
                        _restore_terminal()
                        console.print("\nGoodbye!")
                        break

                    with _thinking_ctx():
                        response = await agent_loop.process_direct(command, session_id)
                    _print_agent_response(response, render_markdown=markdown)
                except KeyboardInterrupt:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
                except EOFError:
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break

        asyncio.run(run_interactive())


@clawwork_app.command("gateway")
def clawwork_gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start gateway with ClawWork economic tracking.

    All channels (Telegram, Discord, etc.) will have cost tracking enabled.
    """
    from nanobot.bus.queue import MessageBus
    from nanobot.channels.manager import ChannelManager
    from nanobot.clawwork import ClawWorkAgentLoop
    from nanobot.config.loader import get_data_dir, load_config
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    from nanobot.session.manager import SessionManager

    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)

    config = load_config()
    _check_clawwork_enabled(config)

    console.print(f"{__logo__} Starting ClawWork gateway on port {port}...")

    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)
    state = _build_clawwork_state(config)

    # Create cron service
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    # Use provider's default model (respects custom provider config)
    model = provider.default_model

    # Create ClawWork agent
    agent = ClawWorkAgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        max_tokens=config.agents.defaults.max_tokens,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        tencent_config=config.tools.web.tencent,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        clawwork_state=state,
    )

    # Set cron callback
    async def on_cron_job(job: CronJob) -> str | None:
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job

    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        return await agent.process_direct(prompt, session_key="heartbeat")

    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,
        enabled=True
    )

    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)

    balance = state.economic_tracker.get_balance()
    console.print(
        f"[green]✓[/green] ClawWork: {state.signature} | "
        f"balance: ${balance:.2f} | status: {state.economic_tracker.get_survival_status()}"
    )

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")

    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")

    console.print("[green]✓[/green] Heartbeat: every 30m")

    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()

    asyncio.run(run())


@clawwork_app.command("status")
def clawwork_status():
    """Show ClawWork economic status."""
    from nanobot.config.loader import load_config

    config = load_config()

    cw = config.agents.clawwork
    console.print("[bold cyan]ClawWork Status[/bold cyan]\n")

    if not cw.enabled:
        console.print("[yellow]ClawWork is disabled[/yellow]")
        console.print("Enable in ~/.nanobot/config.json:")
        console.print('  "agents": { "clawwork": { "enabled": true } }')
        return

    state = _build_clawwork_state(config)
    tracker = state.economic_tracker

    table = Table()
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Signature", state.signature)
    table.add_row("Balance", f"${tracker.get_balance():.2f}")
    table.add_row("Status", tracker.get_survival_status())
    table.add_row("Total Token Cost", f"${tracker.total_token_cost:.2f}")
    table.add_row("Total Work Income", f"${tracker.total_work_income:.2f}")
    table.add_row("Data Path", state.data_path)

    console.print(table)

    console.print("\n[dim]Token Pricing:[/dim]")
    console.print(f"  Input: ${cw.token_pricing.input_price}/1M tokens")
    console.print(f"  Output: ${cw.token_pricing.output_price}/1M tokens")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show nanobot status."""
    from nanobot.config.loader import get_config_path, load_config

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} nanobot Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")

        # Check custom provider first
        custom = config.providers.custom
        if custom.enabled and custom.api_key:
            console.print(f"Custom Provider: [green]✓ {custom.api_base or 'default'}[/green]")
        else:
            console.print("Custom Provider: [dim]disabled[/dim]")

        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


if __name__ == "__main__":
    app()
