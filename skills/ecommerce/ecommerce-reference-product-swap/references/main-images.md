# 按本次参考制作主图

只用用户为当前任务提供或明确指定的参考，不提供默认图片库或历史商品案例。

与用户确认正整数 `main_image_count` 和非负整数 `main_sku_count`（0到主图数／真实颜色数的较小值）。未指定时建议5张，SKU风格位建议min(2,颜色数,张数)。每个SKU位只绑1个不同真实颜色，其余图展示有据卖点、尺寸或细节。用户要求三张且提供三张就计划三张；不足先确认调整数量、补参考或复用本次可用底图，不假定另有模板。

按用户指定顺序建立输出编号、当前source_template_order、真实参考哈希、颜色、角色、商品证据、保留项和逐字文案，template_selection可保存映射。不同人物姿势用各自参考；静物不加人，不把同一成品复制成不同颜色。重复参考的repeat_of按本次编号重建。

job使用asset_type=main，显式写本次张数与SKU风格位。默认1200宽逐张保留原比例，不裁切拉伸，原生取整误差最多1像素。上传图在主图/，原尺寸在主图/原生图/，总览在主图/制作资料/overview.png；根PNG数量等于本次计划。默认无长图，可include_long=true。

```bash
python3 scripts/export_set.py --manifest /absolute/main-job.json --output /absolute/product-delivery
```

浏览器核对入口、全部单图、原生图、总览、顺序和刷新，检查桌面／手机并亲自看截图。
