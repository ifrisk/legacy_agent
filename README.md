# 遗留代码自动化 Agent

`legacy-agent` 用于扫描 Python 和 Go 源代码，提取函数级元数据，
为遗留代码生成表征测试，输出 Markdown API 文档，
并可选地对生成后的测试执行自动修复闭环。

从当前版本开始，项目支持接入真正的 LLM 生成层：可以把“代码理解 -> 测试生成 -> 失败修复”拆分为可配置的 Agent 流程，在保留静态规则兜底能力的同时，让整个系统更接近真实的自动化开发 Agent。

## 解决了什么问题

很多团队在维护遗留项目时，都会遇到下面几类典型问题：

- 代码缺少单元测试，重构时很难判断改动是否引入行为回归
- 历史代码几乎没有文档，新成员接手时需要花大量时间读源码
- 关键函数逻辑分支复杂，人工补测试成本高，且容易漏掉边界条件
- 老项目改动依赖经验驱动，缺少可以快速建立安全感的自动化基线

本项目的目标，就是针对这些问题提供一个自动化入口：先理解代码，再补测试，最后反向生成文档，让遗留系统具备最基础的可维护性资产。

## 提升了什么效率

相较于纯手工梳理代码、编写测试和维护接口文档，这个 Agent 可以显著提升以下环节的效率：

- 测试补全效率：自动识别函数和分支条件，优先生成覆盖边界输入的测试样例
- 重构安全效率：通过表征测试先固化“当前行为”，降低修改遗留代码时的不确定性
- 文档整理效率：根据函数签名、返回值、异常和分支逻辑自动生成 Markdown 文档
- 新人上手效率：把“读源码理解逻辑”转化为“看测试 + 看文档理解逻辑”，缩短熟悉周期
- 评审沟通效率：输出的测试与文档可以直接作为代码评审、技术汇报和项目展示材料

对于缺少测试和文档的老旧项目，这类工具的核心价值不只是“自动生成代码”，而是帮助团队更快建立可验证、可解释、可迭代的维护基线。

## 功能特性

- 递归扫描目标目录下的 `.py` 和 `.go` 文件
- 对函数、参数、返回值注解、分支条件和抛出异常进行静态分析
- 支持可配置的 LLM Agent 流程，用于代码理解、测试生成和失败修复
- 生成面向边界条件输入的 Python `unittest` 表征测试
- 生成 Go `_test.go` 表格驱动测试骨架
- 为每个源码文件生成 Markdown 文档
- 对生成的 Python 测试执行“生成 -> 测试 -> 修复”闭环

## 快速开始

```bash
python -m legacy_agent run --path ./your_project --out ./agent_output
```

输出产物：

- `agent_output/analysis.json`
- `agent_output/agent_context/*.json`
- `agent_output/tests/python/*.py`
- `agent_output/tests/go/*_test.go`
- `agent_output/docs/*.md`
- `agent_output/report.json`

## LLM Agent 模式

项目默认使用静态规则运行，确保在没有大模型依赖时也能完成基础测试和文档生成。

如果要启用真正的 LLM Agent 流程，需要先安装 OpenAI SDK，并设置 API Key：

```bash
pip install .[openai]
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

启用 LLM 的运行方式：

```bash
python -m legacy_agent run --path ./project --out ./agent_output --llm-provider openai --llm-model gpt-5
```

当前 LLM Agent 流程包含三个阶段：

1. 代码理解 Agent：根据静态分析结果和源码内容总结函数职责、风险点和边界条件
2. 测试生成 Agent：结合代码理解结果生成完整的 Python `unittest` 文件
3. 测试修复 Agent：当生成的测试运行失败时，根据报错信息自动修复测试文件

如果 LLM 不可用、API Key 缺失，或模型输出不符合预期，系统会自动回退到原有的静态规则生成流程。

## CLI 用法

```bash
python -m legacy_agent run --path ./project --out ./agent_output --max-repair-attempts 2
python -m legacy_agent analyze --path ./project --out ./agent_output
python -m legacy_agent run --path ./project --out ./agent_output --llm-provider openai --llm-model gpt-5
```

可选参数：

- `--llm-provider`：选择 LLM 提供方，当前支持 `none` 和 `openai`
- `--llm-model`：指定模型名称，默认是 `gpt-5`
- `--llm-api-key-env`：指定 API Key 所在的环境变量名，默认是 `OPENAI_API_KEY`
- `--max-repair-attempts`：控制测试失败后的最大修复次数

## Agent 化架构

当前项目采用“静态分析 + Agent 决策 + 执行闭环”的结构：

```text
代码扫描
  -> 静态分析
  -> 代码理解 Agent
  -> 测试生成 Agent
  -> 执行生成测试
  -> 失败时触发修复 Agent
  -> 输出测试、文档、上下文和报告
```

其中：

- 静态分析负责提供稳定、低成本、可解释的基础上下文
- LLM Agent 负责补足语义理解、边界条件推断和测试代码生成能力
- 执行闭环负责把“生成结果”转化为“可验证结果”，避免只停留在文本输出层面

## 说明

- Python 测试生成更适合可以被安全导入的顶层函数。
- 生成的 Python 测试属于表征测试：它会记录函数在边界输入下的当前行为，从而降低遗留代码重构风险。
- 当前 Go 测试生成的是可编辑骨架，而不是带完整断言的最终测试。
- 当前 LLM 接入优先面向 Python 测试生成与修复；Go 侧仍以静态骨架生成方式为主。
