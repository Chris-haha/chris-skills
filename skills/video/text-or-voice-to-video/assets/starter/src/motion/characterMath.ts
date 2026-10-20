export type Pt=[number,number];
export const clamp=(n:number,a=0,b=1)=>Math.max(a,Math.min(b,n));
export const smooth=(n:number)=>{const t=clamp(n);return t*t*(3-2*t)};
export const phase=(p:number,a:number,b:number)=>a===b?(p<a?0:1):smooth((p-a)/(b-a));
export const mix=(a:number,b:number,p:number)=>a+(b-a)*clamp(p);
/** Two segment inverse kinematics. Unreachable targets are clamped without NaNs. */
export function elbow(shoulder:Pt,requested:Pt,side=1,l1=43,l2=45):{joint:Pt;hand:Pt}{
 const dx=requested[0]-shoulder[0],dy=requested[1]-shoulder[1],raw=Math.hypot(dx,dy);
 const d=clamp(raw,Math.abs(l1-l2)+.001,l1+l2-.001);const vx=raw>.00001?dx/raw:0,vy=raw>.00001?dy/raw:1;
 const a=(l1*l1-l2*l2+d*d)/(2*d),h=Math.sqrt(Math.max(0,l1*l1-a*a));
 return {joint:[shoulder[0]+vx*a-vy*h*side,shoulder[1]+vy*a+vx*h*side],hand:[shoulder[0]+vx*d,shoulder[1]+vy*d]};
}
export function contact(foot:Pt,scale:number,local:Pt,flip=false):Pt{return [foot[0]+((flip?260-local[0]:local[0])-130)*scale,foot[1]+(local[1]-296)*scale]}

/** Use the solved endpoint, including reach clamping and optional mirror, for held props. */
export function handContact(foot:Pt,scale:number,shoulder:Pt,target:Pt,side=1,flip=false):Pt {return contact(foot,scale,elbow(shoulder,target,side).hand,flip)}
