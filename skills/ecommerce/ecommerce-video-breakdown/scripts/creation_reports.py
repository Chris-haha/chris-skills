"""Render validated creative briefs without treating proposed shots as source evidence."""
import html
import re
from urllib.parse import quote
from creation import validate_creation

NAV = [('creation-verdict','先看结论'),('source-beats','视频怎么展开'),('mechanisms','值得学的拍法'),
       ('purchase-bridge','还要补拍什么'),('script','新脚本'),('product-gates','拍之前要确认'),('experiments','比较拍摄效果')]
ROLE = {'attention':'让人愿意停下来看','consideration':'帮助观众判断适不适合自己','conversion':'让有兴趣的人知道下一步怎么选'}
STAGE = {'attention':'引起注意','hook':'开场钩子','proof':'展示证明','consideration':'购买考虑',
         'conversion':'购买行动','cta':'行动提示','demonstration':'实物演示','problem':'使用问题','solution':'解决办法'}
STYLE = '''
aside{max-height:calc(100vh - 40px);overflow:auto}.creation-lead{background:#e9f1e7;border-top:4px solid #126958}.creation-note{font-size:14px;color:var(--muted)}
.beat-card,.mechanism-card,.script-beat{padding:18px 0;border-bottom:1px solid var(--line);scroll-margin-top:24px}
.beat-card:last-child,.mechanism-card:last-child,.script-beat:last-child{border-bottom:0}
.fields{display:grid;grid-template-columns:120px minmax(0,1fr);gap:7px 16px;margin:10px 0 18px}.fields dt{color:var(--muted);font-size:14px}.fields dd{margin:0;white-space:pre-wrap;min-width:0}
.script-time{font-size:18px;font-weight:650;color:var(--accent)}.script-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0}
.copy-fallback textarea{display:block;width:100%;min-height:250px;font:inherit;font-size:14px;line-height:1.7;padding:14px;margin:12px 0;resize:vertical;background:#f5f7f2;color:var(--ink);border:1px solid var(--line)}
.copy-status{font-size:13px;color:var(--muted)}.source-player{width:100%;max-height:560px;background:#142f2e}.clip-button{margin:8px 8px 8px 0}.script-index{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.script-index-card{border:1px solid var(--line);padding:18px}.script-index-card h3{margin-top:0}
@media(max-width:700px){aside{max-height:none}.fields{grid-template-columns:1fr;gap:3px}.fields dd{margin-bottom:10px}.script-index{grid-template-columns:1fr}.script-tools{align-items:flex-start}.source-player{max-height:440px}}
'''
INTERACTIONS = '''<script>
document.addEventListener('click',async function(event){
 const button=event.target.closest('[data-copy-script]');
 if(button){const box=document.getElementById(button.dataset.copyScript),text=box.querySelector('textarea'),status=box.querySelector('[role="status"]');
   try{if(!navigator.clipboard||!navigator.clipboard.writeText)throw new Error('unavailable');await navigator.clipboard.writeText(text.value);status.textContent='脚本文字已复制。';}
   catch(_){const details=box.querySelector('details');details.open=true;text.focus();text.select();status.textContent='已选中文本，请使用系统复制菜单或 Ctrl/Cmd+C。';}return;}
 const clip=event.target.closest('[data-clip-start]');if(!clip)return;
 const player=document.getElementById('source-player'),status=document.getElementById('source-player-status');if(!player)return;
 const start=Number(clip.dataset.clipStart),end=Number(clip.dataset.clipEnd);player.pause();player.dataset.clipEnd=String(end);
 function locate(){player.currentTime=start;player.scrollIntoView({behavior:'smooth',block:'center'});player.focus();if(status)status.textContent='已定位原片 '+start+'–'+end+' 秒；点击播放器播放核对。';}
 if(player.readyState>=1)locate();else player.addEventListener('loadedmetadata',locate,{once:true});
});
document.addEventListener('timeupdate',function(event){const player=event.target;if(player.id==='source-player'&&player.dataset.clipEnd&&player.currentTime>=Number(player.dataset.clipEnd)){player.pause();delete player.dataset.clipEnd;}},true);
</script>'''


def esc(value):
    return html.escape(str(value), quote=True)


def md(value):
    """Keep authored text inert in Markdown viewers, including embedded HTML."""
    return re.sub(r'([\\`*_\[\]|#])', r'\\\1', html.escape(str(value), quote=False))


def fragment(value):
    return quote(str(value), safe='')


def available(analysis, errors=()):
    evidence = {e['id'] for e in analysis.get('evidence', []) if isinstance(e, dict) and isinstance(e.get('id'), str)}
    return not errors and analysis.get('status') == 'complete' and not validate_creation(analysis.get('creation'), evidence)


