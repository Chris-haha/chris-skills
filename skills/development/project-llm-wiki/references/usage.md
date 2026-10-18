# 分发与调用

将整个 `project-llm-wiki/` 文件夹交给使用者，保留 SKILL.md、references、assets 与 scripts 的相对位置。支持技能发现的宿主，放入其支持的用户级或项目级技能目录；实际目录以该宿主约定为准。包内不硬编码安装路径、项目路径或用户身份。

没有技能机制的 Agent，可把下面指令作为任务开头：

```text
读取 /技能所在路径/project-llm-wiki/SKILL.md，并按该技能为 /目标项目路径 搭建 LLM Wiki。
根据任务继续读取技能内部的相对路径资源；先检查现有知识库，完成首轮真实资料摄入并报告验证结果。
```

初始化还需把项目任务规则接入宿主实际读取的入口：优先使用 `init --entry-file ...`，已有库用适配合并加 `connect`。规则指向项目内的 schema、agent-workflow 与 index；完成后用户正常提出项目请求，Agent 按规则消费知识、执行验收并回流，通常无需另装执行 skill 或每次追加长提示词。脚本不会监听消息或自动完成业务任务，执行依靠 Agent 读取并遵循项目规则。

未自动读取项目规则的宿主，在每次新会话开头提供一次入口：

```text
本项目使用 LLM Wiki。请先读取 docs/wiki/AGENTS.md、agent-workflow.md 和 index.md，
后续项目任务按运行流程查询知识、实际执行、验收，并在允许写入时按影响回流。
```

原生支持技能调用时，可按宿主语法调用。以下 `$project-llm-wiki` 是示例入口名；不是所有 Agent 通用的指令语法。

```text
使用 $project-llm-wiki 为当前项目搭建 docs/wiki，读取现有说明与配置，完成首轮摄入。

使用 $project-llm-wiki 为已有知识库补充项目任务运行流程，并合并到当前 Agent 的项目规则入口；保留现有 schema 和知识页。

使用 $project-llm-wiki 修复这个项目的问题：先查相关知识与当前代码，实际验证修复，再同步受影响的知识。

使用 $project-llm-wiki 摄入 docs/wiki/raw/meeting-notes.md，合并到现有页面并登记知识缺口。

使用 $project-llm-wiki 查询：这个项目如何运行，哪些条件还没有确认？本次只读。

使用 $project-llm-wiki 根据本次变更同步受影响知识页，不重写无关主题。

使用 $project-llm-wiki 体检现有 Wiki，区分结构错误、证据缺口和内容过时。
```

可选脚本的本地自测：

```text
node --test "技能目录/scripts/wiki.test.mjs"
```

脚本仅用 Node.js 18+ 标准库；无需 npm install。测试在系统临时目录创建隔离项目，并清理自己创建的目录。宿主禁止创建符号链接/junction 时相应用例会明确 skip；其余用例仍执行。

最低执行能力是读取技能与项目资料、生成 Markdown；写入文件与运行命令取决于宿主权限。纯对话或只读环境可产出文件内容/差异供人工应用，不能保证自动落盘、自动发现技能或后台持续维护。
