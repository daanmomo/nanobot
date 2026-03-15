---
name: skill-creator
description: Create or update AgentSkills. Use when designing, structuring, or packaging skills with scripts, references, and assets.
---

# 技能创建器

本技能提供创建有效技能的指导。

## 关于技能

技能是模块化、自包含的包，通过提供专业知识、工作流和工具来扩展 agent 的能力。可将它们视为特定领域或任务的「入门指南」——它们将 agent 从通用 agent 转变为具备程序性知识的专业 agent，这些知识是任何模型都无法完全掌握的。

### 技能提供什么

1. 专业工作流 - 特定领域的多步骤流程
2. 工具集成 - 处理特定文件格式或 API 的说明
3. 领域专长 - 公司特定知识、模式、业务逻辑
4. 捆绑资源 - 用于复杂和重复任务的脚本、参考和资产

## 核心原则

### 简洁至上

上下文窗口是共享资源。技能与 agent 所需的一切共享上下文窗口：系统提示、对话历史、其他技能的元数据以及实际用户请求。

**默认假设：agent 已经非常聪明。** 只添加 agent 尚不具备的上下文。质疑每条信息：「agent 真的需要这个解释吗？」以及「这段文字是否值得其 token 成本？」

优先使用简洁示例而非冗长解释。

### 设置适当的自由度

根据任务的脆弱性和可变性匹配具体程度：

**高自由度（基于文本的指令）**：当多种方法都有效、决策依赖上下文或启发式指导方法时使用。

**中自由度（带参数的伪代码或脚本）**：当存在首选模式、允许一定变化或配置影响行为时使用。

**低自由度（具体脚本、少量参数）**：当操作脆弱易错、一致性至关重要或必须遵循特定顺序时使用。

将 agent 想象为探索路径：狭窄的悬崖桥需要具体护栏（低自由度），而开阔田野允许多条路线（高自由度）。

### 技能结构

每个技能由必需的 SKILL.md 文件和可选的捆绑资源组成：

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

#### SKILL.md（必需）

每个 SKILL.md 包含：

- **Frontmatter**（YAML）：包含 `name` 和 `description` 字段。这些是 agent 用于判断何时使用技能时读取的唯一字段，因此清晰全面地描述技能是什么以及何时使用非常重要。
- **Body**（Markdown）：使用技能的指令和指导。仅在技能触发后加载（如有）。

#### 捆绑资源（可选）

##### 脚本（`scripts/`）

用于需要确定性可靠性或反复重写的任务的可执行代码（Python/Bash 等）。

- **何时包含**：当同一代码被反复重写或需要确定性可靠性时
- **示例**：`scripts/rotate_pdf.py` 用于 PDF 旋转任务
- **优势**：Token 高效、确定性、可不加载到上下文即可执行
- **注意**：脚本可能仍需被 agent 读取以进行补丁或环境特定调整

##### 参考（`references/`）

在需要时加载到上下文中以指导 agent 流程和思考的文档和参考材料。

- **何时包含**：agent 工作时应参考的文档
- **示例**：`references/finance.md` 财务模式、`references/mnda.md` 公司 NDA 模板、`references/policies.md` 公司政策、`references/api_docs.md` API 规范
- **用例**：数据库模式、API 文档、领域知识、公司政策、详细工作流指南
- **优势**：保持 SKILL.md 精简，仅在 agent 确定需要时加载
- **最佳实践**：若文件较大（>10k 词），在 SKILL.md 中包含 grep 搜索模式
- **避免重复**：信息应只存在于 SKILL.md 或参考文件中，不要两者都有。除非是技能核心，否则详细信息优先放在参考文件中——这样既保持 SKILL.md 精简，又使信息可发现而不占用上下文窗口。SKILL.md 中只保留必要的程序性指令和工作流指导；将详细参考材料、模式和示例移至参考文件。

##### 资产（`assets/`）

不用于加载到上下文的文件，而是用于 agent 产生的输出中。

- **何时包含**：技能需要用于最终输出的文件时
- **示例**：`assets/logo.png` 品牌资产、`assets/slides.pptx` PowerPoint 模板、`assets/frontend-template/` HTML/React 样板、`assets/font.ttf` 字体
- **用例**：模板、图片、图标、样板代码、字体、被复制或修改的示例文档
- **优势**：将输出资源与文档分离，使 agent 可使用文件而无需加载到上下文

#### 技能中不应包含的内容

技能应只包含直接支持其功能的必要文件。请勿创建多余的文档或辅助文件，包括：

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md
- 等

技能应只包含 AI agent 完成手头工作所需的信息。不应包含关于创建过程的辅助上下文、安装和测试流程、面向用户的文档等。创建额外文档文件只会增加混乱。

