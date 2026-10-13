# 第三方内容与权利说明

本仓库的自定义许可仅覆盖不吃辣的Chris有权授权的内容，不能代替上游许可或为来源不明的素材补授权限。来源目录记录不等于完整的版权证明。未标明许可不等于可以任意使用。

## 内容来源与边界

| 内容 | 已知来源 | 许可处理 |
| --- | --- | --- |
| 五个分类 Skill 的来源副本 | 根目录 SOURCES.md 与 catalog.json 记录的本机项目；规格书 Skill 来自归档上传包 | 本人有权授权的部分适用 LICENSE；来源记录本身不证明所有文件原创，遇到第三方标记应保留并按其授权处理 |
| 人际冲突 Skill 及历史 HTML 案例 | skills/communication/deal-with-jerks/ | 本人有权授权的部分适用 LICENSE；历史案例不作为事实或咨询质量的证明 |
| 模板库电商生图工作流及八张模板参考图 | workflows/ecommerce/ecommerce-template-image-workflow/；来源见 SOURCES.md 与 catalog.json | 源目录未附许可或逐图权利证明；本人有权授权的部分适用 LICENSE，模板参考图使用前需核实授权，详见工程 THIRD_PARTY_NOTICES.md |
| 商品图、模特参考图与生成场景图 | assets/examples/sources.json 所列原始项目和博客资产 | 可能涉及摄影、肖像、商标、商品设计及生成服务条款；不授予独立转载、商业使用或品牌背书权限 |
| 外文服装规格书 PDF、原稿与批注成品 | 用户提供材料及 coding-blog 归档 | 原稿及所含第三方信息的权利仍归相应权利人；上传或展示不等于可转授权 |
| 原录音、口播稿、字幕、视频、表格截图 | assets/examples/sources.json 所列来源 | 本人有权授权的部分受 LICENSE 约束；其他素材及输出仍须核对各自权利 |
| AI 生成的 README 配图 | assets/readme/IMAGE-SOURCE.md 及对应记录 | 按生成服务条款及适用法律处理；不保证全部元素具有可主张的著作权 |

## 外部依赖和服务

下列为根据当前清单及使用说明识别的主要外部组件，不是逐项完成的法律审计或完整依赖清单。

- 飞书工作流：openai、adm-zip、zod，以及 TypeScript、tsx、Vitest 和类型包等开发依赖；完整版本和传递依赖见对应 package-lock.json。
- 视频工程：Remotion 及 @remotion/*、React、React DOM、TypeScript 和类型包；完整版本和传递依赖见 starter/package-lock.json。
- Python 与媒体处理：numpy、opencc-python-reimplemented、Pillow（相关渲染脚本使用）、FFmpeg/FFprobe、Whisper CLI 及所使用的识别模型；以实际安装组件为准。
- 模板库电商生图工作流：Pillow、PyYAML、pytest；依赖要求见工程 requirements.txt，各组件适用各自许可。
- 外部服务：飞书 API、图片生成服务及其他接入服务，其服务条款、费用和数据规则独立适用。

本仓库的 LICENSE 不覆盖上述第三方组件，不撤销其原许可授予的权限，也不免除其署名、分发、源码提供或付费许可等要求。尤其不得因获得本项目商业授权，就推断已获得 Remotion、模型、字体或素材的全部商业权限。

仓库不分发 node_modules 和上述工具的已安装运行时。安装或分发第三方组件时，应查阅具体版本随附的 LICENSE/NOTICE 及官方条款，保留所要求的声明。发现遗漏或权属问题，可通过本仓库 Issues 联系维护者；确认后补充说明或调整相关材料。