def status_text(data):
    if data['readiness'] == 'sku_ready':
        return '商品信息已确认 · 可以准备拍摄'
    return '脚本草稿 · 商品尚未选定，尺寸等信息待补'


def fields(items):
    return '<dl class="fields">'+''.join(f'<dt>{esc(label)}</dt><dd>{esc(value)}</dd>' for label,value in items)+'</dl>'


def evidence_links(ids, base=''):
    return '<div class="refs">'+''.join(f'<a href="{esc(base)}#e-{fragment(ref)}">查看原视频 {esc(ref)}</a>' for ref in ids)+'</div>'


def mechanism_links(ids, base=''):
    return '<div class="refs">'+''.join(f'<a href="{esc(base)}#mechanism-{fragment(ref)}">参考拍法 {esc(ref)}</a>' for ref in ids)+'</div>'


def script_text(data):
    s = data['script']
    lines = [s['title'], '新创作建议 · '+status_text(data),
             '目标：'+s['objective'], '形式：'+s['format'], f'拟拍总时长：{s["duration_seconds"]} 秒', '']
    for i,b in enumerate(s['beats'],1):
        lines += [f'镜头 {i} | 拟拍 {b["start"]}–{b["end"]} 秒 | {STAGE.get(b["stage"],b["stage"])}',
                  '景别与动作：'+b['shot'], '口播：'+(b['spoken_text'] or '无口播'), '字幕：'+(b['on_screen_text'] or '无字幕'),
                  '让观众看明白：'+b['viewer_job'], '这一镜头展示什么：'+b['selling_point'], '开拍前要准备：'+b['proof_needed'],
                  '对应前面的拍法：'+', '.join(b['mechanism_ids']), '']
    lines += ['行动提示：'+s['cta'], '', '拍摄素材：']+['- '+v for v in s['materials']]
    lines += ['', '发布前核对：']+['- '+v for v in s['claim_checks']]
    lines += ['', '选好商品后要确认：']+[f'- {r["field"]}（'+('已确认' if r['status']=='verified' else '待确认')+'）：'+r['verification'] for r in data['product_requirements']]
    return '\n'.join(lines)


