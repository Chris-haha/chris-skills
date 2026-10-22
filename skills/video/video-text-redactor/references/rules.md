# 规则和异常处理

规则是 UTF-8 JSON，`version: 1`。所有时间以输入视频开头为零、单位秒；矩形为左上角起点的 `[x,y,width,height]`。

| 字段 | 含义 |
|---|---|
| `terms` | 任意字符串列表；忽略大小写、空白差异、兼容全角；匹配所有出现 |
| `regex` | Python 正则列表；作用于原始 OCR 文本；默认忽略大小写 |
| `presets` | `email`、`phone-cn`（大陆手机号）、`handle`（@账号）、`url` |
| `all_text` | true 时遮住所有已识别文字；不代表能识别全部视觉文字 |
| `exclude` | 整行排除；该行含任一排除词就保留。它会优先于 terms，慎用 |
| `mode` | `mosaic` 默认；`solid` 使用深色不透明矩形 |
| `padding` | 原分辨率像素外扩，默认 8；还会按文字高度外扩 18% |
| `regions` | 固定或随运动跟踪的区域，详见下例 |
| `intent` | 给复核者看的自然语言任务说明，不参与程序匹配 |

同一名字多个变体加入 `terms` 即可。词语跨 OCR 行分开时不会自动拼接，应分别遮住可见片段或添加区域。任意语义类别需要 Codex 从真实画面/候选识别具体成员；电话号码/邮箱等预设只覆盖对应格式，OCR 错字和空格仍需完整候选及视觉复核。

## 精确词语、正则和区域组合

```json
{
  "version": 1,
  "terms": ["任意公司名", "指定昵称"],
  "regex": ["客户编号[:： ]*[A-Z0-9-]+"],
  "presets": ["email", "phone-cn"],
  "mode": "solid",
  "padding": 12,
  "regions": [
    {
      "label": "头像和署名区域",
      "box": [0.02, 0.10, 0.16, 0.08],
      "start": 3.0,
      "end": 8.5,
      "follow": true
    }
  ]
}
```

区域坐标归一化到 0..1；`start <= t < end`，start 默认 0，end 省略为片尾。`follow: false` 为屏幕固定区域；true 在 start 帧锚定后跟随内容运动。应以原始帧实际坐标换算，不从缩略图直接填像素值。多个镜头分别设 region 时间段和锚框。跟踪失效/切镜头时 true 区域会扩大为整帧；完整画面覆盖会保持到 end。要修正应分段重新锚定，不能将“已经整帧打码”误认为精准跟踪成功。

同一目标只想在特定时间遮挡时，用带时间的 region；当前 `terms/regex` 全片生效。多阶段动态排除或同名不同人需要按镜头/时间拆分任务，不能声称支持未实现的文字级时间条件。

## 输出

- 成片：用户指定的 MP4；独立 `.redaction/` 同名目录。
- `rules.json`：执行时展开预设的规则；原始规则保留在 job 目录。预设会去重，可再次使用执行快照。
- `masks.json`：逐帧遮挡框、来源（ocr/forward/backward/fallback/region）与切镜头索引。
- `ocr-source.jsonl`：每帧原文及坐标；`candidates-full.json`：完整候选汇总、首次出现时间及位置。
- `report.json`：输出散列、帧数、音频、尺寸、缺失词语和跟踪异常。
- `contact-*.jpg` / `masked-*.jpg`：打码版；`compare-*.jpg` 左原图右打码，仅供本机检查。
- verify 的 `verification.json`：逐帧复扫、已知目标命中、最终成片散列。修改成片或规则后旧报告不再有效。

## 性能与边界

4K/60fps 每分钟有 3600 帧，本地高精度 OCR 通常需要明显长于视频时长的处理时间。没有固定耗时承诺；以终端实际 frames/s 估计。默认流程不上传视频、不调用付费 API。

镜像/旋转大角度文字、极小字、压缩模糊、遮挡、长时 OCR 失败都可能漏检。对已知重要位置补 region 或用 solid，仍需检查目标范围。字幕、语音、视频元数据、头像辨识及商标识别不由文字 OCR 自动全部处理；明确用户要求后分别处理。

实现依据：Apple Vision 的 [VNRecognizeTextRequest](https://developer.apple.com/documentation/vision/vnrecognizetextrequest)、[minimumTextHeight](https://developer.apple.com/documentation/vision/vnrecognizetextrequest/minimumtextheight)；本实现将最小文字高度设为图像高度的 0.002，以避免默认阈值漏掉工作台小字。运动跟踪为 OpenCV LK 光流与 RANSAC 相似变换。
