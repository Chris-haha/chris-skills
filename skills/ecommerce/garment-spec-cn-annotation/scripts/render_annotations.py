#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]

HIRAGANA = re.compile(r'[\u3040-\u309F]')
KATAKANA = re.compile(r'[\u30A0-\u30FF]')
REPLACEMENT = re.compile(r'[�□◻◼☐]')
LATIN_RUN = re.compile(r'[A-Za-z]{4,}')
CJK = re.compile(r'[\u4e00-\u9fff]')

ALLOWED_EN_TOKENS = {
    'ACE5030','GMP','HBT','STT','M','L','XL','XXL','cm','mm','st'
}

def load_font(size:int, preferred:str|None=None):
    for p in ([preferred] if preferred else []) + FONT_CANDIDATES:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()

def expand(box, m):
    x1,y1,x2,y2 = box
    return (x1-m,y1-m,x2+m,y2+m)

def overlaps(a,b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

def in_canvas(box,w,h):
    return box[0]>=0 and box[1]>=0 and box[2]<=w and box[3]<=h

def wrap_text(draw,text,font,max_width):
    if draw.textbbox((0,0), text, font=font)[2] <= max_width:
        return [text]
    lines=[]; cur=''
    for ch in text:
        test=cur+ch
        if cur and draw.textbbox((0,0), test, font=font)[2] > max_width:
            lines.append(cur)
            cur=ch
        else:
            cur=test
    if cur:
        lines.append(cur)
    return lines

def text_metrics(draw, lines, font, line_gap):
    widths=[]; heights=[]
    for line in lines:
        b=draw.textbbox((0,0),line,font=font)
        widths.append(b[2]-b[0]); heights.append(b[3]-b[1])
    return max(widths or [0]), sum(heights)+(len(lines)-1)*line_gap

def candidate_positions(src, tw, th, gap, preferred):
    x1,y1,x2,y2=src
    cx=(x1+x2)/2; cy=(y1+y2)/2
    sides=[preferred] if preferred else []
    for s in ['top','right','bottom','left']:
        if s not in sides: sides.append(s)
    out=[]
    for side in sides:
        if side=='top': pos=(int(cx-tw/2), int(y1-gap-th))
        elif side=='bottom': pos=(int(cx-tw/2), int(y2+gap))
        elif side=='left': pos=(int(x1-gap-tw), int(cy-th/2))
        else: pos=(int(x2+gap), int(cy-th/2))
        out.append((side,*pos))
        for d in (20,-20,40,-40,70,-70,100,-100):
            if side in ('top','bottom'):
                out.append((side,pos[0]+d,pos[1]))
            else:
                out.append((side,pos[0],pos[1]+d))
    return out

def nearest_point_on_box(src, tx, ty, tw, th):
    x1,y1,x2,y2=src
    sx=min(max(tx+tw/2,x1),x2); sy=min(max(ty+th/2,y1),y2)
    ex=min(max((x1+x2)/2,tx),tx+tw); ey=min(max((y1+y2)/2,ty),ty+th)
    return (int(sx),int(sy)),(int(ex),int(ey))

def validate_cn_text(text: str):
    problems=[]
    if not text or not text.strip():
        problems.append('empty text')
        return problems
    if REPLACEMENT.search(text):
        problems.append('contains replacement/garbled character')
    kana_count = len(HIRAGANA.findall(text)) + len(KATAKANA.findall(text))
    cjk_count = len(CJK.findall(text))
    latin_runs = LATIN_RUN.findall(text)
    if kana_count > 0:
        problems.append('contains Japanese kana; should translate to Chinese')
    # allow some tokens/numbers but reject obvious untranslated sentence fragments
    bad_latin = [s for s in latin_runs if s not in ALLOWED_EN_TOKENS]
    if bad_latin and cjk_count < 2:
        problems.append(f'contains likely untranslated Latin text: {bad_latin[:3]}')
    if cjk_count == 0:
        problems.append('no Chinese characters found')
    return problems

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input',required=True)
    ap.add_argument('--annotations',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--qa-report',default='')
    args=ap.parse_args()

    img=Image.open(args.input).convert('RGBA')
    W,H=img.size
    draw=ImageDraw.Draw(img)
    spec=json.loads(Path(args.annotations).read_text(encoding='utf-8'))
    style=spec.get('style',{})
    fs=int(style.get('font_size', max(14,round(W*0.012))))
    color=tuple(style.get('text_color',[0,70,230]))+(255,)
    safe=int(style.get('safe_margin',6)); gap=max(6,int(fs*0.25))
    font=load_font(fs,style.get('font_path'))
    line_gap=max(1,int(fs*0.12))

    anns=spec.get('annotations',[])
    blocked=[expand(tuple(a['source_box']),safe) for a in anns if 'source_box' in a]
    placed=[]
    qa=[]

    for i,a in enumerate(anns, start=1):
        text=a.get('text','').strip()
        problems = validate_cn_text(text)
        if problems:
            raise RuntimeError(f'Annotation #{i} failed validation: {text} | ' + '; '.join(problems))

    for i,a in enumerate(anns, start=1):
        src=tuple(a['source_box'])
        text=a['text'].strip()
        maxw=int(a.get('max_width', min(W*0.28, max(W*0.10, 420))))
        lines=wrap_text(draw,text,font,maxw)
        tw,th=text_metrics(draw,lines,font,line_gap)
        chosen=None
        for side,x,y in candidate_positions(src,tw,th,gap,a.get('preferred_side')):
            box=(x,y,x+tw,y+th)
            padded=expand(box,safe)
            if in_canvas(box,W,H) and not any(overlaps(padded,b) for b in blocked+placed):
                chosen=(side,x,y,box); break
        if chosen is None:
            radius_step=max(30,fs)
            for r in range(radius_step, max(W,H), radius_step):
                found=False
                for deg in range(0,360,15):
                    x=int((src[0]+src[2])/2 + r*math.cos(math.radians(deg)) - tw/2)
                    y=int((src[1]+src[3])/2 + r*math.sin(math.radians(deg)) - th/2)
                    box=(x,y,x+tw,y+th); padded=expand(box,safe)
                    if in_canvas(box,W,H) and not any(overlaps(padded,b) for b in blocked+placed):
                        chosen=('leader',x,y,box); found=True; break
                if found: break
        if chosen is None:
            raise RuntimeError(f'No safe placement found for annotation #{i}: {text}')

        side,x,y,box=chosen
        if bool(a.get('leader',False)) or side=='leader':
            p1,p2=nearest_point_on_box(src,x,y,tw,th)
            draw.line([p1,p2],fill=color,width=max(1,round(fs/18)))

        yy=y
        for line in lines:
            draw.text((x,yy),line,font=font,fill=color)
            b=draw.textbbox((x,yy),line,font=font)
            yy += (b[3]-b[1])+line_gap
        placed.append(expand(box,safe))
        qa.append({
            'index': i,
            'source_text': a.get('source_text',''),
            'text': text,
            'source_box': list(src),
            'placed_box': list(box),
            'leader': bool(a.get('leader',False)) or side=='leader'
        })

    img.convert('RGB').save(args.output, quality=95)
    if args.qa_report:
        report = [
            '# QA Report',
            '',
            f'- annotations rendered: {len(qa)}',
            f'- output: {args.output}',
            '',
            '## Items'
        ]
        for item in qa:
            report.append(f"- {item['index']}. {item['source_text']} -> {item['text']}")
        Path(args.qa_report).write_text('\n'.join(report), encoding='utf-8')
    print(args.output)

if __name__=='__main__':
    main()
