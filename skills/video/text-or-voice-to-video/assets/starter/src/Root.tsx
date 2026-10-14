import React from 'react';
import {Composition} from 'remotion';
import {NarratedFilm} from './VisualFilm';
import {RecipeGallery} from './motion/Gallery';
import {LibraryExample} from './motion/LibraryExample';
import timeline from './timeline.json';
export const RemotionRoot: React.FC = () => <><Composition id="NarratedFilm" component={NarratedFilm} width={1920} height={1080} fps={timeline.fps} durationInFrames={timeline.durationFrames} defaultProps={{}}/><Composition id="NarratedFilmPortrait" component={NarratedFilm} width={1080} height={1920} fps={timeline.fps} durationInFrames={timeline.durationFrames}/><Composition id="RecipeGallery" component={RecipeGallery} width={1920} height={1080} fps={30} durationInFrames={960}/><Composition id="RecipeGalleryPortrait" component={RecipeGallery} width={1080} height={1920} fps={30} durationInFrames={960}/><Composition id="LibraryExample" component={LibraryExample} width={1920} height={1080} fps={30} durationInFrames={240}/></>;
