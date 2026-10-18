# 混合素材讲解与时间契约

从最终稿生成／整理真实旁白，再按实际音轨拆视觉任务、制作素材、设计状态变化、混音和QA。写稿时可估时，视觉事件必须等真实timeline后锚定。音轨、ASR出处、人工reviewedUnits及换音轨后的失效规则继续遵循[timing.md](timing.md)，混音遵循[audio.md](audio.md)。

## 拆镜头时先写机制

每幕回答：观众应理解什么？哪些对象贯穿其中？这些对象在哪句话后发生什么变化？观众凭什么相信这个变化？界面展示事实，插画解释场景，图解展示关系，文字负责短标签与字幕。同一个书本、请求或磁盘块应保留位置／颜色／轮廓中的身份线索，经历移动、连接、占用或替换；状态改变后留时间读结果。切换媒介时保留关键对象，不把每句话重新画成一张卡片。

按实际内容选媒体比例。当前同稿39.533秒样片的验收目标为文字独占画面时间≤20%、使用四种媒体（illustration、screen、diagram、type）、至少两段持续对象状态演变。这是本次pilot目标，不是强制所有题材或覆盖用户偏好的通用阈值。四种media声明只产生审计数字，不能证明实际画面满足目标。

## storyboard.json v2

顶层为`{"schemaVersion":2,"shots":[...]}`。每个timeline scene恰好对应一shot，所有shot连续覆盖timeline的完整帧区间。

| 字段 | 实际约定 |
|---|---|
| id / sceneId | 唯一镜头ID／当前timeline中scene ID |
| goal | 该幕理解目标，非空 |
| layoutIntent | scene、flow、comparison、classification、transformation之一；正式视觉审计必需 |
| subjects | 对象ID字符串数组，非空且唯一；标签放content，不混用对象与句子 |
| assetIds | assets.json中已登记的ID数组，可为空；screen／illustration必须有素材 |
| media | illustration、screen、diagram、type之一，按实际主画面选择 |
| recipe | assemble、path、state、link、focus、parallax、compare、patch之一 |
| holdMs | 幕尾阅读停留毫秒，非负；动作须在hold前结束 |
| transition | 如`{"kind":"cut"}`；目前为描述信息，starter没有自动转场解释器 |
| events | 至少一个语义事件，见下表 |
| content | 可选的本期组件数据；不得自动映射为图标加白卡的默认布局 |

| event字段 | 实际约定 |
|---|---|
| id | 全片唯一，非空 |
| unitId | 当前timeline caption的id；不要写字幕文字或猜测编号 |
| subjectId | 本shot的subjects成员 |
| action | 非空动作描述；starter不把它自动映射为动画 |
| edge | start或end，默认start |
| offsetMs | 相对所选caption边界的毫秒偏移，默认0，可负但最低-10000；最终事件须在本幕内 |
| durationMs | 正数，省略时编译器默认400；建议显式写出 |

编译帧为`round((caption[edge + 'Ms'] + offsetMs) * fps / 1000)`；动作长度为`ceil(durationMs * fps / 1000)`，hold也向上取整。事件必须满足`scene.startFrame <= event.frame`且`event.frame + durationFrames <= scene.endFrame - holdFrames`。中文词内卡点仍需真实音频复核，句级锚定不能冒充词级精度。

编译器检查媒体／recipe、scene覆盖、引用、事件范围、素材真实存在与来源，输出`src/compiled-storyboard.json`，包含绝对帧事件、输入sourceHashes、assetHashes及媒体时间审计。输出不可覆盖输入或写入public。不要手改编译产物绕过源检查。编译器不是完整JSON Schema验证器：规范字段、subjects字符串类型和转场含义仍须人工核对。

## 真实组件边界

`VisualFilm.tsx`默认只显示不可交付的“画面尚未设计”预览。必须实现本期专用组件，根据稳定event ID取frame／durationFrames，维护具体对象的状态与坐标。多个event必须逐一实现，声明插画或动作字段不代表已执行。字幕仍由真实timeline提供。

`Root.tsx`的AuditComposition位于所有Sequence外部，覆盖整幅画面并记录全局帧。保留这层；视觉对象、关系与状态使用[visual-quality.md](visual-quality.md)中的契约。跨scene延续需要维护对象身份，不能重新加载后跳回初态。录屏播放由本期组件实现，使用public素材并按当前音轨计算片段。

旧storyboard数组可供编译迁移，但不满足新版视觉交付约束；不得通过旧Film或gallery绕过正式导出检查。

## 另一个题材：图书馆借书

假设真实timeline有scene `checkout`，caption `borrow`说“扫描这本书，把借阅记录关联到读者”，caption `due`说“借出后，书的状态和归还日期一起更新”。对象为`book-copy`、`reader-card`、`loan-record`，不要替换成“输入／处理／输出”。以下shot结构有效；必须根据实际caption区间调整offset、duration和hold，并为其余scene补齐shot。

