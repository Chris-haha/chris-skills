# UP主全部视频链接获取（任务C 手册）

目标：拿某 UP 主空间**公开列表里的全部视频**（链接+标题+发布时间）。

## 路线（已实战验证）

### 第1步：元数据打底
`scripts/bili_meta.py <该UP任一视频>` → 拿 `mid`、`season_id`（合集）。
空间投稿总数：打开 `https://space.bilibili.com/<mid>/upload/video`，分页器文本"共 N 页 / X 个"——**X 是最终完整性校验基准**。

### 第2步：合集接口打底（匿名可用）
```
GET https://api.bilibili.com/x/polymer/web-space/seasons_archives_list
    ?mid=<mid>&season_id=<sid>&sort_reverse=true&page_num=<1..N>&page_size=30
```
带 UA + `Referer: https://space.bilibili.com/`。翻页直到返回空/不足30。
⚠️ 合集 ≠ 全部：UP 主常有合集外投稿（快讯/教程/突发），本步只做底料。

### 第3步：内置浏览器翻页补全集（合集外视频只有这条路）
前置：加载 browser-use:control-browser 技能，通过 node_repl 驱动（bootstrap 每次都要跑）。

1. 打开 `https://space.bilibili.com/<mid>/upload/video`，等 `.video-pagination` 出现（列表接口偶发不渲染，reload 重试即可恢复）。
2. 每页抽取：`document.querySelectorAll('a[href*="/video/BV"]')` 取 BV 号；向上找卡片容器拿 innerText（含播放数/日期文本）。
3. 翻页——**三大坑，全部踩过**：
   - **DOM 合成 click() 间歇无效**：必须用真实坐标点击 `getByRole("button", {name: "<页码>"}).click()`。
   - **active 状态 ≠ 内容更新**：分页器高亮先变、列表 XHR 可能被风控静默吞掉。必须以「列表第一个 BV 号变化」为翻页成功判据，轮询等 10~25s。
   - **"下一页"连点易失败，点具体页码更稳**；一次失败换目标页码重试，别连续硬点。
4. 每页存增量（Map 去重落盘），直到 **BV 总数 == 分页器声明的 X 个**。

### 第4步：view 接口补全元数据
对每个 BV 调 `api.bilibili.com/x/web-interface/view?bvid=<bv>`（匿名可用，加 0.15s 间隔；实测 255 连发 0 失败），拿准确 pubdate/title/duration，按时间排序输出 markdown 清单。

## 死路（别再试）
- `x/space/wbi/arc/search`（空间投稿搜索）：匿名 curl → HTTP 412；页面内带 Cookie fetch → -403；Python 正确 wbi 签名后浏览器内请求 → **-352 风控校验失败**。签名没错，是风控拒匿名。
- `web-dynamic/v1/feed/space`（动态流）：同样 412。
- URL 带 `?pn=N` 跳页：SPA 忽略，永远渲染第 1 页。
- 跳页输入框 fill+Enter：不生效。

## 口径注意
- 空间头部"投稿 N"常 > 列表数 X（如 287 vs 255）：差值是仅自己可见/特殊类型稿件，匿名拿不到，如实声明即可。
- AI 字幕/视频总结接口同理需登录；这些死路不用重试，直接走上面的活路。
