# Workflows 工作流目录

这里收录独立运行的工作流工程，按业务用途分类，与根目录 `skills/` 平级。工作流保留自己的源码、测试、模板和依赖配置；使用时进入具体工程目录运行。

| 分类 | 工作流 | 用途 |
| --- | --- | --- |
| 电商与商品资料 · `ecommerce` | [模板库电商生图工作流](ecommerce/ecommerce-template-image-workflow/README.md) | 参考图确认入库、自动选模、产品事实锁定、几何预检、单张生成与逐实例质检。 |

## 运行模板库电商生图工作流

从仓库根目录执行：

```bash
cd workflows/ecommerce/ecommerce-template-image-workflow
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m workflow.runner --help
```

具体命令、产品一致性清单、几何预检和生成渠道说明见[工程 README](ecommerce/ecommerce-template-image-workflow/README.md)。源 README 保留原项目中的路径示例，在本仓库使用时将 `cd E-commerce/ecommerce-template-image-workflow` 替换为上方目录。

需要验证本地工程时，在工程目录执行 `python -m pytest -q`。真实图片生成另需配置自己的服务；网页 ChatGPT 渠道输出交接包，由用户上传素材并执行生成。默认逐张生成、质检并确认后再继续下一张。

本仓库不收录历史任务目录、收件箱、缓存或本地 `image-env.yaml`。内置模板参考图仅作模板结构示例，使用前应确认素材权利。来源与逐文件哈希见根目录 [SOURCES.md](../SOURCES.md) 和 [catalog.json](../catalog.json)。
