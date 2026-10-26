# 独立导出契约：用户参考工作流

脚本仅导出已生成且真实审阅的图，不生图、不选模板、不判断授权；输入路径相对job解析。包内没有参考图片，素材和成品存任务目录。

## 商品与计划

三类job共用非空product_key和完整product_colors=[{id,name,source_ids}]。每条images写asset_role、color_ids；未展示特定色的主图可空数组，未知色、重复色、缺原始证据被拒绝。

| asset_type | 设置与校验 | 默认输出 |
|---|---|---|
| main | main_image_count正整数，main_sku_count为0到主图数／颜色数的较小值；实际数量精确匹配，代表色不重复 | 1200宽，逐张参考比例，无长图 |
| sku | 每色恰1张、全条role=sku、各仅绑定1色 | 1200宽，逐张参考比例，无长图 |
| detail | 完整覆盖颜色，明确detail_model_policy=per_color或not_required | 750宽，单图与PNG长图 |

缺主图数量字段时默认5张，SKU风格位默认min(2,颜色数,张数)；缺详情人物策略时保留旧job的严格per_color。新任务显式填写，不用默认覆盖用户要求。无人物任务用not_required，各色上身要求用per_color，不允许为省事降级。

per_color要求每色有独立model、has_person=true、单色id且商品和人物QA通过；补屏使用本次可用底图，登记source_template_order、added_for_color，不借其他商品素材。原N屏相对顺序保留。

## 有序参考与候选

template_order、images按最终1..M编号且一一对应，不重新排序。每条参考有本次用户图路径及真实sha256，成品reference_sha256与其一致。重复参考的repeat_of指向更早的同哈希参考，主图template_selection可保存本次选图映射。相同成品只能在合法重复绑定下复用。

每条成品写实际prompt、source_ids、具体review_notes、has_person、qa；product/layout/text全pass，有人时human也须pass，无人明确not_applicable。未看图不填pass。品牌、参考来源、可用范围可附加保存；字段声明不是法律或视觉真实性证明。

仅结构的静物详情例子（无照片，不能直接导出）：

```json
{
  "product_id": "当前商品",
  "product_key": "本次稳定标识",
  "product_colors": [{"id":"color-1","name":"用户确认颜色","source_ids":["本次原图ID"]}],
  "asset_type": "detail",
  "detail_model_policy": "not_required",
  "template_group_id": "本次用户参考组",
  "template_order": [{"order":1,"path":"用户提供参考路径","sha256":"实际哈希"}],
  "images": [{
    "order":1,"asset_role":"detail","color_ids":["color-1"],
    "reference_sha256":"同一参考哈希","image":"本次候选路径",
    "prompt":"实际完整提示词","source_ids":["本次原图ID"],"has_person":false,
    "qa":{"product":"pending","layout":"pending","text":"pending","human":"not_applicable"},
    "review_notes":"实际查看后填写"
  }]
}
```

## PNG目录与命令

三类output均指商品根：

```bash
python3 scripts/export_set.py --manifest /absolute/main-job.json --output /absolute/product-delivery
python3 scripts/export_set.py --manifest /absolute/sku-job.json --output /absolute/product-delivery
python3 scripts/export_set.py --manifest /absolute/detail-job.json --output /absolute/product-delivery --width 750
```

主图／SKU上传PNG直接在图集根，原尺寸在原生图/；详情上传PNG在详情图/单图/，原尺寸在单图/原生图/，详情长图.png与单图/同级。总览统一制作资料/overview.png，导出参考在制作资料/参考模板/。全部PNG，原始输入原格式留任务工作区。主图／SKU原生比例只允许1像素取整误差，不能裁切拉伸。

主图可include_long=true，详情长图与单图逐段像素对应。manifest记录本次数量、人物策略、来源绑定、覆盖与PNG哈希；reference_source_sha256为原参考哈希，reference_file_sha256为转PNG后哈希。输出目录仍为layout_version=5，增加制作设置不改既有PNG布局。

跨图集商品／颜色不一致拒绝，已有同类图集不覆盖，临时导出失败清理新产物。文件检查和审阅声明不替代看图；最终实际浏览器查看入口、全部PNG、原生图、总览、长图和刷新，桌面／手机截图亲自查看并记录实际URL、时间、版本。
