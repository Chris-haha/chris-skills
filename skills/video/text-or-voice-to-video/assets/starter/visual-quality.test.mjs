import test from 'node:test';
import assert from 'node:assert/strict';
import {auditSnapshot, connectorPoints} from './src/visual/quality.mjs';

const object=(id,box,kind='receipt')=>({id,box,kind});
const text=(id,box)=>({id,box,text:id});
const snapshot=(extra={})=>({frame:40,sceneId:'s1',intent:'flow',width:1000,height:600,previewOnly:false,
 objects:[object('request',[40,240,180,110]),object('result',[650,240,250,110])],
 texts:[text('request-label',[60,270,130,36]),text('result-label',[680,270,150,36])],
 connectors:[],badges:[],unmanaged:[],...extra});
const edge=(extra={})=>({id:'send',source:'request',target:'result',relationship:'flow',meaning:'把清单送到接收处',
 points:[[232,295],[638,295]],progress:1,arrow:true,...extra});
const codes=s=>auditSnapshot(s).map(i=>i.code);

test('a generic robot AI placeholder is rejected',()=>{
 assert.ok(codes(snapshot({objects:[object('ai',[40,240,180,110],'generic-ai-robot')]})).includes('generic-ai-mascot'));
});
test('directional relations require a visible arrow',()=>{
 assert.ok(codes(snapshot({connectors:[edge({arrow:false})]})).includes('missing-arrow'));
});
test('a line crossing visible text is rejected, including animation frames',()=>{
 assert.ok(codes(snapshot({texts:[text('feedback',[330,270,180,45])],connectors:[edge({progress:.5})]})).includes('line-over-text'));
});
test('floating endpoints and unowned decorative lines fail',()=>{
 assert.ok(codes(snapshot({connectors:[edge({points:[[300,400],[580,400]]})]})).includes('detached-endpoint'));
 assert.ok(codes(snapshot({unmanaged:[{kind:'unmanaged-line',box:[300,300,150,4]}]})).includes('unmanaged-line'));
});
test('a status badge must belong to a real object and avoid text',()=>{
 const badge={id:'error',owner:'result',box:[885,270,45,45],text:'未通过'};
 assert.ok(codes(snapshot({badges:[badge]})).includes('badge-outside-owner'));
 assert.ok(codes(snapshot({badges:[{...badge,box:[700,270,90,45]}]})).includes('badge-over-text'));
 assert.ok(codes(snapshot({badges:[{...badge,owner:'missing'}]})).includes('badge-missing-owner'));
});
test('classification fan-out is not silently accepted as a process diagram',()=>{
 assert.ok(codes(snapshot({connectors:[edge({relationship:'classification'})]})).includes('unsupported-relationship'));
});
test('text overlap, overflow and a starter preview cannot certify delivery',()=>{
 assert.ok(codes(snapshot({texts:[text('a',[20,20,180,40]),text('b',[100,30,180,40])]})).includes('text-overlap'));
 assert.ok(codes(snapshot({texts:[text('a',[900,550,180,80])]})).includes('outside-canvas'));
 assert.ok(codes(snapshot({previewOnly:true})).includes('preview-only'));
});
test('a meaningful boundary-to-boundary arrow with clear labels passes',()=>{
 assert.deepEqual(auditSnapshot(snapshot({connectors:[edge()]})),[]);
});
test('a non-directional association is valid only when explicitly declared',()=>{
 assert.deepEqual(auditSnapshot(snapshot({connectors:[edge({relationship:'association',arrow:false})]})),[]);
});
test('connector ports use object boundaries rather than text centers',()=>{
 const points=connectorPoints({id:'a',box:[20,40,180,100],port:'right'},
 {id:'b',box:[500,240,200,100],port:'left'});
 assert.deepEqual(points[0],[212,90]);assert.deepEqual(points.at(-1),[488,290]);
});
test('overlapping spans inside the same label are still an error',()=>{
 assert.ok(codes(snapshot({texts:[{...text('label',[20,20,180,40]),rangeId:'a'},{...text('label',[100,30,180,40]),rangeId:'b'}]})).includes('text-overlap'));
});
test('renaming a classification edge to association does not bypass a fan-out check',()=>{
 const s=snapshot({objects:[...snapshot().objects,object('third',[650,430,250,110])],connectors:[edge({relationship:'association',arrow:false}),edge({id:'other',target:'third',relationship:'association',arrow:false,points:[[232,295],[638,485]]})]});
 assert.ok(codes(s).includes('branched-connector'));
 assert.ok(codes(snapshot({intent:'classification',connectors:[edge()]})).includes('unnecessary-classification-lines'));
});
test('future undrawn connectors do not require objects that have not appeared',()=>{
 const s=snapshot({objects:[],connectors:[edge({progress:0,points:[],arrow:false}),edge({id:'later',target:'other',progress:0,points:[],arrow:false})]});
 assert.deepEqual(auditSnapshot(s),[]);
});

import {intersectBoxes,insetClipBounds} from './src/visual/quality.mjs';
test('fully clipped text has no visible collision bounds',()=>{
 assert.equal(intersectBoxes([50,50,180,40],insetClipBounds([50,50,900,500],'inset(0px 100% 0px 0px)')),null);
});
test('complementary wipe regions keep only disjoint visible text fragments',()=>{
 const b=[50,50,900,500],t=[50,50,900,40];
 const before=intersectBoxes(t,insetClipBounds(b,'inset(0 0 0 50%)'));
 const after=intersectBoxes(t,insetClipBounds(b,'inset(0 50% 0 0)'));
 assert.deepEqual(before,[500,50,450,40]);assert.deepEqual(after,[50,50,450,40]);
 assert.equal(intersectBoxes(before,after),null);
});
