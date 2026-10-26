# 当前商品的全色SKU图

SKU每个真实颜色恰1张，单独在SKU/，不默认品类、色名或人物。先从当前实拍建立product_colors，每色记录id、名称、source_ids；三类job共用相同product_key和颜色身份，不因主图只选部分色而删色或虚构新色。

每条asset_role=sku、color_ids=[该色唯一id]，按本次确认颜色顺序编号。各色参考由用户提供或明确指定本次已有图；没有可用参考就补问，不调用旧库。同色合格成品经用户指定可复用，如实记录，不称为新生图。

逐色真实传入编辑底图与当前商品事实图，保留对应人物／静物场景、构图和比例，核对本次品牌。亲自审阅商品、文字、版式和人物（如有），未查看不填pass。

```bash
python3 scripts/export_set.py --manifest /absolute/sku-job.json --output /absolute/product-delivery
```

asset_type=sku；默认1200宽且逐张参考比例，不拼长图。上传图在SKU/，原尺寸在SKU/原生图/，总览在SKU/制作资料/overview.png，均仅PNG。output与主图详情同指商品根。核对每色PNG、原生图、总览、顺序、入口和刷新；打包保留相对链接。
