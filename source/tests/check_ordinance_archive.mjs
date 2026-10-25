// Separate DBPF/exemplar reader check, using sc4@0.2.24.
import assert from 'node:assert/strict';import path from 'node:path';import {pathToFileURL,fileURLToPath} from 'node:url';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const {default:DBPF}=await import(pathToFileURL(path.join(process.env.SC4_LIBRARY_ROOT,'lib/core/dbpf.js')));
const {Exemplar}=await import(pathToFileURL(path.join(process.env.SC4_LIBRARY_ROOT,'lib/core/exemplar.js')));
const d=new DBPF(path.join(root,'build/140-ordinances/SC4Speeding-SpeedTraps.dat'));
const en=d.entries.find(e=>e.type===0x6534284a);assert.equal(en.instance,0xf5ee0200);
const e=new Exemplar(en.decompress());const p=new Map(e.properties.map(p=>[p.id,p.value]));
assert.equal(p.get(0x10),14);assert.equal(p.get(0x28ebbc39),-60);
for(const id of [0x6b23d823,0x6b23d800,0x6b23d803])assert.equal(p.get(id),1);
assert.equal(p.get(0xaa5b8407),5);assert.equal(p.get(0x6b23d923),-10);
for(const stations of [0,1,2,10,100])assert.equal(-(p.get(0x28ebbc39)+stations*p.get(0x6b23d923)),60+stations*10);
assert.equal(p.get(0x28ebbc37),0);assert.equal(p.get(0x28ebbc38),0);
for(const [key,text] of [[0x6a416b21,'Speed Traps'],[0xca416b2a,'Speeding deterrent for cities.']]){
 const value=Buffer.from(d.entries.find(...p.get(key)).decompress());
 assert.equal(value.readUInt32LE(0),0x10000000+text.length);
 assert.equal(value.subarray(4).toString('utf16le'),text);
}
assert.equal(d.entries.filter(x=>x.type===0x6534284a).length,1);
assert.equal(d.entries.filter(x=>x.type===0x2026960b).length,2);
assert(d.entries.some(x=>x.type===0xe86b1eef));
console.log('PASS: sc4@0.2.24 reads one type14 exemplar, exact LTEXT keys/texts, base cost, police station multiplier, eligibility thresholds, mayor rating and compressed-resource directory.');
