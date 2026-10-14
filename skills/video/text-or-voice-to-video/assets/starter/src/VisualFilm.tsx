import React from 'react';
import {AbsoluteFill,useCurrentFrame,useVideoConfig} from 'remotion';
import {NarratedFilm as LegacyFilm} from './Film';
import timeline from './timeline.json';
import compiled from './compiled-storyboard.json';
import assets from '../assets.json';
import {CompiledStory} from './motion/types';
import {Assemble,PathTransfer,StateChange,RelationTrace,FocusCamera,ParallaxStage,CompareWipe,PatchMerge,colors} from './motion/recipes';

const Node:React.FC<{label:string;body?:string;accent?:boolean}>=({label,body,accent})=><div style={{width:230,minHeight:180,padding:30,borderRadius:20,background:accent?colors.blue:'white',color:accent?'white':colors.ink,boxShadow:'0 15px 40px #18222e10'}}><div style={{fontSize:38,fontWeight:650}}>{label}</div>{body&&<div style={{fontSize:25,lineHeight:1.5,marginTop:20}}>{body}</div>}</div>;

export const NarratedFilm:React.FC=()=>{
 const f=useCurrentFrame(),{width,height}=useVideoConfig(),portrait=height>width;
 const story=compiled as unknown as CompiledStory;
 if(story.schemaVersion===1)return <LegacyFilm/>;
 const shot=story.shots.find(s=>f>=s.startFrame&&f<s.endFrame);
 if(!shot)throw new Error('No compiled visual shot for current frame');
 const at=shot.events[0].frame,duration=shot.events[0].durationFrames;
 const asset=assets.assets.find(a=>a.id===shot.assetIds[0]);
 const nodes=shot.content?.nodes??shot.subjects.map(label=>({label,body:''}));
 const objects=nodes.map((n,i)=><Node key={i} {...n} accent={i===1}/>);
 const caption=timeline.captions.find(c=>f*1000/timeline.fps>=c.startMs&&f*1000/timeline.fps<c.endMs);
 const stageW=portrait?900:1600,stageH=portrait?900:620;
 const view=<div style={{width:stageW,height:stageH,position:'relative',display:'grid',placeItems:'center'}}>
  {shot.recipe==='assemble'&&<Assemble frame={f} at={at} duration={duration} style={portrait?{flexDirection:'column'}:undefined}>{objects}</Assemble>}
  {shot.recipe==='path'&&<><div style={{position:'absolute',left:40,top:stageH*.35}}>{objects[0]}</div><div style={{position:'absolute',right:40,top:stageH*.35}}>{objects[1]}</div><PathTransfer frame={f} at={at} duration={duration} from={[280,stageH*.5]} to={[stageW-280,stageH*.5]}/></>}
  {shot.recipe==='state'&&<div style={{width:320,height:250}}><StateChange frame={f} at={at} duration={duration} before={objects[0]} after={objects[1]??objects[0]}/></div>}
  {shot.recipe==='link'&&<><div style={{position:'absolute',left:40,top:stageH*.35}}>{objects[0]}</div><div style={{position:'absolute',right:40,top:stageH*.35}}>{objects[1]}</div><RelationTrace frame={f} at={at} duration={duration} path={`M280 ${stageH*.5} C${stageW*.4} 50 ${stageW*.6} 50 ${stageW-280} ${stageH*.5}`}/></>}
  {shot.recipe==='focus'&&asset&&<FocusCamera frame={f} at={at} duration={duration} src={asset.path}/>}
  {shot.recipe==='parallax'&&<ParallaxStage frame={f} at={at} duration={duration} layers={shot.assetIds.map((id,i)=>({src:assets.assets.find(a=>a.id===id)!.path,depth:.3+i}))}/>}
  {shot.recipe==='compare'&&<CompareWipe frame={f} at={at} duration={duration} before={objects[0]} after={objects[1]??objects[0]}/>}
  {shot.recipe==='patch'&&<PatchMerge frame={f} at={at} duration={duration} items={objects} index={Math.min(1,objects.length-1)} replacement={<Node label="已更新" accent/>}/>}
 </div>;
 return <AbsoluteFill style={{background:colors.paper,color:colors.ink,fontFamily:'PingFang SC,sans-serif'}}><div style={{position:'absolute',left:80,top:portrait?170:80,right:80,fontSize:portrait?62:64,fontWeight:650}}>{shot.content?.heading??shot.goal}</div><div style={{position:'absolute',left:(width-stageW)/2,top:portrait?460:230}}>{view}</div><div style={{position:'absolute',left:60,right:60,bottom:portrait?190:65,fontSize:portrait?48:44,textAlign:'center',lineHeight:1.45}}>{caption?.text}</div></AbsoluteFill>;
};
