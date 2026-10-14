import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import {Assemble,PathTransfer,StateChange,RelationTrace,FocusCamera,ParallaxStage,CompareWipe,PatchMerge,colors} from './recipes';

const Tile:React.FC<{label:string;color?:string}>=({label,color=colors.blue})=><div style={{width:180,height:140,background:color,borderRadius:20,color:'white',display:'grid',placeItems:'center',fontSize:32,boxShadow:'0 15px 30px #18222e18'}}>{label}</div>;
export const RecipeGallery:React.FC=()=>{
 const f=useCurrentFrame(),{width,height}=useVideoConfig(),index=Math.min(7,Math.floor(f/120)),local=f-index*120;
 const names=['拆分与组装','路径传递','持续状态变化','建立连接','局部聚焦','分层视差','同尺度对照','局部替换'];
 return <AbsoluteFill style={{background:colors.paper,color:colors.ink,fontFamily:'PingFang SC, sans-serif'}}><div style={{position:'absolute',left:70,top:60,fontSize:50,fontWeight:700}}>{names[index]}</div><div style={{position:'absolute',left:70,top:135,fontSize:24,color:colors.muted}}>可运行镜头示例 · 示意数据 · 真实素材请按内容替换</div><div style={{position:'absolute',left:width*.1,top:height*.3,width:width*.8,height:height*.5,display:'grid',placeItems:'center'}}>
 {index===0&&<Assemble frame={local} at={12}><Tile label="输入"/><Tile label="处理" color={colors.ink}/><Tile label="输出" color={colors.orange}/></Assemble>}
 {index===1&&<><div style={{position:'absolute',left:0,top:100}}><Tile label="请求"/></div><div style={{position:'absolute',right:0,top:100}}><Tile label="接收" color={colors.ink}/></div><PathTransfer frame={local} at={20} duration={50} from={[190,170]} to={[width*.8-180,170]}/></>}
 {index===2&&<div style={{width:420,height:150}}><StateChange frame={local} at={38} before={<Tile label="等待" color={colors.ink}/>} after={<Tile label="完成"/>}/></div>}
 {index===3&&<><div style={{position:'absolute',left:0,top:100}}><Tile label="索引"/></div><div style={{position:'absolute',right:0,top:100}}><Tile label="文件" color={colors.ink}/></div><RelationTrace frame={local} at={15} duration={50} path={`M190 170 C500 20 700 320 ${width*.8-180} 170`}/></>}
 {index===4&&<div style={{width:700,height:400}}><FocusCamera frame={local} at={15} src="examples/source-document.svg" zoom={1.3} x={.55} y={.4}/></div>}
 {index===5&&<ParallaxStage frame={local} at={0} layers={[{src:'examples/backdrop.svg',depth:.2},{src:'examples/source-document.svg',depth:2,style:{width:'50%',left:'25%'}}]}/>}
 {index===6&&<div style={{width:700,height:300}}><CompareWipe frame={local} at={20} duration={50} before={<div style={{width:'100%',height:'100%',background:colors.ink,display:'grid',placeItems:'center',color:'white',fontSize:60}}>处理前</div>} after={<div style={{width:'100%',height:'100%',background:colors.blue,display:'grid',placeItems:'center',color:'white',fontSize:60}}>处理后</div>}/></div>}
 {index===7&&<PatchMerge frame={local} at={15} items={[<Tile key="a" label="保留 A"/>,<Tile key="b" label="原片段" color={colors.ink}/>,<Tile key="c" label="保留 C"/>]} replacement={<Tile label="新片段" color={colors.orange}/>} index={1}/>}
 </div></AbsoluteFill>;
};
