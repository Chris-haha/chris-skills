import React from 'react';
import {AuditScene,VisualText} from './visual/Visual';

/** Non-deliverable starter: replace with a designed episode component. */
export const NarratedFilm:React.FC=()=> <AuditScene id="starter-preview" previewOnly style={{background:'#F4F0E8',color:'#18222E',padding:100}}>
 <VisualText id="setup-title" style={{fontSize:56,fontWeight:700}}>画面尚未设计</VisualText>
 <VisualText id="setup-instruction" style={{marginTop:36,maxWidth:1200}}>请按真实口播绘制具体人物、实物、界面或状态变化。不要把默认节点、机器人标志和无含义连线作为成片。</VisualText>
 <VisualText id="setup-check" style={{marginTop:36}}>完成分镜后运行视觉审计，检查实际静帧，再记录视觉复核结果。</VisualText>
</AuditScene>;
