import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {hash,fingerprint,assertVisualApproval,auditFrames} from './visual-audit.mjs';

async function fixture(){
 const root=await mkdtemp(path.join(os.tmpdir(),'video-visual-guard-'));
 for(const dir of ['src','public','out/visual-audit'])await mkdir(path.join(root,dir),{recursive:true});
 for(const file of ['render.mjs','visual-audit.mjs','package.json','assets.json','script.json','src/Episode.tsx','public/illustration.png'])await writeFile(path.join(root,file),'fixture');
 const screenshot='out/visual-audit/NarratedFilm-f30.png';await writeFile(path.join(root,screenshot),'measured still fixture');
 const report={passed:true,compositionId:'NarratedFilm',sourceFingerprint:await fingerprint(root),expectedScenes:['s1'],
  frames:[{frame:30,screenshot,sha256:hash(await readFile(path.join(root,screenshot))),snapshot:{sceneId:'s1'}}]};
 const raw=JSON.stringify(report);await writeFile(path.join(root,'out/visual-audit/NarratedFilm-report.json'),raw);
 const review={auditSha256:hash(raw),checks:{noGenericAiMascots:true,relationshipsHaveMeaning:true,noUnwantedOverlaps:true,badgePlacement:true,readableHierarchy:true},scenes:[{sceneId:'s1',decision:'pass',frames:[30],reason:'Inspected actual prompt paper, reserved status area and unobstructed directional relation'}]};
 await writeFile(path.join(root,'visual-review.json'),JSON.stringify(review));
 return {root,review,screenshot,cleanup:()=>rm(root,{recursive:true,force:true})};
}
test('missing approval blocks a final render',async()=>{
 const f=await fixture();try{await rm(path.join(f.root,'visual-review.json'));await assert.rejects(assertVisualApproval(f.root,'NarratedFilm',await fingerprint(f.root)),/blocked/);}finally{await f.cleanup();}
});
test('approval becomes stale after editing any visual source or public asset',async()=>{
 const f=await fixture();try{await writeFile(path.join(f.root,'src/Episode.tsx'),'changed layout');await assert.rejects(assertVisualApproval(f.root,'NarratedFilm',await fingerprint(f.root)),/stale/);}finally{await f.cleanup();}
});
test('a replaced reviewed screenshot cannot reuse approval',async()=>{
 const f=await fixture();try{await writeFile(path.join(f.root,f.screenshot),'other image');await assert.rejects(assertVisualApproval(f.root,'NarratedFilm',await fingerprint(f.root)),/screenshot changed/);}finally{await f.cleanup();}
});
test('the review must inspect evidence from every actual scene',async()=>{
 const f=await fixture();try{f.review.scenes[0].frames=[31];await writeFile(path.join(f.root,'visual-review.json'),JSON.stringify(f.review));await assert.rejects(assertVisualApproval(f.root,'NarratedFilm',await fingerprint(f.root)),/do not belong/);}finally{await f.cleanup();}
});
test('current explicit visual evidence passes',async()=>{
 const f=await fixture();try{await assertVisualApproval(f.root,'NarratedFilm',await fingerprint(f.root));}finally{await f.cleanup();}
});
test('automatic sampling covers each action at start, midpoint and end',()=>{
 const frames=auditFrames({shots:[{startFrame:0,endFrame:120,events:[{frame:20,durationFrames:20}]}]});
 for(const frame of [0,20,30,40,60,119])assert.ok(frames.includes(frame));
});
