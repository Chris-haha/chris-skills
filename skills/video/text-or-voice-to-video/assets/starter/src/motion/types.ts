export type Recipe='assemble'|'path'|'state'|'link'|'focus'|'parallax'|'compare'|'patch';
export type VisualEvent={id:string;unitId:string;subjectId:string;action:string;edge?:'start'|'end';offsetMs?:number;durationMs:number;frame:number;durationFrames:number};
export type Shot={id:string;sceneId:string;goal:string;media:'illustration'|'screen'|'diagram'|'type';recipe:Recipe;subjects:string[];assetIds:string[];events:VisualEvent[];holdMs:number;startFrame:number;endFrame:number;transition:{kind:string};content?:{heading?:string;nodes?:{label:string;body?:string}[]}};
export type CompiledStory={schemaVersion:number;shots:Shot[]};
