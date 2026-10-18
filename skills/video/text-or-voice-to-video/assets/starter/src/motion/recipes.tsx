import React, {CSSProperties} from 'react';
import {Img, interpolate, spring, staticFile, useVideoConfig} from 'remotion';

export const colors={paper:'#f4f0e8',ink:'#18222e',blue:'#2864f0',orange:'#ff8c42',muted:'#718096'};
export const progress=(frame:number,at:number,duration=24)=>interpolate(frame,[at,at+Math.max(1,duration)],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
const smooth=(p:number)=>p*p*(3-2*p);
type Timed={frame:number;at:number;duration?:number};

/** Separate parts retain identity while converging on their final layout. */
export const Assemble:React.FC<Timed & {children:React.ReactNode;distance?:number;style?:CSSProperties}>=({frame,at,duration=30,children,distance=140,style})=>{
 const {fps}=useVideoConfig();
 return <div style={{display:'flex',gap:24,alignItems:'center',...style}}>{React.Children.toArray(children).map((child,i,all)=>{
  const p=spring({frame:frame-at-i*5,fps,durationInFrames:duration,config:{damping:22,stiffness:110}});
  return <div key={i} style={{opacity:progress(frame,at+i*5,10),transform:`translate(${(i-(all.length-1)/2)*distance*(1-p)}px,${80*(1-p)}px) rotate(${(i%2?1:-1)*8*(1-p)}deg)`}}>{child}</div>;
 })}</div>;
};

/** A visible object travels along one shared, accurately evaluated cubic path. */
export const PathTransfer:React.FC<Timed & {from:[number,number];to:[number,number];color?:string;children?:React.ReactNode}>=({frame,at,duration=30,from,to,color=colors.blue,children})=>{
 const p=smooth(progress(frame,at,duration)), dx=to[0]-from[0];
 const c1:[number,number]=[from[0]+dx*.38,from[1]],c2:[number,number]=[to[0]-dx*.38,to[1]];
 const point=(axis:number)=>Math.pow(1-p,3)*from[axis]+3*Math.pow(1-p,2)*p*c1[axis]+3*(1-p)*p*p*c2[axis]+p*p*p*to[axis];
 return <><svg style={{position:'absolute',inset:0,width:'100%',height:'100%',overflow:'visible',pointerEvents:'none'}}>
  <path d={`M${from} C${c1} ${c2} ${to}`} stroke={color} strokeWidth={3} fill="none" opacity={.2}/>
  <circle cx={to[0]} cy={to[1]} r={12+progress(frame,at+duration,16)*24} fill="none" stroke={color} strokeWidth={2} opacity={1-progress(frame,at+duration,16)}/>
 </svg><div style={{position:'absolute',left:point(0),top:point(1),transform:'translate(-50%,-50%)',opacity:frame<at?0:1}}>{children??<div style={{width:22,height:22,borderRadius:11,background:color,boxShadow:`0 0 24px ${color}80`}}/>}</div></>;
};

/** Fade out, replace, fade in: two text states never occupy one readable region. */
export const StateChange:React.FC<Timed & {before:React.ReactNode;after:React.ReactNode}>=({frame,at,duration=18,before,after})=>{
 const p=smooth(progress(frame,at,duration));
 return <div style={{position:'relative',width:'100%',height:'100%'}}><div style={{position:'absolute',inset:0,opacity:Math.abs(1-2*p)}}>{p<.5?before:after}</div></div>;
};

/** Relationships bind to actual objects; naked SVG paths are no longer supported. */
export {SemanticConnector as RelationTrace} from '../visual/Visual';

/** x/y are normalized source-image focal coordinates; labels remain outside. */
export const FocusCamera:React.FC<Timed & {src:string;x?:number;y?:number;zoom?:number;highlight?:[number,number,number,number]}>=({frame,at,duration=30,src,x=.5,y=.5,zoom=1.6,highlight})=>{
 const p=smooth(progress(frame,at,duration));
 return <div style={{position:'relative',width:'100%',height:'100%',overflow:'hidden',borderRadius:18}}><div style={{position:'absolute',inset:0,transformOrigin:`${x*100}% ${y*100}%`,transform:`scale(${1+(zoom-1)*p})`}}><Img src={staticFile(src)} style={{width:'100%',height:'100%',objectFit:'contain'}}/>{highlight&&<div style={{position:'absolute',left:`${highlight[0]*100}%`,top:`${highlight[1]*100}%`,width:`${highlight[2]*100}%`,height:`${highlight[3]*100}%`,border:`3px solid ${colors.orange}`,borderRadius:8,opacity:p,boxShadow:'0 0 0 9999px #18222e30'}}/>}</div></div>;
};

/** Independent layers have independent depth; never bake foreground into BG. */
export const ParallaxStage:React.FC<Timed & {layers:{src:string;depth:number;style?:CSSProperties}[];travel?:number}>=({frame,at,duration=120,layers,travel=30})=>{
 const p=smooth(progress(frame,at,duration));
 return <div style={{position:'relative',width:'100%',height:'100%',perspective:1600,overflow:'hidden'}}>{layers.map((layer,i)=><Img key={i} src={staticFile(layer.src)} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'contain',transform:`translateX(${(p-.5)*travel*layer.depth}px) scale(${1+Math.abs(layer.depth)*.012})`,...layer.style}}/>)}</div>;
};

/** Both sides share an exact viewport, so the comparison is meaningful. */
export const CompareWipe:React.FC<Timed & {before:React.ReactNode;after:React.ReactNode;labels?:[string,string]}>=({frame,at,duration=40,before,after,labels})=>{
 const p=smooth(progress(frame,at,duration));
 return <div style={{position:'relative',width:'100%',height:'100%',overflow:'hidden'}}><div style={{position:'absolute',inset:0,clipPath:`inset(0 0 0 ${100*p}%)`}}>{before}</div><div style={{position:'absolute',inset:0,clipPath:`inset(0 ${100*(1-p)}% 0 0)`}}>{after}</div><div style={{position:'absolute',top:0,bottom:0,left:`${p*100}%`,width:3,background:colors.orange}}/>{labels&&<div style={{position:'absolute',bottom:15,left:20,right:20,display:'flex',justifyContent:'space-between',fontSize:22}}><span>{labels[1]}</span><span>{labels[0]}</span></div>}</div>;
};

/** Only the selected segment leaves the stable row and returns as new state. */
export const PatchMerge:React.FC<Timed & {items:React.ReactNode[];replacement:React.ReactNode;index:number}>=({frame,at,duration=60,items,replacement,index})=>{
 const p=progress(frame,at,duration), lift=Math.sin(Math.PI*p)*95;
 return <div style={{display:'flex',alignItems:'center',gap:22}}>{items.map((item,i)=><div key={i} style={{position:'relative',transform:i===index?`translateY(${-lift}px)`:undefined,outline:i===index&&p>0?`3px solid ${colors.orange}`:undefined,borderRadius:14}}>{i===index&&p>=.5?replacement:item}{i===index&&p>.1&&p<.9&&<div style={{position:'absolute',bottom:-40,left:0,right:0,textAlign:'center',fontSize:22,color:colors.orange}}>只更新这一段</div>}</div>)}</div>;
};
