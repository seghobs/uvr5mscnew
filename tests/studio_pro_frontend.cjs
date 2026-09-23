const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ts=require('../frontend/node_modules/typescript');
const studioPro=require('../frontend/src/lib/studio-pro-preset.json');
const file=ts.createSourceFile('preset.tsx',fs.readFileSync('frontend/src/components/ModelConfiguration.tsx','utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let handler;
function visit(n){if(ts.isVariableDeclaration(n)&&n.name.getText(file)==='applyPreset') handler=n.initializer.getText(file);ts.forEachChild(n,visit);}visit(file);
let slots,params,format,notification;
const atlasStudio=require('../frontend/src/lib/atlas-studio-preset.json');
const context={studioPro,atlasStudio,ensembleMode:true,params:{ensemble_profile:'studio_pro'},
 availableModels:{roformer:studioPro.models.filter(m=>m.model_type==='roformer').map(m=>m.model_key),mdx23c:studioPro.models.filter(m=>m.model_type==='mdx23c').map(m=>m.model_key)},
 onToggleEnsembleMode:()=>{},onChangeEnsembleSlots:s=>slots=s,onChangeParams:p=>params=p,onChangeOutputFormat:f=>format=f,onNotify:(...n)=>notification=n};
vm.createContext(context);vm.runInContext(ts.transpile('globalThis.applyPreset='+handler,{target:ts.ScriptTarget.ES2020}),context);
context.applyPreset('studio_pro');
assert.equal(slots.length,4);assert.equal(params.ensemble_profile,'studio_pro');assert.equal(format,'flac');
context.applyPreset('atlas_studio');
assert.equal(slots.length,3);assert.equal(params.ensemble_profile,'atlas_studio');assert.equal(format,'wav');
assert.equal(params.overlap,8);assert.equal(params.amplification_threshold,0);
context.applyPreset('master_studio');assert.equal(slots.length,3);assert.equal(params.ensemble_profile,undefined);
context.availableModels.roformer=[];slots=null;context.applyPreset('studio_pro');assert.equal(slots,null);assert.equal(notification[0],'warning');
context.applyPreset('atlas_studio');assert.equal(slots,null);assert.equal(notification[0],'warning');
console.log('PASS: new preset, exact model selection, legacy preset preserved, profile reset, missing models');
