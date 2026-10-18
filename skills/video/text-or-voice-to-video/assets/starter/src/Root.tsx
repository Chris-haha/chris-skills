import React from 'react';
import {Composition,useCurrentFrame} from 'remotion';
import {NarratedFilm} from './VisualFilm';
import {RecipeGallery} from './motion/Gallery';
import {LibraryExample} from './motion/LibraryExample';
import timeline from './timeline.json';
import storyboard from './compiled-storyboard.json';
import {AuditComposition} from './visual/Visual';
const AuditedFilm:React.FC=()=>{
 const frame=useCurrentFrame();
 const shot=(storyboard.shots as {sceneId:string;startFrame:number;endFrame:number;layoutIntent?:string}[]).find(s=>frame>=s.startFrame&&frame<s.endFrame);
 return <AuditComposition id={shot?.sceneId??'unmapped'} intent={shot?.layoutIntent??'unclassified'}><NarratedFilm/></AuditComposition>;
};
export const RemotionRoot: React.FC = () => <><Composition id="NarratedFilm" component={AuditedFilm} width={1920} height={1080} fps={timeline.fps} durationInFrames={timeline.durationFrames} defaultProps={{}}/><Composition id="NarratedFilmPortrait" component={AuditedFilm} width={1080} height={1920} fps={timeline.fps} durationInFrames={timeline.durationFrames}/><Composition id="RecipeGallery" component={RecipeGallery} width={1920} height={1080} fps={30} durationInFrames={960}/><Composition id="RecipeGalleryPortrait" component={RecipeGallery} width={1080} height={1920} fps={30} durationInFrames={960}/><Composition id="LibraryExample" component={LibraryExample} width={1920} height={1080} fps={30} durationInFrames={240}/></>;
