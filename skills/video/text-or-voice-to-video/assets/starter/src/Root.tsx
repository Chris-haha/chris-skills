import React from 'react';
import {Composition} from 'remotion';
import {NarratedFilm} from './Film';
import timeline from './timeline.json';
export const RemotionRoot: React.FC = () => <Composition id="NarratedFilm" component={NarratedFilm} width={1920} height={1080} fps={timeline.fps} durationInFrames={timeline.durationFrames} defaultProps={{}}/>;
