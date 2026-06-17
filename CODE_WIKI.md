# OpenClaw Code Wiki

> 项目版本：`2026.5.31`
> 许可证：MIT
> 官方仓库：https://github.com/openclaw/openclaw

---

## 1. 项目概述

**OpenClaw** 是一款**多通道 AI 网关（Multi-channel AI Gateway）**，具备可扩展的消息集成能力。它让用户以统一的方式连接各种 AI 模型提供商（Anthropic Claude、OpenAI、Google Gemini、DeepSeek、Mistral、Ollama……），并通过大量消息通道（Slack、Telegram、Discord、微信、Feishu、IRC、Matrix、iMessage、Web……）与这些模型进行交互。

### 1.1 项目定位（Vision）

- **核心价值**：一个可在你的设备、你的通道、按你的规则运行的 AI 助理
- **运行形态**：CLI 工具 + Node.js gateway 守护进程 + 前端 Control UI（Web）+ 移动端（Android / iOS）
- **关键特性**：
  - 可插拔的**模型提供商**（Provider）系统
  - 可插拔的**消息通道**（Channel）系统
  - 可插拔的**插件**（Plugin）系统，支持扩展能力（技能、内存、MCP、诊断、工具等）
  - 内置 **Agent 运行时**（对话、工具调用、子代理、任务调度）
  - 内置 **多代理/任务流**（task flows、detached task runtime）
  - 完整的**配置 / 权限 / 密钥管理**（secret refs、auth profiles、channel pairing）
  - 第一方 **Codex CLI 集成**（来自 OpenAI Codex 的终端代理）
  - **Control UI**（`ui/`）作为管理面板（浏览器中的 Lit Web Components 应用）
  - **Android 客户端**（`openclaw-android/`）—— 在手机上原生运行 Node + Gateway + WebView UI

### 1.2 仓库构成（Mono-repo 概览）

```
workspace/
├── openclaw.mjs                 # CLI 顶层入口
├── package.json                 # 根 workspace 清单（pnpm workspace）
├── pnpm-workspace.yaml          # workspace 定义
├── src/                         # 核心运行时（TypeScript, ESM）
│   ├── index.ts / entry.ts      # 程序启动点
│   ├── agents/                  # Agent 运行时、模型调度、工具流
│   ├── config/                  # 配置加载、校验、Schema、迁移
│   ├── mcp/                     # MCP（Model Context Protocol）集成
│   ├── secrets/                 # 密钥管理（secret-ref、auth profiles、审计）
│   ├── sessions/                # 会话分类、输入来源、线程绑定
│   ├── pairing/                 # 设备配对与认证
│   ├── process/                 # 子进程、隔离、lanes、容器
│   ├── tasks/                   # 任务流、任务执行器、task flows
│   ├── daemon/                  # systemd / launchd / schtasks 守护
│   ├── memory-host-sdk/         # 内存宿主 SDK（embedding / 检索）
│   ├── realtime-transcription/  # 实时转录（语音通道）
│   ├── bootstrap/               # Node 启动环境、CA 证书
│   ├── compat/                  # 向后兼容
│   ├── test-helpers/            # 测试辅助（不含测试）
│   └── …（更多子模块见第 3 节）
├── ui/                          # Control UI 前端（Lit + Vite）
├── openclaw-android/            # Android 客户端（Kotlin + WebView）
│   ├── android/                 # Android Gradle 项目
│   └── documentation/           # Codex app-server 协议定义（JSON/TS）
├── extensions/                  # 插件目录（90+ 插件包）
│   ├── <provider>-xxx/          # 模型/工具/通道插件
│   └── <channel>-xxx/           # 消息通道插件
├── scripts/                     # 构建、发布、CI、诊断、性能脚本
├── test/                        # 集成/端到端测试
├── docs/                        # 技术文档（Markdown）
├── .github/                     # GitHub Actions / issue 模板
└── Dockerfile / fly.toml        # 容器部署配置
```

---

## 2. 整体架构

OpenClaw 采用**分层 + 插件化**的架构，核心部分在 `src/`，扩展能力全部通过 `extensions/` 下的 npm 包注入。

### 2.1 层次化架构图

