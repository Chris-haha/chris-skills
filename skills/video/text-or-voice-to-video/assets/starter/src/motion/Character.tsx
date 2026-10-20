import React from 'react';
import {VisualObject} from '../visual/Visual';
import {Pt,elbow,mix,phase} from './characterMath';
export type Pose='idle'|'walk'|'carry'|'wave'|'point'|'think'|'pull'|'turn'|'write'|'celebrate'|'shiver';
export type Mood='happy'|'think'|'surprised'|'worried'|'proud';
export type CharacterProps={id:string;x:number;y:number;scale?:number;frame:number;pose?:Pose;mood?:Mood;progress?:number;walking?:boolean;shirt?:string;leftHand?:Pt;rightHand?:Pt;look?:number;flip?:boolean};
const ink='#263a40',skin='#ffd9b0';
/** Articulated human learner. x/y is the foot anchor, hands are local rig coordinates. */
export const Character:React.FC<CharacterProps>=({id,x,y,scale=1,frame,pose='idle',mood='happy',progress=1,walking=false,shirt='#ed8f54',leftHand,rightHand,look=0,flip=false})=>{
 const walk=walking||pose==='walk';const cycle=frame*.29;const bounce=walk?-Math.abs(Math.sin(cycle))*5:Math.sin(frame*.065)*1.5;
 const held=!!(leftHand||rightHand||pose==='carry');
 const tremble=pose==='shiver'&&!held?Math.sin(frame*1.9)*2.2:0;const lean=pose==='pull'?-6*phase(progress,0,.4):pose==='think'?4:pose==='turn'?3*Math.sin(progress*Math.PI):0;
 let lh:Pt=[84,202],rh:Pt=[178,202];
 if(walk){lh=[84+Math.sin(cycle)*18,195-Math.cos(cycle)*8];rh=[178-Math.sin(cycle)*18,195+Math.cos(cycle)*8];}
 if(pose==='carry'){lh=[62,192];rh=[198,192];}
 if(pose==='wave'||pose==='celebrate')rh=[182+Math.sin(frame*.21)*13,80+Math.cos(frame*.21)*8];
 if(pose==='celebrate')lh=[77+Math.sin(frame*.19)*10,83];
 if(pose==='point')rh=[211,125];
 if(pose==='think')rh=[151,109];
 if(pose==='pull')lh=[69,72];
 if(pose==='turn')rh=[198+Math.cos(progress*Math.PI*1.6)*10,150+Math.sin(progress*Math.PI*1.6)*12];
 if(pose==='write')rh=[201,121+Math.sin(frame*.5)*4];
 lh=leftHand??lh;rh=rightHand??rh;
 const l=elbow([102,148+bounce],lh,-1),r=elbow([158,148+bounce],rh,1);
 const ankleL:Pt=[100+(walk?Math.sin(cycle)*19:0),285-(walk?Math.max(0,Math.cos(cycle))*13:0)];
 const ankleR:Pt=[160-(walk?Math.sin(cycle)*19:0),285-(walk?Math.max(0,-Math.cos(cycle))*13:0)];
 const blink=(frame+id.length*17)%157<5;const faceAngle=mood==='think'?-6:mood==='surprised'?3:Math.sin(frame*.05)*1.5;
 return <VisualObject id={id} kind="human-learner-puppet" box={[x-130*scale,y-296*scale,260*scale,320*scale]}>
 <svg viewBox="0 0 260 320" width="100%" height="100%" style={{overflow:'visible'}}>
 <ellipse cx="130" cy="301" rx={walk?49:57} ry="9" fill="#203f3720"/>
 <g transform={`translate(${tremble} ${held?0:bounce}) ${flip?'translate(260 0) scale(-1 1)':''}`}>
 <path d={`M113 215Q${ankleL[0]-9} 250 ${ankleL[0]} ${ankleL[1]}`} stroke={ink} strokeWidth="16" strokeLinecap="round" fill="none"/>
 <path d={`M148 215Q${ankleR[0]+9} 251 ${ankleR[0]} ${ankleR[1]}`} stroke={ink} strokeWidth="16" strokeLinecap="round" fill="none"/>
 <path d={`M${ankleL[0]-16} ${ankleL[1]+3}h32M${ankleR[0]-15} ${ankleR[1]+3}h33`} stroke="#3b6259" strokeWidth="16" strokeLinecap="round"/>
 <path d={`M102 ${148+bounce}Q${l.joint[0]} ${l.joint[1]} ${l.hand[0]} ${l.hand[1]}`} stroke={ink} strokeWidth="22" strokeLinecap="round" fill="none"/>
 <path d={`M102 ${148+bounce}Q${l.joint[0]} ${l.joint[1]} ${l.hand[0]} ${l.hand[1]}`} stroke={shirt} strokeWidth="15" strokeLinecap="round" fill="none"/>
 <path d={`M158 ${148+bounce}Q${r.joint[0]} ${r.joint[1]} ${r.hand[0]} ${r.hand[1]}`} stroke={ink} strokeWidth="22" strokeLinecap="round" fill="none"/>
 <path d={`M158 ${148+bounce}Q${r.joint[0]} ${r.joint[1]} ${r.hand[0]} ${r.hand[1]}`} stroke={shirt} strokeWidth="15" strokeLinecap="round" fill="none"/>
 <g transform={`rotate(${lean} 130 211)`}><path d="M103 130Q130 117 157 130Q169 156 173 213Q130 234 87 213Q90 157 103 130Z" fill={shirt} stroke={ink} strokeWidth="5" strokeLinejoin="round"/><path d="M118 137l12 17 12-17M130 155v28M112 199q18 14 36 0" stroke="#fff7e0" strokeWidth="5" strokeLinecap="round" fill="none"/><path d="M115 225v-10M144 225v-10" stroke={ink} strokeWidth="4"/></g>
 <g transform={`rotate(${faceAngle} 130 107)`}>
 <ellipse cx="130" cy="77" rx="43" ry="44" fill={skin} stroke={ink} strokeWidth="5"/>
 <path d="M88 71Q79 37 107 32Q114 14 132 28Q158 17 169 43Q178 51 171 72L157 52Q140 64 118 47L107 65Z" fill={ink}/>
 <ellipse cx="102" cy="93" rx="10" ry="5" fill="#eea88c" opacity=".6"/><ellipse cx="158" cy="93" rx="10" ry="5" fill="#eea88c" opacity=".6"/>
 {blink?<path d="M111 78h11m19 0h11" stroke={ink} strokeWidth="4" strokeLinecap="round"/>:<><ellipse cx={116+look*3} cy="78" rx="4.5" ry={mood==='surprised'?8:6.5} fill={ink}/><ellipse cx={145+look*3} cy="78" rx="4.5" ry={mood==='surprised'?8:6.5} fill={ink}/><circle cx={117+look*3} cy="76" r="1.5" fill="#fff"/><circle cx={146+look*3} cy="76" r="1.5" fill="#fff"/></>}
 {mood==='surprised'?<ellipse cx="131" cy="99" rx="6" ry="8" fill={ink}/>:mood==='worried'?<path d="M121 101q9-9 19 0" stroke={ink} strokeWidth="3.5" strokeLinecap="round"/>:<path d={mood==='think'?'M123 101q8-2 16 0':'M120 96q11 14 23 0'} stroke={ink} strokeWidth="3.5" strokeLinecap="round" fill="none"/>}
 {mood==='think'&&<path d="M108 65l15 3m16-5l14 3" stroke={ink} strokeWidth="3" strokeLinecap="round"/>}
 </g>
 <circle cx={l.hand[0]} cy={l.hand[1]} r="10" fill={skin} stroke={ink} strokeWidth="3"/>
 <circle cx={r.hand[0]} cy={r.hand[1]} r="10" fill={skin} stroke={ink} strokeWidth="3"/>
 </g></svg></VisualObject>;
};