def creation_html(data, source_base='', anchor_prefix=''):
    def section(key, content, extra=''):
        label = dict(NAV)[key]
        return f'<section id="{esc(anchor_prefix+key)}" class="{extra}"><h2>{label}</h2>{content}</section>'
    verdict = data['verdict']
    intro = f'<span class="badge">{esc(status_text(data))}</span><p class="creation-note">先看这条视频有哪些值得学的地方，再看换成自己的商品应该怎么拍。以下是拍摄建议，是否更受欢迎要拍出来比较。</p>'
    if data['product_status']=='not_provided':
        intro += '<p class="warning">还没选定你的商品，脚本先按同类商品来写。[方括号]里的尺寸、款号等信息，选好实物后再填。</p>'
    result = section('creation-verdict', intro+fields([('最值得学什么',verdict['transfer_value']),('要用来卖货还缺什么',verdict['sales_gap'])])+evidence_links(verdict['evidence_ids'],source_base),'creation-lead')
    beats = '<p class="creation-note">下面说的是原片。后面的“新脚本”是另写的拍摄建议，时间安排也不同。</p>'
    for i,b in enumerate(data['source_beats'],1):
        beats += f'<div class="beat-card"><h3>第{i}部分 · {esc(b["locator"])}</h3>'+fields([('视频里拍了什么',b['action']),('观众可能会想',b['viewer_question']),('这一段让人知道什么',b['new_information'])])+evidence_links(b['evidence_ids'],source_base)+'</div>'
    result += section('source-beats',beats)
    mechanisms=''
    for m in data['mechanisms']:
        mechanisms += f'<div class="mechanism-card" id="{esc(anchor_prefix+"mechanism-"+m["id"])}"><h3>{esc(m["name"])}</h3><span class="badge">{esc(ROLE[m["commercial_role"]])}</span>'
        for label,key in [('原视频怎么拍','observation'),('为什么值得学','interpretation'),('我们可以怎么拍','transfer_rule')]:
            mechanisms += f'<p><strong>{label}</strong></p><p>{esc(m[key])}</p>'
        mechanisms += evidence_links(m['evidence_ids'],source_base)+f'<details><summary>想试两种拍法，可以这样比较</summary><p>{esc(m["counterfactual"])}</p><p>{esc(m["test"])}</p></details></div>'
    result += section('mechanisms',mechanisms)
    bridge='<p class="creation-note">这些是建议新加的镜头。原片没有讲清的问题，自己的销售视频可以接着讲清楚。</p>'
    for b in data['purchase_bridge']:
        bridge += '<div class="beat-card"><h3>'+esc(b['objection'])+'</h3>'+fields([('加拍什么',b['recommended_shot']),('可以这样说',b['conditional_copy']),('这句话先确认什么',b['release_condition'])])+evidence_links(b['evidence_ids'],source_base)+'</div>'
    result += section('purchase-bridge',bridge)
    s=data['script']
    script=f'<span class="badge">新创作建议 · 拟拍时间轴</span><span class="badge">{esc(status_text(data))}</span><h3>{esc(s["title"])}</h3>'+fields([('目标',s['objective']),('形式',s['format']),('拟拍总时长',str(s['duration_seconds'])+' 秒')])
    for i,b in enumerate(s['beats'],1):
        script += f'<div class="script-beat"><div class="script-time">拟拍 {esc(b["start"])}–{esc(b["end"])} 秒 · 镜头 {i}</div>'+fields([
            ('本段作用',STAGE.get(b['stage'],b['stage'])),('景别与动作',b['shot']),('口播',b['spoken_text'] or '无口播'),('字幕',b['on_screen_text'] or '无字幕'),
            ('让观众看明白',b['viewer_job']),('这一镜头展示什么',b['selling_point']),('开拍前要准备',b['proof_needed'])])+mechanism_links(b['mechanism_ids'],source_base)+'</div>'
    script+=fields([('行动提示',s['cta'])])+'<h3>拍摄素材</h3><ul>'+''.join(f'<li>{esc(v)}</li>' for v in s['materials'])+'</ul><h3>发布前核对</h3><ul>'+''.join(f'<li>{esc(v)}</li>' for v in s['claim_checks'])+'</ul>'
    box=anchor_prefix+'script-copy'
    script+=f'<div id="{esc(box)}"><div class="script-tools"><button type="button" data-copy-script="{esc(box)}">复制脚本文字</button><span class="copy-status" role="status" aria-live="polite"></span></div><details class="copy-fallback"><summary>选择并复制脚本文字</summary><label for="{esc(box)}-text" class="small">可选中下方全部文字，通过系统菜单或 Ctrl/Cmd+C 复制。</label><textarea id="{esc(box)}-text" readonly>{esc(script_text(data))}</textarea></details></div>'
    result+=section('script',script)
    gates='<h3>哪些情况需要换个拍法</h3>'+''.join(f'<p><strong>{esc(m["name"])}</strong>：{esc(m["conditions"])}</p>' for m in data['mechanisms'])+'<h3>选好商品后，把这些信息补上</h3>'
    for r in data['product_requirements']:
        values=[('状态','已确认' if r['status']=='verified' else '待确认'),('为什么需要',r['needed_for']),('怎么确认',r['verification'])]
        if r.get('evidence'): values.append(('已确认的资料',r['evidence']))
        gates+=f'<div class="beat-card"><h3>{esc(r["field"])}</h3>'+fields(values)+'</div>'
    result+=section('product-gates',gates)
    experiments=''
    for i,e in enumerate(data['experiments'],1):
        experiments+=f'<div class="beat-card"><h3>实验 {i} · {esc(e["variable"])}</h3>'+fields([
            ('第一条视频',e['control']),('第二条视频',e['treatment']),('相同的部分',e['constants']),('记录哪些数字',e['metric']),('怎么计算',e['denominator']),('根据结果怎么选',e['decision_rule'])])+'</div>'
    return result+section('experiments',experiments)


