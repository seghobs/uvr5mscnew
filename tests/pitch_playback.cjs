const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ts=require('../frontend/node_modules/typescript');
const source=fs.readFileSync('frontend/src/components/StemAudioPlayer.tsx','utf8');
const tree=ts.createSourceFile('player.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let callback;
function visit(node){if(ts.isVariableDeclaration(node)&&node.name.getText(tree)==='updateLivePlayback')callback=node.initializer.arguments[0].getText(tree);ts.forEachChild(node,visit);}visit(tree);
let rate,preserve;
const ctx={wsRef:{current:{setPlaybackRate(r,p){rate=r;preserve=p;}}}};vm.createContext(ctx);
vm.runInContext(ts.transpile('globalThis.update='+callback,{target:ts.ScriptTarget.ES2020}),ctx);
for(const pitch of [-12,-3,0,9,11,12])for(const tempo of [.5,.55,1,2]){
 ctx.update(pitch,tempo);assert.equal(rate,tempo);assert.equal(preserve,true);
}
assert.ok(source.includes("runAudioJob"));
assert.ok(!source.includes('tempo * pitchRatio'));
console.log('PASS: all notes use exactly the selected tempo with pitch preservation');