```
┌────────────────────────────────────────────────────────────┐
│                        用户界面层                            │
│  ┌───────────────┐   ┌──────────────────┐   ┌───────────┐  │
│  │ Control UI    │   │ Android WebView  │   │ CLI (TUI) │  │
│  │ (ui/)         │   │ (openclaw-android)│   │ (src/cli) │  │
│  └──────┬────────┘   └────────┬─────────┘   └─────┬─────┘  │
└─────────┼─────────────────────┼────────────────────┼────────┘
          │ HTTP / WebSocket    │ HTTP / WebSocket   │ Direct
┌─────────▼─────────────────────▼────────────────────▼────────┐
│                        Gateway 层                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Gateway Runtime (src/agents + src/config + src/mcp)   │ │
│  │  • 路由 / 会话管理 / 事件分发 / 权限                    │ │
│  │  • 插件注册器（Plugin Registry）                       │ │
│  └──────┬──────────────────┬─────────────────┬───────────┘ │
└─────────┼──────────────────┼─────────────────┼─────────────┘
          │ Providers        │ Channels        │ Plugins
┌─────────▼─────────┐ ┌──────▼─────────┐ ┌─────▼────────────┐
│ 模型 / AI 层       │ │ 消息通道层      │ │ 扩展能力层       │
│ Anthropic, OpenAI, │ │ Slack, Telegram,│ │ 内存 (LanceDB)   │
│ Claude, Gemini,    │ │ Discord, IRC,   │ │ 技能 (Skills)    │
│ DeepSeek, Ollama,  │ │ Feishu, iMessage│ │ 诊断 (Prometheus)│
│ vLLM, SGLang,      │ │ WhatsApp, Web…  │ │ MCP Servers      │
│ Mistral, …         │ │ Voice-Call,     │ │ Web Search        │
│ (extensions/*)     │ │ TTS, Realtime…  │ │ (extensions/*)    │
└────────────────────┘ └─────────────────┘ └──────────────────┘
                                                                
┌─────────────────────────────────────────────────────────────┐
│                      基础设施层                               │
│   Secrets / Auth / Config / Sessions / Tasks / Daemon        │
│   (src/secrets, src/config, src/sessions, src/tasks, ...)   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心运行时启动路径

1. 用户执行 `openclaw <command>`（由 `openclaw.mjs` 启动）
2. `src/entry.ts` 处理：
   - 编译缓存（`entry.compile-cache.ts`）
   - 快速版本路径（`entry.version-fast-path.ts`）
   - 进程重启 / 环境配置（`entry.respawn.ts`）
3. `src/cli/run-main.ts` → `src/cli/program/*` 解析命令
4. 子命令 `gateway` 启动 Gateway 守护进程（`src/daemon/*`）
5. Gateway 启动后：
   - 加载配置（`src/config/`）
   - 加载并注册所有插件（`src/agents/runtime-plugins.ts`）
   - 启动 HTTP / WebSocket 服务
   - 监听消息通道事件 → 路由到 Agent 运行时 → 调用 Provider → 返回消息

### 2.3 主要进程与端口

| 进程 / 模块 | 作用 | 默认端口 | 关键文件 |
|---|---|---|---|
| `openclaw gateway` | 主网关（HTTP + WebSocket） | 视配置而定（常为 3000 附近） | `src/daemon/gateway-entrypoint.ts` |
| `openclaw-control-ui`（开发模式） | Control UI 前端 dev server | Vite 默认 | `ui/package.json` |
| `openclaw.mjs`（CLI） | 命令行交互 | N/A | `openclaw.mjs` |
| Android 原生 | 管理 WebView + Node runtime | 内部（通过 assets proxy） | `openclaw-android/android/` |

---

## 3. 主要目录与模块职责

### 3.1 `src/` — 核心运行时（按字母顺序）

| 目录 | 职责 | 关键文件 |
|---|---|---|
| **agents/** | Agent 运行时：模型调度、工具执行、会话管理、子代理、ACPX、Codex 原生任务 | `embedded-agent-runner.*`, `subagent-registry.*`, `model-catalog.*`, `auth-profiles.*`, `bash-tools.*` |
| **bootstrap/** | Node 启动环境、CA 证书准备 | `node-extra-ca-certs.*`, `node-startup-env.ts` |
| **compat/** | 向后兼容（旧配置键、legacy names） | `legacy-names.ts` |
| **config/** | 配置加载 / 验证 / Schema / 迁移 / Channel 能力 | `io.*`, `schema.*`, `channel-configured.*`, `commands.*`, `defaults.*`, `paths.ts`, `talk.ts` |
| **daemon/** | 守护进程（systemd / launchd / schtasks / Windows 服务） | `systemd.*`, `launchd.*`, `schtasks.*`, `service.*`, `gateway-entrypoint.ts` |
| **mcp/** | Model Context Protocol：通道桥接、服务、工具处理器、stdio server | `channel-bridge.*`, `channel-server.*`, `plugin-tools-handlers.*`, `plugin-tools-serve.*` |
| **memory-host-sdk/** | 内存宿主 SDK（embedding / 检索 / dreaming / 多模态） | `engine-qmd.ts`, `engine-storage.ts`, `dreaming.ts`, `multimodal.ts` |
| **pairing/** | 设备配对：二维码、挑战 / 应答、标签、store | `setup-code.*`, `pairing-messages.*`, `allow-from-store-file.*` |
| **process/** | 子进程 / 隔离：exec、lanes、spawn、kill-tree、respawn runner | `exec.*`, `command-queue.*`, `lanes.ts`, `kill-tree.*`, `spawn-utils.*` |
| **realtime-transcription/** | 实时语音转写（ASR）provider 注册与会话 | `provider-registry.ts`, `websocket-session.*` |
| **secrets/** | 密钥管理：secret-ref 解析、auth profiles、审计、通道密钥 | `resolve.*`, `apply.*`, `audit.*`, `runtime-auth-profiles-*.ts`, `channel-secret-*.ts` |
| **sessions/** | 会话：分类（chat-type）、输入来源、线程绑定、发送策略 | `classify-session-kind.ts`, `session-key-*.ts`, `input-provenance.*`, `send-policy.ts` |
| **skills/** | 技能 / tools 接口类型 | `types.ts` |
| **tasks/** | 任务流 / 任务执行器 / detached-task runtime | `task-flow-registry.*`, `task-executor.*`, `detached-task-runtime.*`, `codex-native-subagent-task.ts` |
| **test-helpers/** | 跨包共享的测试辅助（不包含测试本身） | `temp-dir.*`, `network-interfaces.ts`, `ssrf.ts` |
| **（顶层 src/*.ts）** | 启动入口、日志、工具、参数、编译缓存、重启 | `index.ts`, `entry.ts`, `entry.respawn.ts`, `entry.compile-cache.ts`, `entry.version-fast-path.ts`, `runtime.ts`, `logger.ts`, `library.ts` |

### 3.2 `ui/` — Control UI（前端）

- **框架**：[Lit](https://lit.dev/) Web Components + Vite 8 构建
- **样式**：自定义 CSS（`ui/src/styles/*`），聊天、活动、看板、配置、cron、TTS 等独立样式文件
- **国际化（i18n）**：`ui/src/i18n/locales/*`（支持 en / zh-CN / de / es / ja / fr / ko ...），基于 Lit Controller 模式
- **UI 功能模块**（`ui/src/ui/*`）：
  - `chat/` 聊天渲染、附件、TTS、状态指示、历史合并
  - `components/` 弹窗、可拖动分隔、文件预览
  - `controllers/` 业务控制器（agents / channels / config / cron / devices / health / logs / models / sessions / skills …）
  - `views/` 各页面视图（activity / agents / channels / chat / config / cron / dreaming / exec-approval / logs / nodes / overview / sessions / skills / workboard / usage …）
  - `app.ts`、`presenter.ts`、`gateway.ts` 应用骨架与网关客户端
- **测试**：Vitest + Playwright（`vitest.config.ts`、`vitest.node.config.ts`）
- **资源**：`ui/public/` 包含 favicon、manifest、Service Worker（sw.js）

### 3.3 `openclaw-android/` — Android 客户端

```
openclaw-android/
├── android/
│   ├── app/src/main/
│   │   ├── AndroidManifest.xml
│   │   ├── assets/proxy.js, bionic-compat.js, setup-codex.sh
│   │   ├── java/com/codex/mobile/
│   │   │   ├── BootstrapInstaller.kt     # 安装 Linux 环境
│   │   │   ├── CodexForegroundService.kt # 前台服务保活
│   │   │   ├── CodexServerManager.kt     # Node/网关生命周期
│   │   │   └── MainActivity.kt           # WebView 入口
│   │   └── res/                         # 资源
│   └── build.gradle.kts                 # Kotlin 2.1 构建
└── documentation/
    ├── APP_SERVER_DOCUMENTATION.md       # Codex app-server 协议
    └── app-server-schemas/               # JSON + TS schema 目录
```

该子项目提供：
- 在 Android 上的**原生 WebView** 渲染 Control UI
- **Termux-style bootstrap**：在 `$PREFIX` 内安装 sh / apt / dpkg / Node
- **bionic-compat.js**：让 Node 在 Android libc（bionic）下表现为 "linux" 兼容
- **proxy.js**：将 musl 原生二进制的 DNS/TLS 请求桥接到 Android 的网络栈
- `CodexServerManager`：负责下载、安装、启动、重启 OpenClaw 网关

### 3.4 `extensions/` — 插件生态（90+ 包）

每个插件是一个独立的 npm 包，包含：
- `package.json`
- `openclaw.plugin.json`：插件元数据（入口、契约 API、runtime/setup 钩子）
- `index.ts`：注册入口
- `api.ts` / `runtime-api.ts` / `setup-api.ts` / `contract-api.ts` 等：具体实现
- `*.test.ts`：单元/集成测试（可选）

插件按功能大类划分如下（非穷尽）：

#### A. 模型 / Provider 插件（LLM & 文本生成）
- **Anthropic**（Claude）: `extensions/anthropic/`, `extensions/anthropic-vertex/`
- **OpenAI**（ChatGPT / GPT-4o）: `extensions/openai/`
- **Google / Gemini**（Google, Googlechat 等）
- **DeepSeek**: `extensions/deepseek/`
- **Mistral**: `extensions/mistral/`
- **Qwen / Kimi / Moonshot / Groq / Together / Cerebras / NVIDIA / Arcee / GMI / Gradium / 360 / Alibaba / Tencent / BytePlus / Volcengine / Qianfan / SenseAudio …**
- **自托管 / 标准兼容**：
  - `ollama/`（本地 Ollama 服务）
  - `vllm/`、`sglang/`（推理服务）
  - `lmstudio/`
  - `litellm/`、`openrouter/`
  - `chutes/`、`llm-task/`
  - `vercel-ai-gateway/`、`cloudflare-ai-gateway/`
- **Coder 系列**：`kimi-coding/`, `opencode/`, `opencode-go/`, `kilocode/`

#### B. 消息 / 通道 Channel 插件
- **Slack**：`extensions/slack/`
- **Telegram**：`extensions/telegram/`
- **Discord**：`extensions/discord/`
- **Microsoft Teams**：`extensions/msteams/`
- **Feishu / 飞书**：`extensions/feishu/`
- **IRC**：`extensions/irc/`
- **Matrix**：`extensions/matrix/`
- **iMessage**：`extensions/imessage/`
- **WhatsApp**：`extensions/whatsapp/`
- **Signal**：`extensions/signal/`
- **Line**：`extensions/line/`
- **QQ Bot**：`extensions/qqbot/`
- **Zalo**：`extensions/zalo/`
- **Nostr**：`extensions/nostr/`
- **Nextcloud Talk**：`extensions/nextcloud-talk/`
- **Synology Chat**：`extensions/synology-chat/`
- **Mattermost**：`extensions/mattermost/`
- **Google Chat / Meet**：`extensions/googlechat/`, `extensions/google-meet/`
- **Webhooks**：`extensions/webhooks/`
- **SMS**：`extensions/sms/`
- **Admin HTTP RPC**：`extensions/admin-http-rpc/`（程序化管理通道）
- **Voice-Call**：`extensions/voice-call/`（语音通话）
- **ClickClack**：`extensions/clickclack/`（键盘/输入流）
- **QA-Channels**：`extensions/qa-channel/`, `extensions/qa-matrix/`（测试通道）

#### C. 能力 / 工具类插件
- **浏览器工具**：`extensions/browser/`（CDP / 配置 / profiles）
- **Codex 集成**：`extensions/codex/`, `extensions/codex-supervisor/`
- **OpenProse**：`extensions/open-prose/`（写作相关）
- **文件传输**：`extensions/file-transfer/`
- **Canvas**：`extensions/canvas/`
- **Workboard**：`extensions/workboard/`（任务看板）
- **Inworld**：`extensions/inworld/`（角色 AI）
- **Bonjour**：`extensions/bonjour/`（服务发现）
- **OC Path**：`extensions/oc-path/`
- **Copilot-Proxy**：`extensions/copilot-proxy/`
- **Copilot / GitHub Copilot**：`extensions/copilot/`, `extensions/github-copilot/`
- **TokenJuice**：`extensions/tokenjuice/`（tokens 统计/管理）
- **MCP Code Mode**：`extensions/acpx/`（ACP 协议扩展）
- **OpenShell**：`extensions/openshell/`
- **Lobster**：`extensions/lobster/`
- **Tlon**：`extensions/tlon/`

#### D. 多模态（图像 / 视频 / 音乐 / 语音）插件
- **图像生成**：`image-generation-core/`（共享基础），分散在 OpenAI / Anthropic / Mistral 等 provider 中
- **视频生成**：`video-generation-core/`，如 Runway、Novita、Kimi …
- **音乐生成**：`music-generation-providers.live.test.ts` 入口 + 各 provider
- **语音 / TTS / ASR**：
  - `azure-speech/`, `elevenlabs/`, `senseaudio/`, `tts-local-cli/`, `microsoft/` (speech)
  - `deepgram/`（ASR / 实时转写）
- **媒体理解**：`media-understanding-core/`，接入 Groq / Mistral / OpenAI / Minimax / Qwen / DeepSeek 等
- **实时语音**：`realtime-transcription/`（核心）+ provider 插件（Deepgram, OpenAI, Azure, ElevenLabs …）

#### E. 搜索 / 阅读 / 知识
- **Web Search**：`brave/`, `duckduckgo/`, `perplexity/`, `searxng/`, `tavily/`, `firecrawl/`
- **网页提取**：`web-readability/`, `document-extract/`, `firecrawl/`
- **Exa**：`extensions/exa/`
- **Wiki 内存**：`memory-wiki/`

#### F. 内存 / Embedding
- `memory-core/`（内存宿主，基于 shared engine 实现）
- `memory-lancedb/`（LanceDB 向量存储）
- `extensions/...-memory-*`
- embedding provider：HuggingFace, Mistral, OpenAI, Voyage …

#### G. 诊断 / 监控 / 运维
- `diagnostics-otel/`（OpenTelemetry）
- `diagnostics-prometheus/`（Prometheus metrics）
- `qa-lab/`（内部 QA 运行环境）

#### H. 迁移工具
- `migrate-claude/`（从 Claude Code 迁移到 OpenClaw）
- `migrate-hermes/`（从其他助手迁移）

### 3.5 `scripts/` — 构建 / 发布 / 诊断脚本

| 脚本组 | 用途 |
|---|---|
| 入口与启动 | `openclaw.mjs`, `src/entry.ts`, `scripts/run-node.*`, `scripts/entry.compile-cache.*` |
| 构建 | `scripts/build-all.mjs`, `scripts/prepare-git-hooks.mjs`, `scripts/.*.sh`（macOS/Android 打包） |
| 发布 | `scripts/release-*.ts/.mjs`, `scripts/plugin-npm-*.sh/.ts`, `scripts/package-*.sh`, `scripts/*-beta-*.ts` |
| 质量 / 诊断 | `scripts/check-*.mjs`（边界检查 / 废弃 API / 死代码 / import cycle …）, `scripts/deadcode-unused-files.allowlist.mjs` |
| 性能 | `scripts/bench-*.ts`（CLI / gateway 启动耗时 / model）, `scripts/test-cli-startup-bench-budget.mjs` |
| CI / 测试 | `scripts/ci-*.mjs`, `scripts/vitest-*.mjs`, `scripts/test-projects-*.mjs`, `scripts/test-unit-fast-audit.mjs` |
| Docker | `scripts/docker/`, `scripts/build-image.sh`, `Dockerfile` |
| 子目录 | `scripts/e2e/*`（端到端场景）, `scripts/dev/*`（开发调试）, `scripts/lib/*`（共享库）, `scripts/clawdock/*`（clawdock 工具） |
| 协议生成 | `scripts/protocol-gen.ts`, `scripts/protocol-gen-swift.ts` |
| 审计 / 安全 | `scripts/.*secrets*`, `scripts/audit-seams.mjs` |

### 3.6 `docs/` — 文档

- `docs/agent-runtime-architecture.md`：Agent 运行时架构
- `docs/auth-credential-semantics.md`：鉴权凭证语义
- `docs/date-time.md`：时间日期处理规范
- `docs/logging.md`：日志规范
- `docs/network.md`：网络 / 代理 / SSRF
- `docs/tts.md`, `docs/tts-and-voice.md`：语音/TTS
- `docs/openclaw-agent-runtime.md`：OpenClaw Agent 运行时规范
- `docs/perplexity.md`, `docs/brave-search.md`：特定 provider 文档
- `docs/vps.md`：VPS 部署指南
- `docs/AGENTS.md`：Agent 开发指引
- `docs/index.html`：文档站点入口

---

## 4. 关键类与函数说明

### 4.1 入口与启动

| 位置 | 符号 | 作用 |
|---|---|---|
| `openclaw.mjs` | — | npm bin 入口，ESM 包装 |
| `src/entry.ts` | `parseCliProfileArgs()`, `applyCliProfileEnv()`, `buildCliRespawnPlan()`, `runCliRespawnPlan()` | 命令行参数解析、编译缓存控制、重启子进程 |
| `src/entry.compile-cache.ts` | `enableOpenClawCompileCache()`, `respawnWithoutOpenClawCompileCacheIfNeeded()` | 按需启用编译缓存加速冷启动 |
| `src/entry.respawn.ts` | `buildCliRespawnPlan()`, `runCliRespawnPlan()` | 跨平台进程重启 |
| `src/entry.version-fast-path.ts` | `tryHandleRootVersionFastPath()` | 快速响应 `--version`（避免完整模块加载） |
| `src/library.ts` | `applyTemplate()`, `loadConfig()`, `runExec()`, `saveSessionStore()`, `monitorWebChannel()`, … | 作为库消费时的稳定 API 表面 |

### 4.2 配置系统

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/config/io.ts` | `loadConfig()`, `io.*`（读写/快照/迁移） | 配置 I/O |
| `src/config/schema.*` | zod schemas + baseline generator | Schema 校验 |
| `src/config/channel-configured.ts` | channel 能力 / 配置聚合 | 通道配置合并 |
| `src/config/commands.ts` | 子命令（cron / talk / doctor …）的参数建模 | CLI 子命令 schema |
| `src/config/defaults.ts` | `defaults.*` | 默认值 |
| `src/config/paths.ts` | 配置目录 / 状态目录解析 | 跨平台路径 |
| `src/config/talk.ts` | `talk.*`（"对话"子命令） | 交互式对话配置 |
| `src/config/group-policy.ts` | 组策略模型 | 会话/通道分组 |
| `scripts/generate-base-config-schema.ts` | schema 生成器（构建期） | 生成 JSON schema |

### 4.3 Agent 运行时

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/agents/embedded-agent-runner.*` | 核心 Agent runner，处理工具调用、streaming、会话 | Agent 主循环 |
| `src/agents/model-catalog.*` | 统一的模型目录（provider → 模型） | 模型发现 |
| `src/agents/auth-profiles.*` | auth profile 加载、冷却、冲突解决 | 身份/密钥管理 |
| `src/agents/bash-tools.*` | 本地 shell 工具执行 | 本地命令 |
| `src/agents/subagent-registry.*` | 子代理生命周期与调度 | 子 Agent 管理 |
| `src/agents/subagent-spawn.*` | `subagent-spawn`：子进程形式 spawn 子 agent | 子 Agent 启动 |
| `src/agents/agent-tool-definition-adapter.*`, `agent-tools.*` | 工具定义与调用（参数 schema、权限、中止） | Tool use |
| `src/agents/workspace-run.*` | workspace（工作目录）会话运行 | 工作区运行 |
| `src/agents/provider-stream.*` | provider streaming（SSE / WebSocket） | 模型流式输出 |
| `src/agents/openclaw-tools.sessions.*`, `…image-generation.*`, `…video-generation.*` | OpenClaw 内置工具（session 管理 / 图像 / 视频） | 内部工具 |
| `src/agents/runtime-plugins.ts` | 插件注册器 | 插件系统主入口 |

### 4.4 通道与消息

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/agents/channel-entry-contract.*` | channel 接口契约（入站/出站/配置/会话） | Channel API |
| `extensions/<channel>/channel-plugin-api.ts` | 各通道插件的实现 | Slack/Telegram/... |
| `extensions/<channel>/contract-api.ts` | 各通道暴露的内部契约 | 通道-核心交互 |
| `extensions/<channel>/secret-contract-api.ts` | 通道的密钥管理 | 鉴权 |
| `src/sessions/classify-session-kind.ts` | 会话分类（chat vs other） | 路由策略 |
| `src/sessions/input-provenance.ts` | 输入来源记录（审计） | 消息溯源 |

### 4.5 密钥与安全

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/secrets/runtime.ts` | secrets runtime 入口 | 密钥解析主路径 |
| `src/secrets/resolve.ts` | `resolve*` 系列函数 | 解析 secret-ref |
| `src/secrets/apply.ts` | 配置中应用密钥 | 写回/替换 |
| `src/secrets/audit.ts` | 审计：谁引用了哪些 secret | 安全审计 |
| `src/secrets/auth-profiles-scan.ts` | auth profiles 扫描 | 凭据发现 |
| `src/agents/auth-profiles.ts` | 运行期 auth profile 选择器 | 模型侧鉴权 |
| `src/pairing/*` | 设备配对：挑战 / 签名 / QR | 信任模型 |

### 4.6 任务 / 调度

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/tasks/task-flow-registry.*` | task flow 注册与执行 | 工作流 |
| `src/tasks/task-executor.*` | 任务执行器（并发/重试/状态） | 任务引擎 |
| `src/tasks/detached-task-runtime.*` | 分离式任务 runtime | 长时间运行的任务 |
| `src/tasks/codex-native-subagent-task.ts` | Codex 原生子 Agent 任务 | 与 Codex 集成 |
| `src/daemon/*` | systemd / launchd / schtasks / Windows 服务 | 后台驻留 |
| `src/config/commands.ts` (cron) | `cron` 子命令 schema | 定时任务 |

### 4.7 Gateway / HTTP / WebSocket

| 位置 | 符号 | 作用 |
|---|---|---|
| `src/daemon/gateway-entrypoint.ts` | gateway 启动 | HTTP / WebSocket server |
| `ui/src/ui/gateway.ts` | UI 侧网关客户端 | 前端 API 层 |
| `src/agents/runtime-plugins.ts` | 插件注册到 gateway | 运行时扩展 |

### 4.8 UI 关键文件

| 位置 | 符号 | 作用 |
|---|---|---|
| `ui/src/ui/app.ts` | 顶层 App Lit 组件 | 路由与骨架 |
| `ui/src/ui/presenter.ts` | 应用状态与 presenter（MVC-ish） | 状态管理 |
| `ui/src/ui/gateway.ts` | gateway 的 WebSocket/HTTP 客户端 | 数据层 |
| `ui/src/ui/chat/*` | 聊天 UI（消息、composer、工具卡片、TTS、附件…） | 聊天视图 |
| `ui/src/ui/controllers/*` | 各业务域的控制器（agents / channels / config / cron / devices / logs / models …） | 控制器层 |
| `ui/src/i18n/locales/*` | 本地化资源 | 国际化 |
| `ui/src/styles/*` | 样式文件 | CSS |

### 4.9 Android 关键类

| 文件 | 类/函数 | 作用 |
|---|---|---|
| `openclaw-android/android/app/src/main/java/com/codex/mobile/MainActivity.kt` | `MainActivity` | WebView 容器，入口 Activity |
| `.../CodexServerManager.kt` | `CodexServerManager` | Node.js 进程 + gateway 生命周期管理 |
| `.../CodexForegroundService.kt` | `CodexForegroundService` | 前台服务，保活 |
| `.../BootstrapInstaller.kt` | `BootstrapInstaller` | Termux-style Linux userland 提取与安装 |
| `assets/proxy.js` | — | musl 二进制的 DNS/TLS 桥接代理 |
| `assets/bionic-compat.js` | — | 让 Node 在 Android libc 下表现为 "linux" 平台 |

---

## 5. 依赖关系

### 5.1 主要外部依赖（根 `package.json`）

| 依赖组 | 示例 |
|---|---|
| **构建工具** | TypeScript / Vite / tsdown / pnpm / Gradle（Android） |
| **测试** | Vitest / Playwright / tsx |
| **类型与校验** | Zod（schema）、TypeScript 5.x、oxlint（lint 加速） |
| **运行时（Node）** | Node.js 20+（建议 22 LTS） |
| **加密** | `@noble/ed25519`（pairing） |
| **UI** | Lit 3.x、Vite 8.x、highlight.js、marked、markdown-it、DOMPurify、@create-markdown/preview |
| **HTTP / WebSocket** | 标准 Node `http`、`ws` 或内置实现（分散在 extensions） |
| **语音 / 媒体** | 各 provider SDK（Azure Speech、ElevenLabs、Deepgram …见 `extensions/*`） |
| **向量 / 搜索** | `LanceDB`、SQLite（via sqlite-vec 等） |
| **外部 CLI** | `git`、`curl`、`docker`（按需） |
| **Android** | Kotlin 2.1、Android Gradle Plugin、WebView、Termux bootstrap |

### 5.2 内部依赖方向（自上而下的合法依赖）

```
ui/ ───► src/index.ts (library.ts, gateway RPC)
            ▲
            │
extensions/* ──► src/agents/*, src/config/*, src/secrets/*, src/mcp/*
                    ▲
                    │
                 src/* 内部（可互相引用，但通过 contract-api 约束边界）
```

- `ui/` 只通过 HTTP/WebSocket 与网关通信（不直接 import src/）
- `extensions/*` 通过公开的 `plugin-sdk` 子路径（见 `package.json` exports）与核心交互
- `openclaw-android/` 完全独立，仅通过 HTTP 与运行在本机的 gateway 通信

### 5.3 插件/核心边界

- 插件不可直接引用 `src/` 内部路径（通过 `scripts/check-extension-wildcard-reexports.mjs` 等脚本强制约束）
- 插件依赖一个稳定的 `openclaw` 核心包（通过 `package.json` 的 workspace 依赖与 npm 发布）
- 插件暴露以下几类 API 文件（约定俗成）：
  - `api.ts` / `index.ts`：公共导出
  - `contract-api.ts`：与核心交互的契约（接口/类型）
  - `runtime-api.ts`：运行期钩子（启动后注入）
  - `setup-api.ts` / `setup-entry.ts`：setup 期钩子（`openclaw setup`）
  - `channel-plugin-api.ts`：通道插件的内部 API
  - `secret-contract-api.ts`：密钥相关契约
  - `doctor-contract-api.ts`：doctor/自检契约

---

## 6. 项目运行方式

### 6.1 环境要求

| 项目 | 要求 |
|---|---|
| Node.js | ≥ 20（推荐 22 LTS） |
| 包管理器 | `pnpm`（由根 `pnpm-workspace.yaml` 定义） |
| 操作系统 | Linux / macOS / Windows（通过 WSL 或原生）/ Android（7.0+ ARM64） |
| Android（原生） | Android 7.0+（API 24）、ARM64、WebView、可用存储 ≥ 500MB |
| 浏览器（UI） | 现代浏览器（Chrome / Edge / Firefox / Safari 最近两个大版本） |

### 6.2 安装与运行（开发者模式）

```bash
# 1) 克隆
git clone https://github.com/openclaw/openclaw.git
cd openclaw

# 2) 安装依赖
pnpm install

# 3) 构建核心
pnpm run build          # 或 scripts/build-all.mjs

# 4) 首次运行（配置向导）
node openclaw.mjs setup

# 5) 启动 gateway
node openclaw.mjs gateway start --foreground

# 6) 启动 Control UI（开发模式）
cd ui
pnpm install
pnpm run dev            # Vite dev server

# 7) 浏览器访问 Control UI
# 打开 http://127.0.0.1:<vite-port> 连接到 gateway
```

### 6.3 常用 CLI 子命令（概念）

```bash
openclaw --help                      # 查看所有命令
openclaw setup                       # 初次设置向导
openclaw doctor                      # 自检与修复
openclaw gateway start               # 启动网关（可加 --foreground）
openclaw gateway status
openclaw gateway stop
openclaw talk "你好"                 # 直接运行一次性对话
openclaw chat                        # 交互聊天
openclaw cron list | add | delete    # 定时任务
openclaw secrets audit               # 密钥审计
openclaw nodes inspect               # 多节点/远程节点
openclaw agents list / inspect       # 代理检查
openclaw channels list / inspect     # 通道检查
openclaw models list                 # 模型列表
openclaw login <provider>            # provider OAuth / API key 登录
```

具体命令与参数以实际 `openclaw --help` 输出为准。

### 6.4 Android 构建

```bash
cd openclaw-android/android
# 需先安装 Android SDK + JDK 17+
./gradlew assembleDebug
# 产物：app/build/outputs/apk/debug/app-debug.apk

# 安装并启动
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.codex.mobile/.MainActivity
```

### 6.5 Docker / 容器

```bash
# 使用根 Dockerfile
docker build -t openclaw .
docker run -p 3000:3000 -v ~/.openclaw:/root/.openclaw openclaw gateway start --foreground
```

也可参考 `fly.toml`（Fly.io 部署配置）、`deploy/fly.private.toml`。

### 6.6 测试

```bash
# 单元测试（核心）
pnpm test --filter openclaw

# UI 测试
cd ui && pnpm test

# 扩展（插件）测试
pnpm test --filter ./extensions/*

# E2E（见 scripts/e2e/*、test/*、scripts/test-projects.mjs）
node scripts/test-projects.mjs
```

主要测试框架：**Vitest**（运行时 / UI 通用）+ **Playwright**（浏览器 / E2E）。

---

## 7. 核心概念与术语

| 术语 | 含义 |
|---|---|
| **Provider** | AI 模型 / 工具服务提供方（OpenAI、Anthropic、Ollama …） |
| **Channel** | 消息通道（Slack、Telegram、Web UI …） |
| **Plugin** | npm 形式的扩展包（在 `extensions/` 下或外部发布） |
| **Agent** | 一次 "对话/任务" 实例：包含上下文、工具、模型、策略 |
| **Session / Thread** | 一次独立的对话上下文（对应 channel 线程） |
| **Auth Profile** | 一组 provider 凭证（API key / OAuth token …） |
| **Secret-ref** | 对密钥的引用（通过 `secrets/runtime` 解析成实际值） |
| **Pairing** | 设备与网关建立信任（用于 WebView / 远程 CLI / 手机端） |
| **MCP** | Model Context Protocol，外部工具/上下文服务接入标准 |
| **ACPX** | 代码模式下的 Agent Control Protocol 扩展（面向工具/任务流） |
| **Task Flow** | 结构化任务流（对应 `src/tasks/*`），可持久化、可审计 |
| **Detached Task** | 长生命周期任务，可跨 CLI 调用保持运行状态 |
| **Control UI** | 浏览器端管理面板（`ui/`） |
| **Codex CLI** | OpenAI Codex 的终端代理（OpenClaw 作为上层/并列运行时） |
| **Runtime** | 运行期（区别于 setup / build 期） |

---

## 8. 开发与贡献流程（摘要）

1. **新建分支**，实现功能 / 修复
2. **运行测试**：`pnpm -w test` 或针对具体包 `pnpm --filter <pkg> test`
3. **lint / 格式**：项目使用 oxlint / 内部 `scripts/check-*.mjs` 等一套边界检查脚本
4. **构建产物**：`pnpm run build`（核心）、`pnpm -C ui build`（前端）
5. **提交 & PR**：遵循 `.github/pull_request_template.md`
6. **发布**：维护者运行 `scripts/release-*.ts` / `scripts/plugin-*.sh` 等发布流程（有 changelog、有版本升级脚本）

详细规则见：
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`docs/AGENTS.md`](docs/AGENTS.md)
- [`VISION.md`](VISION.md)

---

## 9. 常见问题与排查路径

| 问题 | 排查路径 |
|---|---|
| gateway 无法启动 | 检查 `~/.openclaw/config.yaml` 权限、端口占用、`openclaw doctor --fix` |
| provider 调用失败 | `openclaw models list`；检查 `auth-profiles`、API key / OAuth；`scripts/debug-claude-usage.ts` 等诊断脚本 |
| UI 无法连接 gateway | 检查浏览器控制台 / WS 连接；确认 `control-ui-origins` 配置；手机端检查 `proxy.js` |
| 插件未生效 | 检查 `openclaw plugin list`；`scripts/check-plugin-sdk-subpath-exports.mjs` 验证子路径导出 |
| 冷启动慢 | `scripts/bench-cli-startup.ts` 抽样；启用 compile-cache；`entry.compile-cache.ts` |
| Android 闪退 | `adb logcat | grep -i codex`；检查 targetSdk；确保 `assets/setup-codex.sh` 下载成功 |
| 内存/性能 | `scripts/bench-gateway-startup.ts`, `scripts/bench-gateway-restart.ts`, `src/agents/cache-trace.ts` |

---

## 10. 进一步阅读

- 项目根：[`README.md`](README.md)、[`VISION.md`](VISION.md)、[`CONTRIBUTING.md`](CONTRIBUTING.md)、[`SECURITY.md`](SECURITY.md)
- Agent 运行时：[`docs/agent-runtime-architecture.md`](docs/agent-runtime-architecture.md)、[`docs/openclaw-agent-runtime.md`](docs/openclaw-agent-runtime.md)
- 网络与安全：[`docs/network.md`](docs/network.md)、[`docs/auth-credential-semantics.md`](docs/auth-credential-semantics.md)
- 日志与时间：[`docs/logging.md`](docs/logging.md)、[`docs/date-time.md`](docs/date-time.md)
- 语音 / TTS：[`docs/tts.md`](docs/tts.md)
- 插件系统：[`docs/tools/plugin.md`](docs/tools/plugin.md)、`extensions/AGENTS.md`
- Android 协议：`openclaw-android/documentation/APP_SERVER_DOCUMENTATION.md`（Codex app-server 协议参考）

---

> 本 Wiki 为代码仓库的结构化导读，**不是替代源码阅读**，而是帮助你在正确的目录下快速定位关注点。遇到未覆盖的细节，请从相关源文件（尤其是 `*.test.ts`）和 `docs/` 下的 Markdown 入手。
