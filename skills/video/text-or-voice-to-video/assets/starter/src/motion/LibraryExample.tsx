import React from 'react';
import {AbsoluteFill,useCurrentFrame} from 'remotion';
import timing from './library-example.json';
import {colors,PathTransfer,RelationTrace,StateChange,progress} from './recipes';

export const LibraryExample:React.FC=()=>{
 const f=useCurrentFrame();
 const anchor=(id:string)=>{const e=timing.events.find(x=>x.id===id)!;return Math.round((timing.captions.find(c=>c.id===e.unitId)!.startMs+e.offsetMs)*timing.fps/1000);};
 const book=(loaned=false)=><div style={{width:175,height:240,borderRadius:'5px 15px 15px 5px',background:loaned?colors.orange:colors.blue,color:'white',borderLeft:'18px solid #18222e55',boxShadow:'12px 15px 35px #18222e20',padding:'32px 20px'}}><div style={{fontSize:20,letterSpacing:3}}>BOOK</div><div style={{fontSize:37,fontWeight:650,marginTop:18}}>B-017</div><div style={{fontSize:25,marginTop:35}}>{loaned?'已借出':'可借阅'}</div></div>;
 return <AbsoluteFill style={{background:colors.paper,color:colors.ink,fontFamily:'PingFang SC,sans-serif'}}><div style={{position:'absolute',left:95,top:75,fontSize:60,fontWeight:650}}>借出的是同一本书。</div><div style={{position:'absolute',left:100,top:160,fontSize:24,color:colors.muted}}>不同题材结构样例 · 合成时间线 · 无旁白</div>
 <div style={{position:'absolute',left:100,top:330,width:430,height:420,borderBottom:'22px solid #937d65',borderLeft:'14px solid #937d65',borderRight:'14px solid #937d65',background:'#e8e0d5'}}>{Array.from({length:5},(_,i)=><div key={i} style={{position:'absolute',left:25+i*72,top:50,width:52,height:300,background:['#50687e','#8f9f99','#a88a76','#526d9d','#808374'][i],borderRadius:4}}/>)}<div style={{position:'absolute',left:20,top:460,fontSize:31}}>馆藏书架</div></div>
 {f<anchor('scan')?<div style={{position:'absolute',left:180,top:410}}>{book()}</div>:f<anchor('scan')+30?<PathTransfer frame={f} at={anchor('scan')} duration={30} from={[265,530]} to={[930,530]}>{book()}</PathTransfer>:<div style={{position:'absolute',left:842,top:410,width:175,height:240}}><StateChange frame={f} at={anchor('loan')} duration={15} before={book()} after={book(true)}/></div>}
 <div style={{position:'absolute',left:735,top:750,width:410,height:6,background:colors.blue}}/><div style={{position:'absolute',left:810,top:800,fontSize:31}}>扫描并更新状态</div>
 <RelationTrace id="book-reader-association" frame={f} at={anchor('associate')} duration={21} source={{id:'book',box:[842,410,175,240],port:'right'}} target={{id:'reader',box:[1390,335,390,310],port:'left'}} relationship="association" meaning="这本书的借阅记录关联到此读者"/>
 <div style={{position:'absolute',left:1390,top:335,width:390,height:310,background:'white',borderRadius:22,padding:32,boxShadow:'0 15px 40px #18222e14'}}><div style={{fontSize:23,color:colors.muted}}>读者卡 / READER</div><div style={{fontSize:48,marginTop:28}}>R-023</div><div style={{fontSize:27,color:colors.blue,marginTop:30,opacity:progress(f,anchor('associate'),15)}}>关联 B-017</div><div style={{fontSize:25,color:'#b95f1a',marginTop:18,opacity:progress(f,anchor('loan'),15)}}>归还日期已更新 · 示意</div></div>
 <div style={{position:'absolute',bottom:65,left:100,fontSize:35}}>{f<anchor('scan')?'先找到可借阅的书。':f<anchor('associate')?'扫描这本书。':f<anchor('loan')?'把书和读者的借阅记录关联起来。':'书的位置、身份保留，借阅状态发生变化。'}</div></AbsoluteFill>;
};