### 渐进式披露设计原则

技能使用三级加载系统高效管理上下文：

1. **元数据（name + description）** - 始终在上下文中（约 100 词）
2. **SKILL.md body** - 技能触发时（<5k 词）
3. **捆绑资源** - agent 需要时（无限制，因为脚本可不读入上下文窗口即可执行）

#### 渐进式披露模式

将 SKILL.md body 保持在必要内容且不超过 500 行以最小化上下文膨胀。接近此限制时将内容拆分到单独文件。拆分内容到其他文件时，务必从 SKILL.md 引用并清楚描述何时读取，以确保技能读者知道它们存在以及何时使用。

**关键原则**：当技能支持多种变体、框架或选项时，SKILL.md 中只保留核心工作流和选择指导。将变体特定细节（模式、示例、配置）移至单独参考文件。

**模式 1：带参考的高级指南**

```markdown
# PDF Processing

## Quick start

Extract text with pdfplumber:
[code example]

## Advanced features

- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

agent 仅在需要时加载 FORMS.md、REFERENCE.md 或 EXAMPLES.md。

**模式 2：按领域组织**

For Skills with multiple domains, organize content by domain to avoid loading irrelevant context:

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

当用户询问销售指标时，agent 仅读取 sales.md。

类似地，对于支持多种框架或变体的技能，按变体组织：

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

当用户选择 AWS 时，agent 仅读取 aws.md。

**模式 3：条件性细节**

展示基本内容，链接到高级内容：

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

agent 仅在用户需要这些功能时读取 REDLINING.md 或 OOXML.md。

**重要指南：**

- **避免深层嵌套引用** - 保持引用仅从 SKILL.md 深入一层。所有参考文件应从 SKILL.md 直接链接。
- **结构化较长参考文件** - 对于超过 100 行的文件，在顶部包含目录以让 agent 预览时看到完整范围。

## 技能创建流程

技能创建包含以下步骤：

1. 通过具体示例理解技能
2. 规划可重复使用的技能内容（脚本、参考、资产）
3. 初始化技能（运行 init_skill.py）
4. 编辑技能（实现资源并编写 SKILL.md）
5. 打包技能（运行 package_skill.py）
6. 根据实际使用迭代

按顺序执行这些步骤，仅在明确不适用时跳过。

### 技能命名

- 仅使用小写字母、数字和连字符；将用户提供的标题规范化为 hyphen-case（如 "Plan Mode" -> `plan-mode`）。
- 生成名称时，生成不超过 64 个字符的名称（字母、数字、连字符）。
- 优先使用描述动作的简短动词短语。
- 当有助于清晰或触发时按工具命名空间（如 `gh-address-comments`、`linear-address-issue`）。
- 技能文件夹名称与技能名称完全一致。

### 步骤 1：通过具体示例理解技能

仅在技能的用法模式已明确理解时跳过此步骤。即使处理现有技能，此步骤仍有价值。

要创建有效技能，需清楚理解技能将如何被使用的具体示例。此理解可来自直接用户示例或经用户反馈验证的生成示例。

例如，构建 image-editor 技能时，相关问题包括：

- "image-editor 技能应支持哪些功能？编辑、旋转，还有其他吗？"
- "能否举例说明此技能如何被使用？"
- "我能想象用户会问'移除这张图片的红眼'或'旋转这张图片'。你还能想象其他用法吗？"
- "用户会说什么来触发此技能？"

为避免让用户感到困扰，避免在单条消息中问太多问题。从最重要的问题开始，按需跟进以提高效果。

当对技能应支持的功能有清晰认识时，结束此步骤。

### 步骤 2：规划可重复使用的技能内容

要将具体示例转化为有效技能，通过以下方式分析每个示例：

1. 考虑如何从头执行示例
2. 确定在执行这些工作流时哪些脚本、参考和资产会有帮助

示例：构建 `pdf-editor` 技能处理"帮我旋转这个 PDF"等查询时，分析显示：

1. 旋转 PDF 每次都需要重写相同代码
2. 在技能中存储 `scripts/rotate_pdf.py` 脚本会有帮助

示例：设计 `frontend-webapp-builder` 技能处理"帮我建个待办应用"或"帮我建个仪表盘追踪步数"时，分析显示：

1. 编写前端 webapp 每次都需要相同的样板 HTML/React
2. 在技能中存储包含样板 HTML/React 项目文件的 `assets/hello-world/` 模板会有帮助

示例：构建 `big-query` 技能处理"今天有多少用户登录？"时，分析显示：

1. 查询 BigQuery 每次都需要重新发现表模式和关系
2. 在技能中存储记录表模式的 `references/schema.md` 文件会有帮助

要确定技能内容，分析每个具体示例以创建要包含的可重复使用资源列表：脚本、参考和资产。

### 步骤 3：初始化技能

此时应实际创建技能。

仅在正在开发的技能已存在且需要迭代或打包时跳过此步骤。此时继续下一步。

从头创建新技能时，始终运行 `init_skill.py` 脚本。该脚本会便利地生成新的模板技能目录，自动包含技能所需的一切，使技能创建过程更高效可靠。

用法：

```bash
scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

