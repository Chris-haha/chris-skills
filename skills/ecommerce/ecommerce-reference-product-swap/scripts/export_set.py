#!/usr/bin/env python3
"""Export an already reviewed, ordered image set. Does not generate or review images."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
import tempfile
from PIL import Image, ImageChops, ImageDraw

ROOT_INDEX_MARKER='<!-- reference-product-swap:product-index-v5 -->'
OWNED_INDEX_MARKERS=(ROOT_INDEX_MARKER,'<!-- reference-product-swap:product-index-v4 -->')
GROUPS=('主图','SKU','详情图')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_product_root(root, destination):
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise FileExistsError('Product output must be a real directory.')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('This image group already exists; use a new product directory.')
    index=root/'index.html'
    if index.is_symlink() or (index.exists() and (not index.is_file() or not any(marker in index.read_text(encoding='utf-8') for marker in OWNED_INDEX_MARKERS))):
        raise FileExistsError('Refusing to overwrite an unrelated product index.')


def product_index(root):
    links=''.join('<li><a href="'+name+'/index.html">'+name+'</a></li>' for name in GROUPS if (root/name/'index.html').is_file())
    counts=[]
    for name in GROUPS:
        manifest=root/name/'manifest.json'
        if manifest.is_file():
            records=json.loads(manifest.read_text(encoding='utf-8'))
            counts.append(name+' '+str(len(records.get('images',[])))+' 张')
    summary=' · '.join(counts)
    return '<!doctype html>'+ROOT_INDEX_MARKER+'<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(root.name)+'</title><style>body{font:18px/1.8 system-ui;max-width:850px;margin:40px auto;padding:0 20px;background:#f4f1eb}a{color:#315d50}h1{overflow-wrap:anywhere}</style><h1>'+html.escape(root.name)+'</h1><p>'+summary+'。按本次确认的参考与制作计划交付，全部图片为PNG。详情长图与全部单图在详情图目录内。</p><ul>'+links+'</ul></html>'


def main_image_policy(job, colors):
    count=job.get('main_image_count',5)
    if type(count) is not int or count<1:
        raise ValueError('main_image_count must be a positive integer.')
    sku_count=job.get('main_sku_count',min(2,len(colors),count))
    if type(sku_count) is not int or not 0<=sku_count<=min(count,len(colors)):
        raise ValueError('main_sku_count must fit the main image count and available product colors.')
    return count,sku_count


def detail_model_policy(job):
    # Old manifests retain their stricter per-color model requirement.
    policy=job.get('detail_model_policy','per_color')
    if policy not in ('per_color','not_required'):
        raise ValueError('detail_model_policy must be per_color or not_required.')
    return policy


def product_colors(job):
    colors=job.get('product_colors')
    if not isinstance(colors,list) or not colors:
        raise ValueError('product_colors must be a nonempty list with original color evidence.')
    ids=set();names=set();identity={}
    for color in colors:
        if not isinstance(color,dict):raise ValueError('Invalid product color record.')
        cid=color.get('id');name=color.get('name');sources=color.get('source_ids')
        if not isinstance(cid,str) or not cid.strip() or not isinstance(name,str) or not name.strip():
            raise ValueError('Each product color requires a nonempty id and name.')
        if cid in ids or name in names:raise ValueError('Duplicate product color id or name.')
        if not isinstance(sources,list) or not sources or any(not isinstance(src,str) or not src.strip() for src in sources):
            raise ValueError('Each product color requires nonempty original source_ids evidence.')
        ids.add(cid);names.add(name);identity[cid]=(name,sorted(set(sources)))
    return identity


def check_product_identity(root, job):
    identity=job.get('product_key')
    if not isinstance(identity,str) or not identity.strip():
        raise ValueError('A nonempty product identity is required (product_key).')
    colors=product_colors(job)
    for name in GROUPS:
        folder=root/name
        if not folder.is_dir():continue
        manifest=folder/'manifest.json'
        if not manifest.is_file():raise ValueError('Cannot verify product identity of an existing image group.')
        previous=json.loads(manifest.read_text(encoding='utf-8'))
        if previous.get('product_key')!=identity:
            raise ValueError('Different product identity cannot share one product directory.')
        if product_colors(previous)!=colors:
            raise ValueError('Different product color declarations cannot share one product directory.')
    return identity


def check_color_contract(job, asset_type, entries):
    colors=product_colors(job);coverage=set();sku_colors=[];model_colors=set()
    for entry in entries:
        if not isinstance(entry,dict):raise ValueError('Each image requires color_ids and asset_role.')
        ids=entry.get('color_ids');role=entry.get('asset_role')
        if not isinstance(ids,list) or any(not isinstance(cid,str) or cid not in colors for cid in ids):
            raise ValueError('Each image must declare color_ids containing only known product colors.')
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate image color_ids are not allowed.')
        if not isinstance(role,str) or not role.strip():raise ValueError('Each image requires a nonempty asset_role.')
        coverage.update(ids)
        if role=='model' and entry.get('has_person') is True and len(ids)==1:
            model_colors.update(ids)
        if role=='sku':
            if len(ids)!=1:raise ValueError('Each SKU image must bind exactly one color.')
            sku_colors.extend(ids)
        if asset_type=='sku' and role!='sku':raise ValueError('All SKU entries require asset_role=sku.')
    if asset_type=='main':
        count,sku_count=main_image_policy(job,colors)
        if len(entries)!=count:raise ValueError(f'Main image set must contain exactly {count} images.')
        if len(sku_colors)!=sku_count or len(set(sku_colors))!=len(sku_colors):
            raise ValueError(f'Main images require {sku_count} distinct SKU colors.')
    if asset_type=='sku' and (len(entries)!=len(colors) or len(set(sku_colors))!=len(sku_colors) or set(sku_colors)!=set(colors)):
        raise ValueError('SKU set requires exactly one image per product color, without missing or duplicate colors.')
    if asset_type=='detail' and coverage!=set(colors):
        raise ValueError('Detail images must cover every product color.')
    if asset_type=='detail' and detail_model_policy(job)=='per_color' and model_colors!=set(colors):
        raise ValueError('Detail images require an individual model image for every product color.')
    ordered_models=[color['id'] for color in job['product_colors'] if color['id'] in model_colors] if asset_type=='detail' else []
    return [color['id'] for color in job['product_colors'] if color['id'] in coverage],sku_colors,ordered_models


def export_set(manifest_path, output, width=None):
    manifest_path=Path(manifest_path).resolve();output=Path(output).absolute()
    job=json.loads(manifest_path.read_text(encoding='utf-8'))
    asset_type=job.get('asset_type','detail')
    if asset_type not in ('detail','main','sku'):raise ValueError('asset_type must be detail, main or sku.')
    group={'main':'主图','sku':'SKU','detail':'详情图'}[asset_type];destination=output/group
    check_product_root(output,destination)
    product_key=check_product_identity(output,job)
    singles=Path('单图') if asset_type=='detail' else Path('.')
    natives=singles/'原生图';references=Path('制作资料/参考模板')
    long_name={'main':'主图长图','sku':'SKU长图','detail':'详情长图'}[asset_type]
    if width is None:width=750 if asset_type=='detail' else 1200
    if not isinstance(width,int) or not 1<=width<=3840:raise ValueError('Width must be 1..3840.')
    include_long=asset_type=='detail' or job.get('include_long',False)
    if not isinstance(include_long,bool):raise ValueError('include_long must be a boolean.')
    refs=job.get('template_order',[]);entries=job.get('images',[])
    if not isinstance(refs,list) or not isinstance(entries,list):raise ValueError('Reference and image lists are required.')
    color_coverage,selected_sku_colors,model_color_coverage=check_color_contract(job,asset_type,entries)
    expected=list(range(1,len(refs)+1))
    if not refs or len(entries)!=len(refs):raise ValueError('One completed image is required per reference.')
    if [r.get('order') for r in refs]!=expected or [e.get('order') for e in entries]!=expected:
        raise ValueError('Reference and image lists must already be in original order 1..N.')
    resolve=lambda p:(manifest_path.parent/p).resolve()
    prepared=[];seen={};total=0
    for ref,entry in zip(refs,entries):
        r=resolve(ref['path']);src=resolve(entry['image']);rh=digest(r);ih=digest(src)
        if rh!=ref.get('sha256') or rh!=entry.get('reference_sha256'):
            raise ValueError('Reference hash/order binding mismatch.')
        repeat=ref.get('repeat_of')
        if repeat is not None:
            if type(repeat) is not int or not 1<=repeat<ref['order'] or refs[repeat-1]['sha256']!=rh:
                raise ValueError('Invalid repeat_of reference binding.')
        if ih in seen and not (repeat is not None and seen[ih]==(repeat,rh)):
            raise ValueError('Duplicate completed image content requires a matching explicit repeat_of.')
        seen.setdefault(ih,(ref['order'],rh))
        qa=entry.get('qa',{})
        if any(qa.get(k)!='pass' for k in ('product','layout','text')):
            raise ValueError('Product, layout and text must be visually reviewed before export.')
        if not isinstance(entry.get('has_person'),bool):raise ValueError('Declare has_person for each screen.')
        if entry['has_person'] and qa.get('human')!='pass':raise ValueError('Human screen requires human review.')
        if qa.get('human') not in ('pass','not_applicable'):raise ValueError('Human review is pending.')
        if not entry.get('prompt') or not entry.get('source_ids') or not entry.get('review_notes'):
            raise ValueError('Save prompt, original product evidence and actual review observations.')
        with Image.open(r) as im:
            reference_size=im.size;im.verify()
        with Image.open(src) as im:
            im.load();size=im.size
            if asset_type in ('main','sku') and abs(im.height-im.width*reference_size[1]/reference_size[0])>1.01:
                raise ValueError('Main/SKU image aspect ratio differs from its reference.')
            upload_height=round(width*reference_size[1]/reference_size[0]) if asset_type in ('main','sku') else round(im.height*width/im.width)
            panel=im.convert('RGB').resize((width,upload_height),Image.Resampling.LANCZOS)
        prepared.append((ref,entry,r,src,rh,ih,size,panel));total+=panel.height
    if include_long and total>65000:raise ValueError('Long image exceeds supported height; use a smaller proportional width.')
    output.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.image-set-export-',dir=output.parent))
    committed=False;created_root=False
    try:
        for name in (singles,natives,references):(stage/name).mkdir(parents=True,exist_ok=True)
        long=Image.new('RGB',(width,total),'white') if include_long else None;offset=0;records=[];rows=[]
        # Contact sheet is a file/navigation preview, not semantic QA evidence.
        sheet=Image.new('RGB',(1200,360*((len(prepared)+3)//4)),'#f3f0ea');draw=ImageDraw.Draw(sheet)
        for j,(ref,entry,r,src,rh,ih,size,panel) in enumerate(prepared):
            number=f'{j+1:02d}';native=stage/natives/(number+'.png')
            with Image.open(src) as im:
                if im.format=='PNG':shutil.copy2(src,native)
                else:im.convert('RGBA' if 'A' in im.getbands() else 'RGB').save(native,format='PNG')
            reference_name=number+'.png';reference_file=stage/references/reference_name
            with Image.open(r) as im:im.convert('RGBA' if 'A' in im.getbands() else 'RGB').save(reference_file,format='PNG')
            panel.save(stage/singles/(number+'.png'))
            if long is not None:long.paste(panel,(0,offset))
            record=dict(entry,reference=(references/reference_name).as_posix(),reference_sha256=rh,
                        reference_source_sha256=rh,reference_file_sha256=digest(reference_file),image_source_sha256=ih,
                        image=(natives/(number+'.png')).as_posix(),image_sha256=digest(native),native_size=list(size),
                        upload_png=(singles/(number+'.png')).as_posix(),upload_size=list(panel.size))
            record.pop('upload_jpg',None)
            if include_long:record.update(long_y_start=offset,long_y_end=offset+panel.height)
            if ref.get('repeat_of') is not None:record['repeat_of']=ref['repeat_of']
            records.append(record);offset+=panel.height
            thumb=panel.copy();thumb.thumbnail((280,310),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(j%4*300+10,j//4*360+10));draw.text((j%4*300+10,j//4*360+330),number,fill='#222')
            rows.append('<section><h2>'+number+'</h2><p><a href="'+record['upload_png']+'">上传 PNG</a></p><div class="pair"><a href="'+record['reference']+'"><img alt="Reference '+number+'" src="'+record['reference']+'"></a><a href="'+record['image']+'"><img alt="Product '+number+'" src="'+record['image']+'"></a></div></section>')
        if long is not None:
            long.save(stage/(long_name+'.png'))
        sheet.save(stage/'制作资料/overview.png')
        if include_long:
            with Image.open(stage/(long_name+'.png')) as stitched:
                stitched.load()
                for record,prepared_row in zip(records,prepared):
                    crop=stitched.crop((0,record['long_y_start'],width,record['long_y_end']))
                    if ImageChops.difference(crop,prepared_row[-1]).getbbox() is not None:
                        raise RuntimeError('Long image segment mismatch.')
        title=html.escape(str(job.get('product_id','Product')))
        set_label={'main':'Main image set','sku':'SKU image set','detail':'Detail set'}[asset_type]
        long_links='<a href="长图预览.html">长图预览</a><a href="'+long_name+'.png">Long PNG</a>' if include_long else ''
        page='<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+title+' · '+set_label+'</title><style>body{margin:24px auto;max-width:1100px;padding:0 16px;background:#f4f1eb;color:#222;font:16px system-ui}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}img{width:100%;height:auto}section{margin:24px 0}h2{font-size:18px}a{color:inherit}nav{display:flex;gap:24px;flex-wrap:wrap}</style><h1>'+title+' · '+str(len(records))+' screens</h1><p>Left: original reference. Right: corresponding product. Selected reference order retained.</p><nav>'+long_links+'<a href="制作资料/overview.png">Overview</a></nav>'+''.join(rows)+'</html>'
        page=page.replace('<nav>','<nav><a href="../index.html">商品目录</a>')
        (stage/'index.html').write_text(page,encoding='utf-8')
        if include_long:
            (stage/'长图预览.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · 长图</title><style>body{margin:0;background:#eeeae2;font:16px/1.7 system-ui}header{max-width:850px;margin:24px auto;padding:0 16px}img{display:block;width:100%;height:auto}main{max-width:'+str(width)+'px;margin:auto}h1{overflow-wrap:anywhere}</style><header><h1>'+title+'</h1><p>'+str(len(records))+'屏 · '+str(width)+'×'+str(total)+'</p><a href="index.html">逐屏对照</a> · <a href="../index.html">商品目录</a> · <a href="'+long_name+'.png">PNG</a></header><main><img src="'+long_name+'.png" alt="'+title+'完整长图"></main></html>',encoding='utf-8')
        report={'asset_type':asset_type,'delivery_directory':group,'singles_directory':singles.as_posix(),'layout_version':5,'file_checks':'pass','order':expected,'screens':len(records),'long_size':[width,total] if include_long else None,
                'pixel_verified_segments':len(records) if include_long else 0,'semantic_review':'user_supplied_agent_attestation',
                'browser_review':'pending','color_coverage':color_coverage,'selected_sku_colors':selected_sku_colors,'model_color_coverage':model_color_coverage,'claim':'File checks do not prove product/model fidelity.'}
        policy={}
        if asset_type=='main':
            main_count,sku_count=main_image_policy(job,product_colors(job))
            policy.update(main_image_count=main_count,main_sku_count=sku_count)
        if asset_type=='detail':policy['detail_model_policy']=detail_model_policy(job)
        report.update(policy)
        manifest=dict(product_id=job.get('product_id'),product_key=product_key,asset_type=asset_type,product_colors=job['product_colors'],selected_sku_colors=selected_sku_colors,color_coverage=color_coverage,model_color_coverage=model_color_coverage,template_group_id=job.get('template_group_id'),template_selection=job.get('template_selection'),layout_version=5,images=records,**policy)
        (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        (stage/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        check_product_root(output,destination)
        check_product_identity(output,job)
        if not output.exists():output.mkdir();created_root=True
        stage.rename(destination);committed=True
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=output,prefix='.product-index-',delete=False) as temp:
            index_temp=Path(temp.name);temp.write(product_index(output))
        try:index_temp.replace(output/'index.html')
        finally:index_temp.unlink(missing_ok=True)
        return report
    except Exception:
        if stage.exists():shutil.rmtree(stage)
        if committed and destination.exists():shutil.rmtree(destination)
        if created_root and output.exists() and not any(output.iterdir()):output.rmdir()
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path,help='Shared product root; creates 主图/, SKU/ or 详情图/ without replacing an existing group.')
    parser.add_argument('--width',type=int,default=None,help='Defaults to 750 for detail, 1200 for main/sku; preserves each image ratio.')
    args=parser.parse_args()
    print(json.dumps(export_set(args.manifest,args.output,args.width),ensure_ascii=False,indent=2))