```json
{
  "id": "checkout-shot",
  "sceneId": "checkout",
  "goal": "同一本书从可借变为借出，并关联读者与归还日期",
  "layoutIntent": "scene",
  "subjects": ["book-copy", "reader-card", "loan-record"],
  "assetIds": [],
  "recipe": "link",
  "media": "diagram",
  "holdMs": 600,
  "transition": {"kind": "cut"},
  "events": [
    {"id":"scan-book","unitId":"borrow","subjectId":"book-copy","action":"移动到扫描区","edge":"start","offsetMs":0,"durationMs":600},
    {"id":"associate-reader","unitId":"borrow","subjectId":"loan-record","action":"连到读者卡","edge":"start","offsetMs":700,"durationMs":500},
    {"id":"mark-loaned","unitId":"due","subjectId":"book-copy","action":"可借变为借出并显示归还日期","edge":"start","offsetMs":0,"durationMs":500}
  ],
  "content": {"heading":"借出的是同一本书","nodes":[{"label":"书 B-017","body":"可借 → 借出"},{"label":"读者 R-023","body":"借阅记录关联"}]}
}
```

本次专用组件用`PathTransfer`移动书本副本、`RelationTrace`建立借阅关系、`StateChange`在原坐标更新书本状态，以三个event分别驱动。若动画早于归还日期的实际口播，先只显示借出状态，等相应锚点再显示日期。可以插入实际借阅系统截图与统一风格书架插画；示意系统必须标明。这个例子不需要任何AI工作流术语。

## 可执行预览与交付

下列命令在PROJECT_DIR运行；`SKILL_DIR`替换为实际候选／已安装技能绝对路径，`PYTHON`替换为装有requirements的解释器，路径含空格时保留引号。不要把这些占位符原样执行，也不把某台机器的运行时路径写回技能默认值。

```sh
export VIDEO_PYTHON="PYTHON"
"PYTHON" "SKILL_DIR/scripts/compile_storyboard.py" --timeline src/timeline.json --storyboard src/storyboard.json --assets assets.json --public-dir public --output src/compiled-storyboard.json
```

先选开场、最密集段和结尾三个实际帧号，替换下列F1/F2/F3：

```sh
VIDEO_FRAMES=F1,F2,F3 node render.mjs stills
```

检查像素尺寸下的字、素材、遮挡、对象身份和具体内容，然后对关键运动从起点到落定抽连续帧，例如实际动作若在300–307帧：

```sh
VIDEO_FRAMES=300,301,302,303,304,305,306,307 node render.mjs stills
node render.mjs audit
```

随后实际查看audit产生的全部采样图片，按[visual-quality.md](visual-quality.md)填写当前visual-review.json，再执行`node render.mjs render`。完整渲染逐帧测量，失败候选不能交付。只看上述三张预览不构成审计。

render/stills在bundle前验证当前voice／timeline／script关联并重新编译资产与分镜。audit仅独立检查视觉；render另要求当前源码和图片绑定的审计与逐幕复核。style跳过音轨验证但仍编译分镜；只能用于视觉预览。gallery/gallery-stills跳过音轨验证与分镜编译，使用示意素材；八段各120帧，共960帧／30fps＝32秒。

```sh
node render.mjs gallery-stills
node render.mjs gallery
VIDEO_COMPOSITION=NarratedFilmPortrait node render.mjs stills
VIDEO_COMPOSITION=NarratedFilmPortrait node render.mjs audit
# 查看竖版全部采样并保存对应复核后，才执行正式render
VIDEO_COMPOSITION=NarratedFilmPortrait node render.mjs render
VIDEO_COMPOSITION=RecipeGalleryPortrait node render.mjs gallery
VIDEO_COMPOSITION=LibraryExample node render.mjs gallery
```

横版默认NarratedFilm／RecipeGallery。全帧审计通过的完整渲染写out/silent.mp4；gallery写out/recipe-gallery.mp4；其他gallery composition写out/COMPOSITION_ID.mp4。LibraryExample为8秒无旁白图书馆结构示例，合成时间线明确写在motion/library-example.json，三个事件分别驱动移动、关联和状态更新。静帧在out/stills，元数据在out/MODE-metadata.json。竖版需要再次检查拥挤、越界与素材焦点，不因更换composition就声称适配完成。

先保留纯旁白基准，使用与timeline一致的public/audio/voice.wav：

```sh
"PYTHON" "SKILL_DIR/scripts/mux_audio.py" --video out/silent.mp4 --voice public/audio/voice.wav --timeline src/timeline.json --output out/voice-only.mp4
"PYTHON" "SKILL_DIR/scripts/verify_media.py" --video out/voice-only.mp4 --voice public/audio/voice.wav --output-dir out/qa-voice
```

需要混音时，先按audio.md建立并核对audio-plan，SFX锚定当前caption；所有plan/source/manifest保持可用：

```sh
"PYTHON" "SKILL_DIR/scripts/mix_audio.py" --voice public/audio/voice.wav --timeline src/timeline.json --plan audio-plan.json --output out/audio/mix.wav --no-bgm-output out/audio/mix-no-bgm.wav
"PYTHON" "SKILL_DIR/scripts/mux_audio.py" --video out/silent.mp4 --voice public/audio/voice.wav --mix out/audio/mix.wav --timeline src/timeline.json --output out/final.mp4
"PYTHON" "SKILL_DIR/scripts/verify_media.py" --video out/final.mp4 --voice public/audio/voice.wav --mix out/audio/mix.wav --output-dir out/qa
"PYTHON" "SKILL_DIR/scripts/export_srt.py" --timeline src/timeline.json --output out/captions.srt
```

最终正常速度看整片并听最终混音和无BGM版，报告实际检查范围。静帧、连续帧、全片、PCM同步分别提供不同证据，不能互相替代。发现模板节点堆叠、字幕提前、对象跳变、读不完或旁白被盖住时，回到对应内容／素材／事件／混音步骤修正。
