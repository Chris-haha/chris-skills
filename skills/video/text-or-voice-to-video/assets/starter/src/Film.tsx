import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';
import storyboardData from './storyboard.json';
const storyboard=(Array.isArray(storyboardData)?storyboardData:[]) as {sceneId:string;eyebrow:string;title:string;layout:string;items:{title:string;body:string;visual?:string}[];notes:string}[];

// Replace these layouts with content-specific art direction before final delivery.
const ink='#142d35',paper='#f0ece0',bg='#13232b',accent='#eac567';
export const NarratedFilm:React.FC=()=>{
 const f=useCurrentFrame(),ms=f*1000/timeline.fps;
 const s=timeline.scenes.find(x=>f>=x.startFrame&&f<x.endFrame)??timeline.scenes.at(-1)!;
 const board=storyboard.find(x=>x.sceneId===s.id)??{sceneId:s.id,eyebrow:'',title:s.label,layout:'hero',items:[],notes:''};
 const caption=timeline.captions.find(x=>ms>=x.startMs&&ms<x.endMs);
 const a=interpolate(f-s.startFrame,[0,22],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <AbsoluteFill style={{background:bg,color:paper,fontFamily:'"PingFang SC", sans-serif',padding:'90px 120px'}}>
 <div style={{fontSize:30,letterSpacing:3,color:'#91c3bc'}}>{board.eyebrow}</div>
 <div style={{fontSize:78,fontWeight:600,marginTop:24,opacity:a,transform:`translateY(${(1-a)*25}px)`}}>{board.title}</div>
 <div style={{display:'flex',gap:34,marginTop:60,alignItems:'center'}}>{board.items.map((item,i)=>{
 const k=interpolate(f-s.startFrame,[8+i*8,32+i*8],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
 return <React.Fragment key={i}>{board.layout==='flow'&&i>0?<div style={{fontSize:44,color:accent}}>→</div>:null}<div style={{flex:1,minHeight:270,padding:36,borderRadius:18,background:paper,color:ink,opacity:k,transform:`translateY(${(1-k)*40}px)`,boxShadow:'0 24px 55px #0004'}}>{item.visual?<Img src={staticFile(item.visual)} style={{width:'100%',height:180,objectFit:'contain',marginBottom:20}}/>:null}<div style={{fontSize:42,fontWeight:600}}>{item.title}</div><div style={{fontSize:32,marginTop:24,lineHeight:1.6,whiteSpace:'pre-line'}}>{item.body}</div></div></React.Fragment>})}</div>
 {board.layout==='record'?<svg width="1000" height="170" style={{marginTop:50}}>{Array.from({length:100},(_,i)=>{const v=timeline.waveform[Math.max(0,Math.min(timeline.waveform.length-1,f-50+i))]??0;return <rect key={i} x={i*10} y={85-v*75} width={4} height={Math.max(3,v*150)} fill="#91c3bc"/>})}</svg>:null}
 {board.layout==='transcript'?<div style={{fontSize:44,lineHeight:1.8,marginTop:40}}>{timeline.captions.filter(x=>x.endMs<ms).slice(-4).map(x=><div key={x.id}>{x.text}</div>)}</div>:null}
 <div style={{position:'absolute',left:120,bottom:185,fontSize:30,color:'#9db6b6'}}>{board.notes}</div>
 <div style={{position:'absolute',left:90,right:90,bottom:65,fontSize:62,textAlign:'center',textShadow:'0 3px 10px #000'}}>{caption?.text}</div>
 </AbsoluteFill>;
};
