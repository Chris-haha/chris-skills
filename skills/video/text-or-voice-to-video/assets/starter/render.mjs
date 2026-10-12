import path from 'node:path';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=process.cwd();const mode=process.argv[2]||'stills';
const timeline=JSON.parse(await readFile('src/timeline.json','utf8'));
if(mode!=='style') {const valid=spawnSync(process.env.VIDEO_PYTHON||'python3',['pipeline/validate_timeline.py','--voice','public/audio/voice.wav','--timeline','src/timeline.json','--script','script.json'],{stdio:'inherit'});if(valid.status!==0)throw new Error('Audio/timeline validation failed');}
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts')});
const composition=await selectComposition({serveUrl,id:'NarratedFilm',chromiumOptions:{gl:'angle'}});
await mkdir('out/stills',{recursive:true});
const frames=process.env.VIDEO_FRAMES?process.env.VIDEO_FRAMES.split(',').map(Number):timeline.scenes.flatMap(s=>[s.startFrame+Math.min(45,Math.floor((s.endFrame-s.startFrame)/2)),s.endFrame-8]).filter(f=>f>=0&&f<timeline.durationFrames);
if(mode==='stills'||mode==='style'){for(const frame of frames){await renderStill({serveUrl,composition,frame,output:`out/stills/f${frame}.png`,chromiumOptions:{gl:'angle'}});console.log(`still ${frame}`)}}
else{let lastProgress=-1;await renderMedia({serveUrl,composition,outputLocation:'out/silent.mp4',codec:'h264',muted:true,crf:18,pixelFormat:'yuv420p',concurrency:4,chromiumOptions:{gl:'angle'},onProgress:({progress})=>{const n=Math.floor(progress*10)*10;if(n>lastProgress){lastProgress=n;console.log(`Rendering ${n}%`)}}});console.log('\nSilent video complete.');}
await writeFile(`out/${mode}-metadata.json`,JSON.stringify({composition,frames},null,2));
