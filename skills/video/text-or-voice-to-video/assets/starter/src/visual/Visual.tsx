import React,{CSSProperties,useId,useLayoutEffect,useRef} from 'react';
import {AbsoluteFill,cancelRender,continueRender,delayRender,getInputProps,useCurrentFrame,useVideoConfig} from 'remotion';
import {Box,Endpoint,Point,connectorPoints,trimPoints,intersectBoxes,insetClipBounds} from './quality.mjs';

export const VisualObject:React.FC<{id:string;kind:string;box:Box;children:React.ReactNode;style?:CSSProperties}>=({id,kind,box,children,style})=><div data-vq-object={id} data-vq-kind={kind} style={{position:'absolute',left:box[0],top:box[1],width:box[2],height:box[3],...style}}>{children}</div>;
export const VisualText:React.FC<{id:string;children:React.ReactNode;style?:CSSProperties}>=({id,children,style})=><div data-vq-label={id} style={{fontSize:34,lineHeight:1.4,...style}}>{children}</div>;
export const VisualDecoration:React.FC<{purpose:'background'|'section-divider';children:React.ReactNode;style?:CSSProperties}>=({purpose,children,style})=><div data-vq-decoration={purpose} style={style}>{children}</div>;

/** Status occupies normal flow in a reserved owner region; no absolute red X. */
export const StatusLabel:React.FC<{id:string;owner:string;state:'pass'|'revise'|'pending';label:string;style?:CSSProperties}>=({id,owner,state,label,style})=>{
 const color=state==='pass'?'#237B65':state==='revise'?'#B46B23':'#647185';
 return <div data-vq-badge={id} data-vq-owner={owner} style={{display:'inline-flex',alignItems:'center',gap:10,alignSelf:'flex-start',padding:'8px 16px',borderRadius:12,fontSize:25,fontWeight:650,lineHeight:1.4,color,background:state==='pass'?'#E0F0E8':state==='revise'?'#FFF0DE':'#EAEFF5',...style}}><span aria-hidden="true" style={{width:8,height:8,borderRadius:8,background:color,flex:'0 0 auto'}}/>{label}</div>;
};