Examples:

```bash
scripts/init_skill.py my-skill --path skills/public
scripts/init_skill.py my-skill --path skills/public --resources scripts,references
scripts/init_skill.py my-skill --path skills/public --resources scripts --examples
```

脚本会：

- 在指定路径创建技能目录
- 生成带正确 frontmatter 和 TODO 占位符的 SKILL.md 模板
- 根据 `--resources` 可选创建资源目录
- 当设置 `--examples` 时可选添加示例文件

初始化后，根据需要自定义 SKILL.md 并添加资源。若使用了 `--examples`，替换或删除占位符文件。

### 步骤 4：编辑技能

编辑（新生成或现有）技能时，记住技能是为另一个 agent 实例创建的。包含对 agent 有益且非显而易见的信息。考虑哪些程序性知识、领域特定细节或可重复使用资产能帮助另一个 agent 实例更有效地执行这些任务。

#### 学习经过验证的设计模式

根据技能需求参考以下指南：

- **多步骤流程**：参见 references/workflows.md 了解顺序工作流和条件逻辑
- **特定输出格式或质量标准**：参见 references/output-patterns.md 了解模板和示例模式

这些文件包含有效技能设计的既定最佳实践。

#### 从可重复使用的技能内容开始

开始实现时，从上述已识别的可重复使用资源开始：`scripts/`、`references/` 和 `assets/` 文件。注意此步骤可能需要用户输入。例如，实现 `brand-guidelines` 技能时，用户可能需要提供品牌资产或模板存储在 `assets/` 中，或文档存储在 `references/` 中。

添加的脚本必须通过实际运行进行测试，确保无 bug 且输出符合预期。若有多个类似脚本，仅需测试代表性样本即可确保它们都能工作，同时平衡完成时间。

若使用了 `--examples`，删除技能不需要的任何占位符文件。仅创建实际需要的资源目录。

#### 更新 SKILL.md

**写作指南**：始终使用祈使/不定式形式。

##### Frontmatter

使用 `name` 和 `description` 编写 YAML frontmatter：

- `name`：技能名称
- `description`：这是技能的主要触发机制，帮助 agent 理解何时使用技能。
  - 包含技能做什么以及何时使用的具体触发/上下文。
  - 在此处包含所有「何时使用」信息——不要在 body 中。body 仅在触发后加载，因此 body 中的「何时使用此技能」部分对 agent 无帮助。
  - `docx` 技能示例描述："全面的文档创建、编辑和分析，支持修订追踪、批注、格式保留和文本提取。当 agent 需要处理专业文档（.docx 文件）时使用：(1) 创建新文档，(2) 修改或编辑内容，(3) 处理修订追踪，(4) 添加批注，或任何其他文档任务"

在 YAML frontmatter 中不要包含任何其他字段。

##### Body

编写使用技能及其捆绑资源的指令。

### 步骤 5：打包技能

技能开发完成后，必须打包成可分发的 .skill 文件供用户使用。打包过程会先自动验证技能以确保满足所有要求：

```bash
scripts/package_skill.py <path/to/skill-folder>
```

Optional output directory specification:

```bash
scripts/package_skill.py <path/to/skill-folder> ./dist
```

打包脚本会：

1. **验证**技能，自动检查：

   - YAML frontmatter 格式和必需字段
   - 技能命名约定和目录结构
   - 描述完整性和质量
   - 文件组织和资源引用

2. **打包**若验证通过，创建以技能命名的 .skill 文件（如 `my-skill.skill`），包含所有文件并保持正确的分发目录结构。.skill 文件是带 .skill 扩展名的 zip 文件。

若验证失败，脚本会报告错误并退出而不创建包。修复所有验证错误后重新运行打包命令。

### 步骤 6：迭代

测试技能后，用户可能会请求改进。这通常发生在使用技能后不久，带着技能表现的新鲜上下文。

**迭代工作流：**

1. 在实际任务中使用技能
2. 注意困难或低效
3. 确定 SKILL.md 或捆绑资源应如何更新
4. 实施更改并再次测试
