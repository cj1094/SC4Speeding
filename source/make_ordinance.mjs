// Follow Null 45's tutorial using its Space Exploration example as the template.
// Build dependency: sc4@0.2.24 (MIT); set SC4_LIBRARY_ROOT to its installed folder.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
const lib=process.env.SC4_LIBRARY_ROOT;
if(!lib)throw Error('Set SC4_LIBRARY_ROOT to the installed sc4@0.2.24 package directory.');
const {default:DBPF}=await import(pathToFileURL(path.join(lib,'lib/core/dbpf.js')));
const {Exemplar}=await import(pathToFileURL(path.join(lib,'lib/core/exemplar.js')));
const template=new DBPF(path.join(here,'reference/SpaceExplorationProgramOrdinance.dat'));
const original=template.entries.find(e=>e.type===0x6534284a);
const exemplar=new Exemplar(original.decompress());
const keep=new Set([0x10,0x20,0x28ebbc30,0x28ebbc37,0x28ebbc38,0x28ebbc39,0x6a416b21,0xca416b2a]);
const nameKey=[0x2026960b,0x18ed0359,0xf5ee0201];
const descriptionKey=[0x2026960b,0x18ed0359,0xf5ee0202];
const values=new Map([[0x20,'Ordinance - Speed Traps'],[0x28ebbc30,0xf5ee0200],
 [0x28ebbc37,0],[0x28ebbc38,0],[0x28ebbc39,-60],[0x6a416b21,nameKey],[0xca416b2a,descriptionKey]]);
const props=exemplar.properties.filter(p=>keep.has(p.id)).map(p=>({id:p.id,type:p.type,value:values.has(p.id)?values.get(p.id):p.value}));
// Host availability conditions are ANDed; income factors add signed income.
props.push(
 {id:0xaa5b8407,type:'Sint32',value:5},
 {id:0x6b23d823,type:'Uint32',value:1},
 {id:0x6b23d800,type:'Uint32',value:1000},
 {id:0x6b23d803,type:'Uint32',value:100},
 {id:0x6b23d923,type:'Float32',value:-10},
);
const result=new Exemplar({parent:exemplar.parent,properties:props});
function ltext(s){const b=Buffer.alloc(4+s.length*2);b.writeUInt32LE(0x10000000+s.length);b.write(s,4,'utf16le');return b;}
const out=new DBPF();
out.add([0x6534284a,original.group,0xf5ee0200],result,{compressed:true});
out.add(nameKey,ltext('Speed Traps'),{compressed:true});
out.add(descriptionKey,ltext('Speeding deterrent for cities.'),{compressed:true});
const dest=path.join(here,'build/140-ordinances/SC4Speeding-SpeedTraps.dat');
fs.mkdirSync(path.dirname(dest),{recursive:true});
const archive=out.toBuffer();
// Keep a complete 1 KiB archive extent; resource offsets/index remain unchanged.
const padded=Buffer.alloc(Math.max(1024,archive.length));padded.set(archive);
fs.writeFileSync(dest,padded);
console.log('Built from upstream example: unique ordinance and two LTEXTs; $60 + $10 per police station expense; +5 mayor rating; police/R$/CS$ prerequisites.');
