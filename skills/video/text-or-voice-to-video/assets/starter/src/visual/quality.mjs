const finite=(values)=>Array.isArray(values)&&values.every(Number.isFinite);
const validBox=b=>finite(b)&&b.length===4&&b[2]>0&&b[3]>0;
const inside=(a,b,tolerance=0)=>a[0]>=b[0]-tolerance&&a[1]>=b[1]-tolerance&&a[0]+a[2]<=b[0]+b[2]+tolerance&&a[1]+a[3]<=b[1]+b[3]+tolerance;
const overlap=(a,b)=>Math.min(a[0]+a[2],b[0]+b[2])-Math.max(a[0],b[0])>1&&Math.min(a[1]+a[3],b[1]+b[3])-Math.max(a[1],b[1])>1;
const distance=(p,b)=>Math.hypot(Math.max(b[0]-p[0],0,p[0]-b[0]-b[2]),Math.max(b[1]-p[1],0,p[1]-b[1]-b[3]));

export function intersectBoxes(a,b){
 const x=Math.max(a[0],b[0]),y=Math.max(a[1],b[1]);
 const w=Math.min(a[0]+a[2],b[0]+b[2])-x,h=Math.min(a[1]+a[3],b[1]+b[3])-y;
 return w>0&&h>0?[x,y,w,h]:null;
}
export function insetClipBounds(box,css){
 const match=/^inset\(([^)]+)\)$/.exec(css);if(!match)return null;
 const tokens=match[1].split(/\s+round\s+/)[0].trim().split(/\s+/);
 if(tokens.length<1||tokens.length>4||tokens.some(t=>!/^[-+]?(?:\d*\.)?\d+(?:px|%)?$/.test(t)))return null;
 const v=tokens.length===1?[tokens[0],tokens[0],tokens[0],tokens[0]]:tokens.length===2?[tokens[0],tokens[1],tokens[0],tokens[1]]:tokens.length===3?[tokens[0],tokens[1],tokens[2],tokens[1]]:tokens;
 const [t,r,b,l]=v.map((value,i)=>parseFloat(value)*(value.endsWith('%')?box[i%2===0?3:2]/100:1));
 return [box[0]+l,box[1]+t,Math.max(0,box[2]-l-r),Math.max(0,box[3]-t-b)];
}

export function segmentHitsBox(a,b,box,pad=4){
 let lo=0,hi=1;const min=[box[0]-pad,box[1]-pad],max=[box[0]+box[2]+pad,box[1]+box[3]+pad];
 for(let axis=0;axis<2;axis++){
  const d=b[axis]-a[axis];if(Math.abs(d)<1e-9){if(a[axis]<min[axis]||a[axis]>max[axis])return false;continue;}
  const t1=(min[axis]-a[axis])/d,t2=(max[axis]-a[axis])/d;
  lo=Math.max(lo,Math.min(t1,t2));hi=Math.min(hi,Math.max(t1,t2));if(lo>hi)return false;
 }
 return true;
}

export function connectorPoints(source,target,via=[]){
 const anchor=(node)=>{
  if(!node?.id||!validBox(node.box))throw new Error('Connector requires an object ID and finite positive bounds');
  const [x,y,w,h]=node.box;
  switch(node.port){case 'left':return[x-12,y+h/2];case 'right':return[x+w+12,y+h/2];case 'top':return[x+w/2,y-12];case 'bottom':return[x+w/2,y+h+12];default:throw new Error('Explicit connector port required');}
 };
 const start=anchor(source),end=anchor(target);
 if(via.length){if(!via.every(p=>finite(p)&&p.length===2))throw new Error('Invalid connector waypoints');return[start,...via,end];}
 if(Math.abs(start[0]-end[0])<.1||Math.abs(start[1]-end[1])<.1)return[start,end];
 const horizontal=['left','right'].includes(source.port);
 return horizontal?[start,[(start[0]+end[0])/2,start[1]],[(start[0]+end[0])/2,end[1]],end]:[start,[start[0],(start[1]+end[1])/2],[end[0],(start[1]+end[1])/2],end];
}

export function trimPoints(points,progress){
 const lengths=points.slice(1).map((p,i)=>Math.hypot(p[0]-points[i][0],p[1]-points[i][1]));
 let remaining=lengths.reduce((a,b)=>a+b,0)*Math.max(0,Math.min(1,progress));const visible=[points[0]];
 for(let i=0;i<lengths.length;i++){
  if(remaining>=lengths[i]){visible.push(points[i+1]);remaining-=lengths[i];}
  else {const k=lengths[i]?remaining/lengths[i]:0;visible.push(points[i].map((v,j)=>v+(points[i+1][j]-v)*k));break;}
 }
 return visible;
}

