# 维护约定

1. 新增前核对用户指定来源及可用的博客 PROJECT_SOURCES.md；有 SKILL.md 的 Skill 按业务用途归入 skills/<分类>/<skill-name>/，不改 Skill 名称。独立运行工程归入与 skills/ 平级的 workflows/<分类>/<workflow-name>/；不要仅凭名称中包含 workflow 就将 Skill 移出 skills/。
2. 完整保留 Skill 或工作流配套源码、参考、模板、示例及许可，排除 .git、依赖、缓存、构建输出、运行数据与本地凭据；允许复制公开 .env.example、image-env.example.yaml，禁止收录本地 image-env.yaml。
3. 更新前先检查本仓库改动并比对来源，禁止盲目覆盖本地修改。来源缺失时在 catalog.json 的 pending 中记录，恢复后再复制。
4. 同步更新 README.md 用途表、能力总览与对应流程配图、SOURCES.md 来源与变更说明、catalog.json 日期、介绍、状态和文件哈希；Skill 记入 skills，独立工程记入 workflows。安装位置和外部运行依赖写清楚，新增工作流同时更新 workflows/README.md。
5. 核对所有复制文件 SHA-256 与来源一致；补充文件单独注明来源。新增或修改实现时再运行对应测试，真实外部服务执行另行按任务授权。
6. 本仓库修改不会自动同步到原项目或已安装的 Skill；更新后按需复制完整单个 Skill 或工作流目录，并核对版本。独立工作流在工程目录运行，不作为 Skill 安装。

本次只复制与整理，不自动安装、不提交 Git、不推送远端。

## 许可维护（2026-10-11）

本仓库采用根目录 LICENSE 所述自定义个人非商业学习许可，仅对本人有权授权的内容适用。每个 Skill 携带 LICENSE、THIRD_PARTY_NOTICES.md 和 COMMERCIAL-LICENSE.md，独立复制时不得遗漏。根目录许可变更后同步六个 Skill 副本和 catalog.json 哈希；新增第三方代码、依赖或示例时补充权利说明，不覆盖上游许可。新许可不追溯撤销既有有效授权。对外正式采用自定义条款前建议进行法律审阅。
