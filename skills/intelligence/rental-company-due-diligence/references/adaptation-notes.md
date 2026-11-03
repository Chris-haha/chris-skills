# 外部方法的来源与适配

2026-11-03核对GitHub原文后，围绕租户签约付款决策自行实现以下改进。没有复制第三方脚本、词典、模板或整包安装，没有将其专用服务、采集额度或个人配置设为本技能依赖。

| 研究来源 | 本技能采用的设计思路 | 适配边界 |
|---|---|---|
| [multi-search-engine](https://github.com/KPWang-Skills-Hub/multi-search-engine/blob/main/SKILL.md)，文件SHA `1b4e0d80e146680c67fc3941c71b070b0295aec7` | 明确搜索入口与不同渠道；提供自行编写的URL规划器 | 仅选适用入口，规划不等于执行；区域入口、镜像和同源结果不当成独立证据 |
| [zuzufang风险分类参考](https://github.com/daxueren666/zuzufang/blob/main/references/risk-signals.md)，SHA `d66b67885c28a0b02decd22d6939ef0c463e32e7` | 关键词召回后需要语义复核；保留数据稀少与采集缺口 | 自行编写投诉陈述与事件核验规则；不复制词典/代码，不以高赞或附和决定置信度，不引入登录采集、固定批量或7天缓存策略 |
| [osint-agent证据模板](https://github.com/carlosceja27/osint-agent/blob/main/references/templates.md)，SHA `8557c50494146f3d04510b7a3c7d57a886fc08fb`；[企业尽调参考](https://github.com/carlosceja27/osint-agent/blob/main/references/due-diligence.md) | 有来源的关系边、原始证据链、替代解释检验，以及新发现后的同步更新 | 只覆盖相关企业/交易，简化为表格；不照搬海外制裁筛查、全量个人背景或固定多年追溯和审批流程 |
| [agent-browser交互流程](https://github.com/vercel-labs/agent-browser/blob/main/skill-data/core/SKILL.md)，SHA `83c735a83665630a93e60af36c33ca3fa0006543` | 观察、操作、等待结果、重新观察；任务隔离 | 复用现有浏览器工具；不强制安装或替换工具，不授予登录、提交投诉、账户操作权限 |

依赖与版权取舍：zuzufang仓库的 [LICENSE](https://github.com/daxueren666/zuzufang/blob/main/LICENSE) 是PolyForm Noncommercial 1.0.0，本次仅研究公开设计思路，未纳入其受许可的实现或文本。osint-agent与agent-browser仓库声明Apache-2.0；multi-search-engine的SKILL声明MIT，不能据此假设所有第三方附件均已获相同授权。后续若实际引入第三方内容，另核对具体文件许可并保留所需声明。

[博查接口说明](https://github.com/Bocha-Labs/bocha-skills/blob/main/bocha-web-search/SKILL.md)与[企查查Connector示例](https://github.com/infometa/workbuddyskills/blob/main/skills/qcc-company/SKILL.md)仅作可选能力识别。当前没有引入其API或运行时，不承诺数据权限或可访问性。