/** Direction is explicit, geometry is shared with layout, labels stay outside paths. */
export const SemanticConnector:React.FC<{id:string;frame:number;at:number;duration?:number;source:Endpoint;target:Endpoint;relationship:'flow'|'association';meaning:string;via?:Point[];color?:string;width?:number}>=({id,frame,at,duration=24,source,target,relationship,meaning,via=[],color='#2864F0',width=5})=>{
 const marker=useId().replace(/[^a-zA-Z0-9_-]/g,'');
 if(!id||!meaning.trim()||!['flow','association'].includes(relationship))throw new Error('Semantic connector requires ID, meaning and explicit flow/association');
 const raw=Math.max(0,Math.min(1,(frame-at)/Math.max(1,duration))),p=raw*raw*(3-2*raw);
 const points=trimPoints(connectorPoints(source,target,via),p);
 const d=points.map((point,i)=>`${i?'L':'M'}${point[0]} ${point[1]}`).join(' ');
 return <svg data-vq-connector={id} data-vq-source={source.id} data-vq-target={target.id} data-vq-relationship={relationship} data-vq-meaning={meaning} data-vq-progress={p} style={{position:'absolute',inset:0,width:'100%',height:'100%',overflow:'visible',pointerEvents:'none'}}>
  <defs><marker id={marker} markerWidth="20" markerHeight="20" viewBox="0 0 10 10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0L10 5L0 10Z" fill={color}/></marker></defs>
  {p>0&&<path data-vq-visible-path="true" d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" markerEnd={relationship==='flow'?`url(#${marker})`:undefined}/>}
 </svg>;
};

export const AuditScene:React.FC<{id:string;children:React.ReactNode;previewOnly?:boolean;style?:CSSProperties}>=({id,children,previewOnly=false,style})=><AbsoluteFill data-vq-scene={id} data-vq-preview-only={previewOnly?'true':undefined} style={style}>{children}</AbsoluteFill>;

/** Installed at the composition root, outside Sequence, so frame and scope are absolute. */
export const AuditComposition:React.FC<{id:string;intent:string;children:React.ReactNode}>=({id,intent,children})=>{
 const root=useRef<HTMLDivElement>(null),frame=useCurrentFrame(),{width,height}=useVideoConfig();
 const audit=getInputProps().visualAudit===true;
 useLayoutEffect(()=>{
  if(!audit)return;
  const handle=delayRender('Measuring actual visual layout');let disposed=false;
  document.fonts.ready.then(async()=>{
   // Read the version-pinned Remotion readiness list, excluding this audit's own handle.
   const started=performance.now();let settled=0;
   while(performance.now()-started<25000){
    await new Promise<void>(resolve=>requestAnimationFrame(()=>resolve()));
    if(disposed)return;
    const r=root.current?.getBoundingClientRect();
    const others=window.remotion_delayRenderHandles.filter(h=>h!==handle);
    const images=Array.from(root.current?.querySelectorAll('img')??[]);
    const ready=others.length===0&&document.fonts.status==='loaded'&&r&&r.width>0&&r.height>0&&images.every(im=>im.complete&&im.naturalWidth>0);
    settled=ready?settled+1:0;if(settled>=3)return;
   }
   throw new Error('Visual audit could not observe a ready, settled frame');
  }).then(()=>{
   if(disposed||!root.current)return;
   const scene=root.current,base=scene.getBoundingClientRect(),sx=width/base.width,sy=height/base.height;
   const box=(r:DOMRect|DOMRectReadOnly):Box=>[(r.left-base.left)*sx,(r.top-base.top)*sy,r.width*sx,r.height*sy];
   const visible=(el:Element)=>{
    let current:Element|null=el,opacity=1;
    while(current&&current!==scene.parentElement){const c=getComputedStyle(current);if(c.display==='none'||c.visibility==='hidden')return false;opacity*=Number(c.opacity);current=current.parentElement;}
    const r=el.getBoundingClientRect();return opacity>.04&&r.width>0&&r.height>0;
   };
   const objects=Array.from(scene.querySelectorAll<HTMLElement>('[data-vq-object]')).filter(visible).map(el=>({id:el.dataset.vqObject,kind:el.dataset.vqKind,box:box(el.getBoundingClientRect())}));
   const clippedText=(rect:DOMRect,parent:Element):Box|null=>{
    let result:Box|null=box(rect),ancestor:Element|null=parent;
    while(ancestor&&ancestor!==scene&&result){
     const c=getComputedStyle(ancestor),bounds=box(ancestor.getBoundingClientRect());
     if(c.clipPath!=='none'){
      const clip=insetClipBounds(bounds,c.clipPath);
      if(!clip)throw new Error('Audited text clipping requires an explicit inset() region');
      result=intersectBoxes(result,clip);
     }
     if(result&&['hidden','clip','scroll','auto'].includes(c.overflowX))result=intersectBoxes(result,[bounds[0],result[1],bounds[2],result[3]]);
     if(result&&['hidden','clip','scroll','auto'].includes(c.overflowY))result=intersectBoxes(result,[result[0],bounds[1],result[2],bounds[3]]);
     ancestor=ancestor.parentElement;
    }
    return result;
   };
   const badges=Array.from(scene.querySelectorAll<HTMLElement>('[data-vq-badge]')).filter(visible).map(el=>({id:el.dataset.vqBadge,owner:el.dataset.vqOwner,box:box(el.getBoundingClientRect()),text:el.innerText}));
   const texts:{id:string;box:Box;text:string;badge?:string;rangeId:string}[]=[];
   const walker=document.createTreeWalker(scene,NodeFilter.SHOW_TEXT);let node:Node|null;let textIndex=0;
   while((node=walker.nextNode())){
    const parent=node.parentElement;if(!parent||!node.textContent?.trim()||!visible(parent)||parent.closest('defs,style,script'))continue;
    const range=document.createRange();range.selectNodeContents(node);
    const label=parent.closest<HTMLElement>('[data-vq-label]')?.dataset.vqLabel??`text-${textIndex++}`;
    const badge=parent.closest<HTMLElement>('[data-vq-badge]')?.dataset.vqBadge;
    const rangeId=`range-${textIndex++}`;let ri=0;
    for(const rect of Array.from(range.getClientRects())){
     const clipped=clippedText(rect,parent);
     if(clipped&&clipped[2]>1&&clipped[3]>1)texts.push({id:label,rangeId:`${rangeId}-${ri++}`,box:clipped,text:node.textContent.trim(),badge});
    }
   }
   const connectors=Array.from(scene.querySelectorAll<SVGSVGElement>('[data-vq-connector]')).map(el=>{
    const path=el.querySelector<SVGPathElement>('[data-vq-visible-path]');const points:Point[]=[];
    if(path&&visible(el)){
     const length=path.getTotalLength(),ctm=path.getScreenCTM();
     if(ctm)for(let i=0;i<=Math.max(1,Math.ceil(length/4));i++){
      const p=path.getPointAtLength(length*i/Math.max(1,Math.ceil(length/4))),screen=new DOMPoint(p.x,p.y).matrixTransform(ctm);
      points.push([(screen.x-base.left)*sx,(screen.y-base.top)*sy]);
     }
    }
    return{id:el.dataset.vqConnector,source:el.dataset.vqSource,target:el.dataset.vqTarget,relationship:el.dataset.vqRelationship,meaning:el.dataset.vqMeaning,progress:Number(el.dataset.vqProgress),arrow:!!path&&getComputedStyle(path).markerEnd!=='none',points};
   });
   const unmanaged:{kind:string;detail:string;box?:Box}[]=[];
   for(const el of Array.from(scene.querySelectorAll<HTMLElement>('img,svg,path,line,polyline,div'))){
    if(!visible(el)||el.closest('defs')||el.closest('[data-vq-object],[data-vq-badge],[data-vq-connector]'))continue;
    const decoration=el.closest<HTMLElement>('[data-vq-decoration]');
    if(decoration){
     const b=box(decoration.getBoundingClientRect());
     if(decoration.dataset.vqDecoration==='section-divider'&&b[1]>height*.22&&b[1]+b[3]<height*.8)unmanaged.push({kind:'unmanaged-line',detail:'A middle-stage divider can masquerade as an unexplained relationship; remove it',box:b});
     continue;
    }
    if(['svg','path','line','polyline','img'].includes(el.tagName.toLowerCase())){unmanaged.push({kind:'unmanaged-graphic',detail:`Unowned ${el.tagName} requires a concrete VisualObject or a declared decoration`});continue;}
    const b=box(el.getBoundingClientRect()),c=getComputedStyle(el);
    if(b[2]>60&&b[3]<=10&&b[3]>0&&b[2]/b[3]>8&&c.backgroundColor!=='rgba(0, 0, 0, 0)'&&c.backgroundColor!=='transparent')unmanaged.push({kind:'unmanaged-line',detail:'Unexplained thin horizontal bar',box:b});
   }
   const previewOnly=!!scene.querySelector('[data-vq-preview-only="true"]');
   console.log('VISUAL_AUDIT:'+JSON.stringify({frame,sceneId:id,intent,width,height,previewOnly,objects,texts,badges,connectors,unmanaged}));
  }).catch(error=>cancelRender(error)).finally(()=>continueRender(handle));
  return()=>{disposed=true;continueRender(handle);};
 },[audit,frame,height,id,intent,width]);
 return <AbsoluteFill ref={root} data-vq-audit-root="true" style={{fontFamily:'PingFang SC,sans-serif'}}>{children}</AbsoluteFill>;
};
