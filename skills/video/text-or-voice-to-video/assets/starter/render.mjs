import path from 'node:path';
import {mkdir,readFile,writeFile,rename} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderStill,renderMedia,openBrowser} from '@remotion/renderer';
import {fingerprint,scanSource,auditFrames,browserCollector,writeAudit,assertVisualApproval} from './visual-audit.mjs';
const root=process.cwd(),mode=process.argv[2]||'stills';
const gallery=mode==='gallery'||mode==='gallery-stills';
if(!['render','stills','audit','style','gallery','gallery-stills'].includes(mode))throw new Error('Unknown render mode');
const timeline=JSON.parse(await readFile('src/timeline.json','utf8'));
const id=process.env.VIDEO_COMPOSITION||(gallery?'RecipeGallery':'NarratedFilm');
const python=process.env.VIDEO_PYTHON||'python3';
const pipeline=(script,args)=>{const r=spawnSync(python,['pipeline/'+script,...args],{stdio:'inherit'});if(r.status!==0)throw new Error(script+' failed');};
if(!gallery)pipeline('compile_storyboard.py',['--timeline','src/timeline.json','--storyboard','src/storyboard.json','--assets','assets.json','--public-dir','public','--output','src/compiled-storyboard.json']);
const story=JSON.parse(await readFile('src/compiled-storyboard.json','utf8'));
let sourceFingerprint;
if(!gallery&&mode!=='style'){
 const violations=await scanSource(root);if(violations.length)throw new Error('Visual export blocked: '+violations.join('; '));
 sourceFingerprint=await fingerprint(root);
}
if(mode==='render')await assertVisualApproval(root,id,sourceFingerprint);
// Visual audit is independent of voice certification; final renders still require it.
if(['render','stills'].includes(mode))pipeline('validate_timeline.py',['--voice','public/audio/voice.wav','--timeline','src/timeline.json','--script','script.json']);
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts')});
const measured=['audit','render','stills'].includes(mode)&&!gallery;
const inputProps={visualAudit:measured};
const browser=await openBrowser('chrome',{chromiumOptions:{gl:'angle'}});
try{
const composition=await selectComposition({serveUrl,id,inputProps,puppeteerInstance:browser,chromiumOptions:{gl:'angle'}});
await mkdir('out/stills',{recursive:true});await mkdir('out/visual-audit',{recursive:true});
const frames=mode==='audit'?auditFrames(story):process.env.VIDEO_FRAMES?process.env.VIDEO_FRAMES.split(',').map(Number):gallery?Array.from({length:Math.ceil(composition.durationInFrames/120)},(_,i)=>Math.min(composition.durationInFrames-1,i*120+65)):timeline.scenes.flatMap(s=>[s.startFrame+Math.min(45,Math.floor((s.endFrame-s.startFrame)/2)),s.endFrame-8]).filter(f=>f>=0&&f<timeline.durationFrames);
if(frames.some(f=>!Number.isInteger(f)||f<0||f>=composition.durationInFrames))throw new Error('Requested still frame outside composition');
const snapshots=new Map(),issues=[],onBrowserLog=browserCollector(snapshots,issues);
if(['audit','stills','style','gallery-stills'].includes(mode)){
 for(const frame of frames){await renderStill({serveUrl,composition,inputProps,puppeteerInstance:browser,frame,output:mode==='audit'?`out/visual-audit/${id}-f${frame}.png`:`out/stills/${id}-f${frame}.png`,chromiumOptions:{gl:'angle'},onBrowserLog});console.log(`still ${frame}`);}
 if(mode==='audit'){
  const report=await writeAudit(root,composition,frames,story,snapshots,issues,sourceFingerprint);
  if(!report.passed)throw new Error('Visual audit failed: '+[...new Set(report.issues.map(i=>i.code))].join(', '));
  console.log('Structural visual audit passed. Inspect the images and write visual-review.json; this report is not aesthetic approval.');
 }else if(measured){
  for(const frame of frames)if(!snapshots.has(frame))issues.push({code:'missing-dom-audit',frame});
  if(issues.length)throw new Error('Still validation failed: '+[...new Set(issues.map(i=>i.code))].join(', '));
 }
}else{
 const candidate=gallery?(id==='RecipeGallery'?'out/recipe-gallery.mp4':`out/${id}.mp4`):'out/pending-visual.mp4';
 let lastProgress=-1;
 await renderMedia({serveUrl,composition,inputProps,puppeteerInstance:browser,outputLocation:candidate,codec:'h264',muted:true,crf:18,pixelFormat:'yuv420p',concurrency:Number(process.env.VIDEO_CONCURRENCY)||4,chromiumOptions:{gl:'angle'},onBrowserLog,
  onProgress:({progress})=>{const n=Math.floor(progress*10)*10;if(n>lastProgress){lastProgress=n;console.log(`Rendering ${n}%`);}}});
 if(!gallery){
  for(let f=0;f<composition.durationInFrames;f++)if(!snapshots.has(f))issues.push({code:'missing-dom-audit',frame:f});
  for(const s of snapshots.values()){
   const expected=story.shots.find(shot=>s.frame>=shot.startFrame&&s.frame<shot.endFrame);
   if(expected?.sceneId!==s.sceneId)issues.push({code:'scene-mismatch',frame:s.frame});
  }
  if(await fingerprint(root)!==sourceFingerprint)issues.push({code:'source-changed-during-render'});
  const report={passed:issues.length===0,compositionId:id,sourceFingerprint,expectedFrames:composition.durationInFrames,measuredFrames:snapshots.size,issues};
  await writeFile('out/visual-audit/full-render-report.json',JSON.stringify(report,null,2));
  if(!report.passed)throw new Error('Full-frame visual audit failed; pending-visual.mp4 is not a deliverable: '+[...new Set(issues.map(i=>i.code))].join(', '));
  await rename(candidate,'out/silent.mp4');
 }
 console.log('Silent video complete.');
}
await writeFile(`out/${mode}-metadata.json`,JSON.stringify({composition,frames},null,2));

}finally{await browser.close({silent:true});}