export function auditSnapshot(s){
 const issues=[];const add=(code,ids,detail)=>issues.push({code,ids,detail,frame:s.frame,sceneId:s.sceneId});
 if(!Number.isFinite(s.width)||!Number.isFinite(s.height)||s.width<=0||s.height<=0){add('invalid-canvas',[],'Canvas must have finite positive dimensions');return issues;}
 if(s.previewOnly)add('preview-only',[],'Starter/gallery visuals cannot certify a delivered film');
 const objects=s.objects??[],texts=s.texts??[],badges=s.badges??[],connectors=s.connectors??[];
 if(!['scene','flow','comparison','classification','transformation'].includes(s.intent))add('missing-layout-intent',[],'Choose a concrete scene/flow/comparison/classification/transformation before laying out objects');
 if(!objects.length&&!texts.length)add('empty-scene',[],'No measured foreground content; an empty frame cannot certify a layout');
 const byId=new Map();
 for(const item of [...objects,...badges]){
  if(!item.id||byId.has(item.id))add('duplicate-object',[item.id],'Every visible object/status has a stable unique ID');
  byId.set(item.id,item);
 }
 for(const item of [...objects,...texts,...badges]){
  if(!validBox(item.box)){add('invalid-geometry',[item.id],'Measured bounds are invalid');continue;}
  if(!inside(item.box,[0,0,s.width,s.height],1))add('outside-canvas',[item.id],'Visible content extends outside the composition');
 }
 for(const o of objects){
  if(!o.kind?.trim())add('missing-object-kind',[o.id],'Name the concrete object, not a generic placeholder');
  if(/(?:generic.?ai|robot|robot-face|(?:^|[-_])bot(?:$|[-_]))/i.test(o.kind??''))add('generic-ai-mascot',[o.id],'Generic AI robot/mascot placeholders are prohibited');
 }
 const validTexts=texts.filter(t=>validBox(t.box));
 for(let i=0;i<validTexts.length;i++)for(let j=i+1;j<validTexts.length;j++){
  const a=validTexts[i],b=validTexts[j];if(a.rangeId&&b.rangeId&&a.rangeId===b.rangeId)continue;
  if(overlap(a.box,b.box))add('text-overlap',[a.id,b.id],'Two visible text ranges overlap, including spans within one label');
 }
 for(const badge of badges){
  const owner=objects.find(o=>o.id===badge.owner);
  if(!owner)add('badge-missing-owner',[badge.id,badge.owner],'Status needs a specific visible owner');
  else if(validBox(badge.box)&&validBox(owner.box)&&!inside(badge.box,owner.box,.5))add('badge-outside-owner',[badge.id,owner.id],'Place status in a reserved area inside its owner');
  for(const t of validTexts)if(t.badge!==badge.id&&validBox(badge.box)&&overlap(badge.box,t.box))add('badge-over-text',[badge.id,t.id],'Status overlaps a label or body text');
 }
 for(const edge of connectors){
  const from=objects.find(o=>o.id===edge.source),to=objects.find(o=>o.id===edge.target);
  if(!edge.id||!edge.meaning?.trim())add('meaningless-connector',[edge.id],'Every connector must describe a concrete relation');
  if(!['flow','association'].includes(edge.relationship))add('unsupported-relationship',[edge.id],'Classification/comparison uses aligned groups, not branching pseudo-process lines');
  if(edge.relationship==='flow'&&edge.progress>0&&!edge.arrow)add('missing-arrow',[edge.id],'Flow must have a visible arrowhead');
  if(edge.progress<=0)continue;
  if(!from||!to){add('missing-endpoint-object',[edge.id],'Both endpoints must bind to visible objects');continue;}
  if(!Array.isArray(edge.points)||edge.points.some(p=>!finite(p)||p.length!==2)){add('invalid-geometry',[edge.id],'Connector samples must be finite XY pairs');continue;}
  if(edge.progress<=0||edge.points.length<2)continue;
  const start=edge.points[0],end=edge.points.at(-1);
  if(validBox(from.box)&&(distance(start,from.box)<2||distance(start,from.box)>28)||edge.progress>=.995&&validBox(to.box)&&(distance(end,to.box)<2||distance(end,to.box)>28))add('detached-endpoint',[edge.id],'Endpoints need a short gap to object boundaries, not text centers or empty space');
  for(let i=1;i<edge.points.length;i++){
   const a=edge.points[i-1],b=edge.points[i];
   for(const t of validTexts)if(segmentHitsBox(a,b,t.box))add('line-over-text',[edge.id,t.id],'Connector intersects readable text');
   for(const o of objects)if(o.id!==edge.source&&o.id!==edge.target&&validBox(o.box)&&segmentHitsBox(a,b,o.box))add('line-over-object',[edge.id,o.id],'Connector crosses an unrelated object');
  }
 }
 const destinations=new Map();
 for(const edge of connectors.filter(e=>e.progress>0)){if(!destinations.has(edge.source))destinations.set(edge.source,new Set());destinations.get(edge.source).add(edge.target);}
 if([...destinations.values()].some(targets=>targets.size>1))add('branched-connector',[],'Replace one-to-many classification/fan-out with a designed group or comparison layout');
 if(['classification','comparison'].includes(s.intent)&&connectors.some(e=>e.progress>0))add('unnecessary-classification-lines',[],'Aligned categories/comparisons do not need process lines');
 for(const item of s.unmanaged??[])add(item.kind??'unmanaged-graphic',[],item.detail??'Use measured semantic objects/connectors or a meaningful decoration');
 return issues.filter((v,i,a)=>a.findIndex(x=>x.code===v.code&&JSON.stringify(x.ids)===JSON.stringify(v.ids))===i);
}
