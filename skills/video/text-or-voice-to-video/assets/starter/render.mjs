import path from 'node:path';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {bundle} from '@remotion/bundler';
import {selectComposition,renderStill,renderMedia} from '@remotion/renderer';
const root=process.cwd();const mode=process.argv[2]||'stills';
const gallery=mode==='gallery'||mode==='gallery-stills';
if(!['render','stills','style','gallery','gallery-stills'].includes(mode))throw new Error('Unknown render mode');
const timeline=JSON.parse(await readFile('src/timeline.json','utf8'));
if(mode!=='style'&&!gallery) {const valid=spawnSync(process.env.VIDEO_PYTHON||'python3',['pipeline/validate_timeline.py','--voice','public/audio/voice.wav','--timeline','src/timeline.json','--script','script.json'],{stdio:'inherit'});if(valid.status!==0)throw new Error('Audio/timeline validation failed');}
if(!gallery){const valid=spawnSync(process.env.VIDEO_PYTHON||'python3',['pipeline/compile_storyboard.py','--timeline','src/timeline.json','--storyboard','src/storyboard.json','--assets','assets.json','--public-dir','public','--output','src/compiled-storyboard.json'],{stdio:'inherit'});if(valid.status!==0)throw new Error('Visual storyboard/assets validation failed');}
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.ts')});
const id=process.env.VIDEO_COMPOSITION||(gallery?'RecipeGallery':'NarratedFilm');
const composition=await selectComposition({serveUrl,id,chromiumOptions:{gl:'angle'}});
await mkdir('out/stills',{recursive:true});
const frames=process.env.VIDEO_FRAMES?process.env.VIDEO_FRAMES.split(',').map(Number):gallery?Array.from({length:Math.ceil(composition.durationInFrames/120)},(_,i)=>Math.min(composition.durationInFrames-1,i*120+65)):timeline.scenes.flatMap(s=>[s.startFrame+Math.min(45,Math.floor((s.endFrame-s.startFrame)/2)),s.endFrame-8]).filter(f=>f>=0&&f<timeline.durationFrames);
if(frames.some(f=>!Number.isInteger(f)||f<0||f>=composition.durationInFrames))throw new Error('Requested still frame outside composition');
if(mode==='stills'||mode==='style'||mode==='gallery-stills'){for(const frame of frames){await renderStill({serveUrl,composition,frame,output:`out/stills/${id}-f${frame}.png`,chromiumOptions:{gl:'angle'}});console.log(`still ${frame}`)}}
else{let lastProgress=-1;await renderMedia({serveUrl,composition,outputLocation:gallery?(id==='RecipeGallery'?'out/recipe-gallery.mp4':`out/${id}.mp4`):'out/silent.mp4',codec:'h264',muted:true,crf:18,pixelFormat:'yuv420p',concurrency:Number(process.env.VIDEO_CONCURRENCY)||4,chromiumOptions:{gl:'angle'},onProgress:({progress})=>{const n=Math.floor(progress*10)*10;if(n>lastProgress){lastProgress=n;console.log(`Rendering ${n}%`)}}});console.log('\nSilent video complete.');}
await writeFile(`out/${mode}-metadata.json`,JSON.stringify({composition,frames},null,2));
