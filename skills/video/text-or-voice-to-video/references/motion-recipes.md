# 八种可运行运动原语

实现位于`assets/starter/src/motion/recipes.tsx`，预览位于`src/motion/Gallery.tsx`。从当前工程的`./motion/recipes`导入；gallery展示技术能力，不代表任何稿件的设计已经完成。默认色板是paper `#f4f0e8`、ink `#18222e`、blue `#2864f0`、orange `#ff8c42`、muted `#718096`，可按题材与品牌调整。

所有组件共享`frame:number`、`at:number`、可选`duration:number`，单位均为帧。frame与at必须使用相同坐标系：主片可直接用useCurrentFrame和编译event绝对frame；若放在Sequence中用局部帧，先将at减去Sequence起始帧。duration取编译的durationFrames，避免另写固定秒数。下面的默认帧数是组件默认值，语义时长仍由当前音轨决定。

| recipe / 导出组件 | 附加props与默认值 | 适用与实际边界 |
|---|---|---|
| assemble / Assemble | children必需；distance=140；style可选；duration=30 | 零件保留身份后组装。children按索引错开5帧，淡入10帧；最后一件可能比首件晚落定，应纳入hold检查。使用spring，非几何形变。 |
| path / PathTransfer | from、to为像素二元组；color=blue；children可选；duration=30 | 同一对象沿三次贝塞尔路径移动；无children时为光点。路径显示浅线，到达后16帧光圈扩散，给尾效留空间。不是物理模拟。 |
| state / StateChange | before、after必需；duration=18 | 同一坐标空间内两状态交叉淡化。父容器须有宽高；保留对象外形与位置才有连续性，不能把两张无关卡片叫作对象变形。 |
| link / RelationTrace | path为SVG path字符串；color=blue；width=4；duration=24 | 按pathLength绘制关系线；路径坐标对应父舞台。仅画线，不自动移动对象或推导关系。 |
| focus / FocusCamera | src为public相对路径；x=.5、y=.5；zoom=1.6；highlight可选[x,y,w,h]；duration=30 | 通过transformOrigin与scale聚焦。x/y和highlight归一化；图像objectFit=contain，有留白时高亮须按实际呈现核对。标签应在缩放层外。 |
| parallax / ParallaxStage | layers为{src,depth,style?}数组；travel=30；duration=120 | 各图层以不同深度横移并轻微缩放；src为public相对路径。透明前景与背景应分离，整张图反复复制不能产生真实遮挡关系。 |
| compare / CompareWipe | before、after必需；labels可选二字符串组；duration=40 | 同一视口从左向右揭示after，orange分割线。当前labels[1]显示左下、labels[0]显示右下；使用前核对顺序。对照对象必须同尺度／同指标。 |
| patch / PatchMerge | items、replacement、index必需；duration=60 | 指定索引单元上抬，在进度0.5时换内容再回位；其余保持稳定。内置中文“只更新这一段”提示，非中文或不同语义需改组件。index须为有效索引。 |

组件要求带尺寸的相对定位父容器。对象可传图片、SVG或具体图形，children不必是文字节点。复杂题材可扩展这些原语或直接写本次组件；不要求所有片子都展示八种效果。

## 多事件如何实际驱动

编译器负责把caption锚点转成帧，组件负责解释动作。不要把JSON里列了三个event当作执行了三个动作。下面从当前shot取两个事件，示意书本移动与关联线；尺寸、路径、外形应按本次画面设计：

```tsx
const f = useCurrentFrame();
const byId = (id: string) => {
  const event = shot.events.find(e => e.id === id);
  if (!event) throw new Error(`Missing event ${id}`);
  return event;
};
const scan = byId('scan-book');
const associate = byId('associate-reader');
return <div style={{position:'relative', width:1200, height:600}}>
  <PathTransfer frame={f} at={scan.frame} duration={scan.durationFrames}
    from={[180,300]} to={[600,300]}>
    <BookCopy id="book-copy" />
  </PathTransfer>
  <RelationTrace frame={f} at={associate.frame}
    duration={associate.durationFrames} path="M600 300 C760 300 820 420 1000 420" />
</div>;
```

`BookCopy`是项目自己实现的书本对象，不是技能提供的组件。还应按mark-loaned事件更新同一书本的状态和日期，避免同时存在一个旧书本与一个未关联的新书本。完整shot示例见[visual-story.md](visual-story.md)。先看动作起、中、末连续帧，再看正常速度；落定静帧不能揭示遮挡、跳变或不自然的加速。
