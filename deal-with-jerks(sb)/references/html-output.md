# HTML 方案页

仅在用户明确需要页面时使用。先完成核心判断，页面不能增加更强的指控或把推测写成事实。

## 结构与构建

在任务输出目录创建独立文件夹，保留如下结构：

```text
case-output/
  _base.html
  _footer.html
  styles.css
  build.sh
  modules/
    01-situation.html
    02-plan.html
    03-scripts.html
    04-next.html
  index.html
```

1. 从本 skill 的 `references/` 复制 `_base.html`、`_footer.html`、`styles.css` 和 `build.sh`。
2. 替换 `_base.html` 中所有 `CASE_TITLE` 与 `NAV_LINKS`。导航指向模块实际 `id`，例如 `<a href="#plan">行动</a>`。
3. 模块只写 `<section class="module" id="plan">...</section>` 内容；可用 `.script-block`、`.script-item` 展示话术。无需 JavaScript 或框架。
4. 在输出目录执行 `bash build.sh`，检查产出的 `index.html`。

## 内容要求

页面包含：局面与信息缺口、风险与权力关系、主策略和具体动作、适用话术、升级条件。简单案例可合并模块。用户选择不回复时，用安全下一步替代话术卡。

标题描述行为与行动，不下人格结论。事实、用户叙述和推测在页面上明确区分。默认去掉真实姓名、单位、账号、住址和联系方式；除非用户明确要求，不嵌入聊天截图或其他私人材料。

将用户文本作为纯文本处理，转义 `& < > " '`；不得把原始消息拼成 HTML、脚本、事件属性或未经检查的链接。页面不自动上传或分享。

## 验证

- 构建退出码为 0，模块和结束标签顺序完整。
- 无残留 `CASE_TITLE` 或 `NAV_LINKS`，所有导航锚点存在。
- 本地 CSS 正确引用，桌面和窄屏无明显溢出。
- 模板使用在线 Google Fonts；离线时依靠本地字体回退。用户要求完全离线时删除远程字体链接。
- 实际打开检查可读性、敏感信息与文字版一致性；无法预览时明确说明只完成构建和结构检查。
