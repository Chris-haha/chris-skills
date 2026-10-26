"""Structural checks for evidence → mechanism → conditional product script.

These checks reject missing relationships, not bad creative judgment. Editorial review is still required.
"""
import math


def template():
    return {'version':1,'product_status':'not_provided','readiness':'conditional_brief',
            'verdict':{'transfer_value':'','sales_gap':'','evidence_ids':[]},
            'source_beats':[],'mechanisms':[],'purchase_bridge':[],'product_requirements':[],
            'script':{'title':'','objective':'','format':'','duration_seconds':0,'timeline_basis':'proposed',
                      'shoot_status':'conditional','beats':[],'cta':'','materials':[],'claim_checks':[]},'experiments':[]}


def number(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def validate_creation(data, evidence_ids):
    errors=[]
    if not isinstance(data,dict) or data.get('version')!=1:
        return ['缺少新版创作转化包；旧报告只保留为分析资料，需补充机制、商品迁移与逐镜头脚本']
    def fields(obj,names,label):
        if not isinstance(obj,dict):
            errors.append(label+'必须是对象');return False
        for k in names:
            if not isinstance(obj.get(k),str) or not obj[k].strip():errors.append(label+'缺少文本 '+k)
        return True
    def objects(obj,key,label):
        items=obj.get(key)
        if not isinstance(items,list) or not items or any(not isinstance(x,dict) for x in items):
            errors.append(label+'需要非空对象数组');return []
        return items
    def refs(obj,key,allowed,label):
        value=obj.get(key)
        if not isinstance(value,list) or not value or any(not isinstance(x,str) for x in value) or not set(value).issubset(allowed):
            errors.append(label+'引用缺失或无效')
    def texts(obj,key,label):
        value=obj.get(key)
        if not isinstance(value,list) or not value or any(not isinstance(x,str) or not x.strip() for x in value):
            errors.append(label+'需要非空文本数组')
    if data.get('product_status') not in ('not_provided','provided'):
        errors.append('必须说明我方商品资料是否提供')
    if data.get('readiness') not in ('conditional_brief','sku_ready'):
        errors.append('创作成熟度无效')
    verdict=data.get('verdict')
    if fields(verdict,('transfer_value','sales_gap'),'创作判断'):refs(verdict,'evidence_ids',evidence_ids,'创作判断')
    for b in objects(data,'source_beats','原片信息推进'):
        fields(b,('locator','action','viewer_question','new_information'),'原片节拍')
        refs(b,'evidence_ids',evidence_ids,'原片节拍')
    mechanisms=objects(data,'mechanisms','内容机制')
    ids=[]
    for m in mechanisms:
        fields(m,('id','name','observation','viewer_task','interpretation','transfer_rule','conditions','counterfactual','test'),'机制')
        refs(m,'evidence_ids',evidence_ids,'机制')
        if m.get('commercial_role') not in ('attention','consideration','conversion'):
            errors.append('机制需说明注意、考虑或行动作用')
        if isinstance(m.get('id'),str):ids.append(m['id'])
    if len(ids)!=len(set(ids)):errors.append('机制ID重复')
    for b in objects(data,'purchase_bridge','购买说服补充'):
        fields(b,('objection','recommended_shot','conditional_copy','release_condition'),'购买说服补充')
        refs(b,'evidence_ids',evidence_ids,'购买说服补充')
    requirements=objects(data,'product_requirements','我方商品核验清单')
    for r in requirements:
        fields(r,('field','needed_for','verification'),'商品核验项')
        if r.get('status') not in ('unknown','verified'):errors.append('商品核验状态无效')
        if r.get('status')=='verified' and (not isinstance(r.get('evidence'),str) or not r['evidence'].strip()):errors.append('已核验商品字段缺少我方证据文本出处')
    if data.get('readiness')=='sku_ready' and (data.get('product_status')!='provided' or any(r.get('status')!='verified' for r in requirements)):
        errors.append('未知商品条件不能标记为可直接拍摄的SKU脚本')
    script=data.get('script')
    if not fields(script,('title','objective','format','cta'),'拟拍脚本'):
        return errors
    if script.get('timeline_basis')!='proposed':errors.append('拟拍脚本时间轴必须标为新创作建议，不能冒充原片时间轴')
    if script.get('shoot_status') not in ('conditional','ready'):errors.append('拟拍脚本拍摄状态无效')
    if script.get('shoot_status')=='ready' and data.get('readiness')!='sku_ready':errors.append('条件化草案不能标记可直接拍摄')
    duration=script.get('duration_seconds')
    if not number(duration) or duration<=0:errors.append('拟拍脚本总时长必须是正数')
    previous=0
    for b in objects(script,'beats','逐镜头脚本'):
        fields(b,('stage','shot','viewer_job','selling_point','proof_needed'),'脚本镜头')
        for k in ('spoken_text','on_screen_text'):
            if not isinstance(b.get(k),str):errors.append('脚本镜头需明确口播／字幕文本，静音时口播可为空')
        if not b.get('spoken_text') and not b.get('on_screen_text'):errors.append('脚本镜头缺少口播和字幕设计')
        refs(b,'mechanism_ids',set(ids),'脚本到机制')
        start,end=b.get('start'),b.get('end')
        if not number(start) or not number(end) or start!=previous or end<=start or (number(duration) and end>duration):
            errors.append('新脚本镜头需顺序连续且在总时长内，不能重叠、遗漏或倒序')
        if number(end):previous=end
    if number(duration) and previous!=duration:errors.append('镜头安排未覆盖完整拟拍时长')
    texts(script,'materials','拍摄素材');texts(script,'claim_checks','发布前核对')
    for e in objects(data,'experiments','创意实验'):
        fields(e,('variable','control','treatment','constants','metric','denominator','decision_rule'),'创意实验')
    return errors
