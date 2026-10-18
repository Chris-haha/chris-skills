import path from 'node:path';
import {readFile,readdir,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {auditSnapshot} from './src/visual/quality.mjs';

export const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
export async function fingerprint(root){
 const files=[];
 const walk=async(dir)=>{for(const entry of await readdir(path.join(root,dir),{withFileTypes:true})){const rel=path.join(dir,entry.name);if(entry.isDirectory())await walk(rel);else if(entry.isFile())files.push(rel);}};
 await walk('src');await walk('public');
 files.push('render.mjs','visual-audit.mjs','package.json','assets.json','script.json');
 const records={};for(const file of files.sort())records[file]=hash(await readFile(path.join(root,file)));
 return hash(JSON.stringify(records));
}
export async function scanSource(root){
 const ts=createRequire(path.join(root,'package.json'))('typescript'),violations=[];
 const walk=async(dir)=>{for(const entry of await readdir(path.join(root,dir),{withFileTypes:true})){
  const rel=path.join(dir,entry.name);if(entry.isDirectory()){await walk(rel);continue;}
  if(!/\.tsx?$/.test(rel)||rel.startsWith(path.join('src','visual')))continue;
  const file=ts.createSourceFile(rel,await readFile(path.join(root,rel),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
  const bad=name=>/^(?:robot|bot)(?:head|face|icon|avatar|mascot)?$/i.test(name)||/generic.?ai.?icon/i.test(name);
  const visit=node=>{
   if((ts.isFunctionDeclaration(node)||ts.isClassDeclaration(node)||ts.isVariableDeclaration(node))&&node.name&&bad(node.name.getText(file)))violations.push(`${rel}: generic AI mascot declaration ${node.name.getText(file)}`);
   if((ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node))&&bad(node.tagName.getText(file)))violations.push(`${rel}: generic AI mascot JSX`);
   if(ts.isJsxAttribute(node)&&['name','kind','icon','type'].includes(node.name.getText(file))&&node.initializer){
    let value=node.initializer;if(ts.isJsxExpression(value)&&value.expression)value=value.expression;
    if(ts.isStringLiteral(value)&&bad(value.text))violations.push(`${rel}: forbidden placeholder ${value.text}`);
   }
   ts.forEachChild(node,visit);
  };visit(file);
 }};
 await walk('src');return violations;
}
export function auditFrames(story){
 const frames=new Set();
 for(const shot of story.shots){
  const add=f=>frames.add(Math.max(shot.startFrame,Math.min(shot.endFrame-1,Math.round(f))));
  add(shot.startFrame);add((shot.startFrame+shot.endFrame)/2);add(shot.endFrame-1);
  for(const e of shot.events){add(e.frame);add(e.frame+e.durationFrames/2);add(e.frame+e.durationFrames);}
 }
 return [...frames].sort((a,b)=>a-b);
}
export function browserCollector(snapshots,issues){
 return log=>{
  const index=log.text.indexOf('VISUAL_AUDIT:');if(index<0)return;
  const snapshot=JSON.parse(log.text.slice(index+'VISUAL_AUDIT:'.length));
  if(snapshots.has(snapshot.frame)){
   if(JSON.stringify(snapshots.get(snapshot.frame))!==JSON.stringify(snapshot))issues.push({code:'conflicting-frame-audits',frame:snapshot.frame,detail:'Multiple or unstable audit roots reported different layouts for one composition frame'});
   return;
  }
  snapshots.set(snapshot.frame,snapshot);issues.push(...auditSnapshot(snapshot));
 };
}
export async function writeAudit(root,composition,frames,story,snapshots,issues,sourceFingerprint){
 const frameRecords=[];
 for(const frame of frames){
  const screenshot=`out/visual-audit/${composition.id}-f${frame}.png`;
  if(!snapshots.has(frame))issues.push({code:'missing-dom-audit',frame,detail:'Composition must retain root AuditComposition; unmeasured custom components cannot pass'});
  const expected=story.shots.find(s=>frame>=s.startFrame&&frame<s.endFrame);
  if(snapshots.has(frame)&&snapshots.get(frame).sceneId!==expected?.sceneId)issues.push({code:'scene-mismatch',frame,detail:'Audit scene does not match the actual timeline interval'});
  frameRecords.push({frame,screenshot,sha256:hash(await readFile(path.join(root,screenshot))),snapshot:snapshots.get(frame)??null});
 }
 const expectedScenes=new Set(story.shots.map(s=>s.sceneId));
 for(const s of snapshots.values())if(!expectedScenes.has(s.sceneId))issues.push({code:'scene-mismatch',frame:s.frame,detail:`Unknown scene ${s.sceneId}`});
 const report={schemaVersion:1,compositionId:composition.id,width:composition.width,height:composition.height,sourceFingerprint,
  passed:issues.length===0,issues,frames:frameRecords,expectedScenes:[...expectedScenes],
  scope:'Measured rendered DOM and visible SVG paths at shot/event boundary, midpoint and settled frames; image semantics and aesthetics require the separate visual review.'};
 await mkdir(path.join(root,'out/visual-audit'),{recursive:true});
 const file=path.join(root,`out/visual-audit/${composition.id}-report.json`);
 await writeFile(file,JSON.stringify(report,null,2));return report;
}
export async function assertVisualApproval(root,id,currentFingerprint){
 const reportFile=path.join(root,`out/visual-audit/${id}-report.json`),reviewFile=path.join(root,'visual-review.json');
 let raw,report,review;
 try{raw=await readFile(reportFile);report=JSON.parse(raw);review=JSON.parse(await readFile(reviewFile));}
 catch{throw new Error('Visual export blocked: run node render.mjs audit, inspect the images, and record visual-review.json first');}
 if(report.compositionId!==id||!report.passed||report.sourceFingerprint!==currentFingerprint)throw new Error('Visual export blocked: visual audit failed or is stale for this composition/source');
 for(const f of report.frames)if(hash(await readFile(path.join(root,f.screenshot)))!==f.sha256)throw new Error('Visual export blocked: reviewed screenshot changed');
 const required=['noGenericAiMascots','relationshipsHaveMeaning','noUnwantedOverlaps','badgePlacement','readableHierarchy'];
 if(review.auditSha256!==hash(raw)||!required.every(key=>review.checks?.[key]===true))throw new Error('Visual export blocked: missing/stale visual review or unresolved design checks');
 for(const sceneId of report.expectedScenes){
  const scene=review.scenes?.find(s=>s.sceneId===sceneId);
  if(scene?.decision!=='pass'||!scene.reason?.trim()||!scene.frames?.length)throw new Error(`Visual export blocked: ${sceneId} needs a concrete image review`);
  if(scene.frames.some(frame=>!report.frames.some(f=>f.frame===frame&&f.snapshot?.sceneId===sceneId)))throw new Error(`Visual export blocked: review frames do not belong to ${sceneId}`);
  const requiredFrames=report.frames.filter(f=>f.snapshot?.sceneId===sceneId).map(f=>f.frame);
  if(requiredFrames.some(frame=>!scene.frames.includes(frame)))throw new Error(`Visual export blocked: ${sceneId} review omits action/settled evidence`);
 }
 return report;
}