def creation_markdown(data, source_base=''):
    def refs(ids, kind='e', label='查看原视频'):
        return ' · '.join(f'[{md(label)} {md(ref)}]({source_base}#{kind}-{fragment(ref)})' for ref in ids)
    def pairs(items):
        return [f'- **{label}**：{md(value)}' for label,value in items]+['']
    v=data['verdict']
    lines=['## 先看结论','',status_text(data),'','先看原视频有什么值得学，再看自己的商品怎么拍。建议是否有效，要拍出来比较。','']
    if data['product_status']=='not_provided':
        lines+=['**还没选定你的商品。[方括号]里的尺寸、款号等信息，选好实物后再填。**','']
    lines+=pairs([('最值得学什么',v['transfer_value']),('要用来卖货还缺什么',v['sales_gap'])])+[refs(v['evidence_ids']),'','## 视频怎么展开','','下面说的是原片，时间安排与后面的新脚本不同。','']
    for i,b in enumerate(data['source_beats'],1):
        lines += [f'### 第{i}部分 · {md(b["locator"])}','']+pairs([('视频里拍了什么',b['action']),('观众可能会想',b['viewer_question']),('这一段让人知道什么',b['new_information'])])+[refs(b['evidence_ids']),'']
    lines+=['## 值得学的拍法','']
    for m in data['mechanisms']:
        lines+=[f'### {md(m["name"])}','',ROLE[m['commercial_role']],'']+pairs([('原视频怎么拍',m['observation']),('为什么值得学',m['interpretation']),('我们可以怎么拍',m['transfer_rule'])])+[refs(m['evidence_ids']),'', '**想试两种拍法，可以这样比较**','',md(m['counterfactual']),'',md(m['test']),'']
    lines+=['## 还要补拍什么','','这些是建议新加的镜头。原片没有讲清的问题，自己的销售视频可以接着讲清楚。','']
    for b in data['purchase_bridge']:
        lines+=['### '+md(b['objection']),'']+pairs([('加拍什么',b['recommended_shot']),('可以这样说',b['conditional_copy']),('这句话先确认什么',b['release_condition'])])+[refs(b['evidence_ids']),'']
    s=data['script']
    lines+=['## 新脚本 · 新创作建议，拟拍时间','',f'### {md(s["title"])}','',status_text(data),'']+pairs([('目标',s['objective']),('形式',s['format']),('拟拍总时长',str(s['duration_seconds'])+' 秒')])
    for i,b in enumerate(s['beats'],1):
        lines+=[f'### 拟拍 {b["start"]}–{b["end"]} 秒 · 镜头 {i}','']+pairs([('本段作用',STAGE.get(b['stage'],b['stage'])),('景别与动作',b['shot']),('口播',b['spoken_text'] or '无口播'),('字幕',b['on_screen_text'] or '无字幕'),('让观众看明白',b['viewer_job']),('这一镜头展示什么',b['selling_point']),('开拍前要准备',b['proof_needed'])])+[refs(b['mechanism_ids'],'mechanism','参考拍法'),'']
    lines+=pairs([('行动提示',s['cta'])])+['### 拍摄素材','']+['- '+md(v) for v in s['materials']]+['','### 发布前核对','']+['- '+md(v) for v in s['claim_checks']]+['','## 拍之前要确认','','### 哪些情况需要换个拍法','']
    for m in data['mechanisms']:
        lines+=['- **'+md(m['name'])+'**：'+md(m['conditions'])]
    lines+=['','### 选好商品后，把这些信息补上','']
    for r in data['product_requirements']:
        items=[('状态','已确认' if r['status']=='verified' else '待确认'),('为什么需要',r['needed_for']),('怎么确认',r['verification'])]
        if r.get('evidence'):items.append(('已确认的资料',r['evidence']))
        lines+=['### '+md(r['field']),'']+pairs(items)
    lines+=['## 比较拍摄效果','']
    for i,e in enumerate(data['experiments'],1):
        lines+=[f'### 比较 {i} · {md(e["variable"])}','']+pairs([('第一条视频',e['control']),('第二条视频',e['treatment']),('相同的部分',e['constants']),('记录哪些数字',e['metric']),('怎么计算',e['denominator']),('根据结果怎么选',e['decision_rule'])])
    return '\n'.join(lines)+'\n'


def collection(reports):
    """Both exports link evidence and mechanisms to each original report."""
    cards=[]; bodies=[]; markdown=['# 脚本创作合集','','[返回唯一总入口](index.html)','','每条脚本都能回到原视频查看依据。选好自己的商品，再补上尺寸、款号和实际拍摄素材。','']
    for report in reports:
        r,a=report['record'],report['analysis']
        if not available(a,report['validation_errors']):continue
        base='videos/'+quote(r['video_key'],safe='')+'.html'
        data=a['creation'];label=status_text(data)
        marker='<span class="badge">合成验收示例</span>' if r.get('is_synthetic') else ''
        cards.append(f'<div class="script-index-card">{marker}<h3><a href="{esc(base)}#script">{esc(data["script"]["title"])}</a></h3><p class="small">{esc(r["creator_name"] or "待确认博主")} · {esc(label)}</p><p>{esc(data["verdict"]["transfer_value"])}</p><a href="{esc(base)}#product-gates">查看拍之前要确认的事</a></div>')
        bodies.append(f'<section><h2>{esc(r["title"])}</h2>{marker}<p><a href="{esc(base)}#script">打开单条脚本与原片证据</a></p></section>'+creation_html(data,base,r['video_key']+'--'))
        markdown += ['---','',f'## {md(r["title"])}','','[打开单条脚本与原片证据]('+base+'#script)','','**合成验收示例，不能作为真实爆款案例。**' if r.get('is_synthetic') else '',creation_markdown(data,base)]
    summary='<section id="script-navigation"><h2>脚本创作导航</h2><p>先看原视频值得学什么，再看每个镜头怎么拍、说什么、要准备什么。</p><p><a href="scripts.html">浏览脚本创作合集</a> · <a href="scripts.md">下载 Markdown 合集</a></p><div class="script-index">'+(''.join(cards) or '<p class="muted">尚无通过证据校验的创作包；旧版分析资料仍从下方原入口查看。</p>')+'</div></section>'
    return summary, ''.join(bodies) or '<section><p>尚无通过证据校验的创作包。</p></section>', '\n'.join(markdown)+'\n'
