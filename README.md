# Execute Agent

Execute Agent 是一个智能代码执行助手，基于 LangChain 和 LangGraph 构建，能够理解自然语言指令并安全地执行代码相关任务。该代理集成了丰富的工具集，支持文件操作、代码搜索、终端命令执行、网络搜索等功能，同时内置了严格的安全机制来防止意外操作。

## 主要功能

### 智能任务管理
- 自动将复杂任务拆解为多个独立的子任务
- **状态持久化**: 运行时会自动在 `data/` 目录下生成 `todos.json` 文件，用于持久化存储任务列表和状态（注：`data/` 目录默认被 git 忽略）。
- 支持任务状态跟踪和更新

### 安全文件操作
- **文件读取**: 安全读取文件内容，支持 UTF-8 编码
- **文件写入**: 集成路径安全检查，防止写入关键目录
- **文件编辑**: 精确匹配并替换指定字符串
- **文件删除**: 严格的安全检查，防止误删核心文件

### 目录与文件搜索
- **目录列表**: 列出指定目录内容，支持递归模式
- **文件搜索**: 根据 glob 模式搜索文件
- **代码库搜索**: 基于关键词搜索整个代码库
- **高级文本搜索**: 支持正则表达式和语义搜索（使用本地向量索引，缓存存储于 `.semantic_cache/`）

### 系统命令执行
- 执行系统命令并捕获输出
- 内置危险命令黑名单（rm、mv、dd、shutdown、sudo 等）
- 工作目录限制在项目根目录内
- 支持超时控制和后台执行

### 代码质量检查
- 集成 pylint、flake8、mypy 等代码检查工具
- 自动解析错误信息并提供详细统计

### 网络与外部集成
- **网络搜索**: 集成博查 (Bocha) API 进行联网搜索
- **MCP 客户端**: 支持 Context7 和 Gitee 的 MCP 服务
- **Git 集成**: 支持 Gitee 仓库操作

## 安装方法

1. 克隆项目仓库：
   ```bash
   git clone <repository-url>
   cd execute-agent
   ```

2. 创建虚拟环境（推荐）：
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 配置说明

本项目使用 `config.json` 进行配置。由于包含敏感信息（API 密钥），`config.json` 默认被 git 忽略。

1. 复制默认配置文件：
   ```bash
   cp config.default.json config.json
   ```

2. 编辑 `config.json` 文件，填入以下配置：

   **模型配置**（支持针对不同任务指定不同模型）：
   - `PLAN_LLM_MODEL`: 规划任务使用的模型（如 `qwen-plus`）
   - `SUMMARY_LLM_MODEL`: 总结任务使用的模型
   - `ANALYSIS_LLM_MODEL`: 分析任务使用的模型
   - `CODE_LLM_MODEL`: 代码生成任务使用的模型（建议使用 coding 能力强的模型）

   **API 密钥配置**：
   - `LLM_API_KEY`: LLM 服务商的 API 密钥（必填）
   - `LLM_API_BASE`: LLM API 基础 URL（默认：`https://dashscope.aliyuncs.com/compatible-mode/v1`）
   - `CONTEXT7_API_KEY`: Context7 MCP 服务 API 密钥（可选）
   - `BOCHA_API_KEY`: 博查搜索 API 密钥（可选，用于联网搜索）
   - `GITEE_TOKEN`: Gitee 访问令牌（可选，用于 Gitee 操作）

   **系统参数**：
   - `RECURSION_LIMIT`: 最大递归深度（默认 1000）
   - `SUMMARY_MAX_LENGTH`: 摘要最大长度（默认 4000）
   - `SUMMARY_THRESHOLD`: 触发摘要的上下文长度阈值（默认 10000）

   或者通过**环境变量**设置上述任何配置项（环境变量优先级高于 `config.json`）。

## 使用说明

### 基本用法
```bash
python main.py "你的指令"
```

### 参数选项
- `-p`, `--print`: **打印模式**。仅输出建议的操作，不实际执行文件修改或命令。用于预览。
- `--force`: **强制模式**。强制执行操作，跳过确认，并可在打印模式下强制写入。
- `--output-format {text,json,stream-json}`: 指定输出格式（默认为 text）。
- `--prompt-file <file_path>`: 从文件读取提示词，读取后自动删除该文件。
- `--stream-partial-output`: 启用流式输出。

### 示例

```bash
# 执行简单指令
python main.py "创建一个测试文件 test.txt，内容为 'Hello World'"

# 仅预览操作，不实际执行
python main.py -p "删除所有 .pyc 文件"

# 使用 Gitee 工具（需配置 GITEE_TOKEN）
python main.py "在 Gitee 上创建一个名为 test-repo 的私有仓库"
```

### Windows 用户
可以使用批处理脚本直接运行：
```cmd
execute-agent.bat "你的指令"
```

## 安全机制

- **路径限制**: 所有文件操作被限制在项目根目录内。
- **核心保护**: 禁止删除或修改核心配置文件（如 `config.json`）。
- **命令过滤**: 内置危险命令黑名单。
- **敏感信息**: `config.json` 和缓存目录默认被 git 忽略，防止泄露。

## 开发与测试

运行测试套件：
```bash
python -m pytest tests/
```

## 贡献

欢迎提交 Issue 和 Pull Request。请确保代码符合 PEP 8 规范，并通过所有测试。
