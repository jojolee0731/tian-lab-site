import test from 'node:test';
import assert from 'node:assert/strict';
import {blankProfile,normalizeProfile,normalizeDoi,safeLink,validateProfile,plainBibliographic,paperFromCrossref} from '../members/model.mjs';

const image='member-15/00000000-0000-4000-8000-000000000001.png';
const project=overrides=>({id:'project-1',title:'Research question',title_en:'',question:'',question_en:'',approach:'',approach_en:'',contribution:'',contribution_en:'',progress:'',progress_en:'',image_path:'',image_caption:'',image_caption_en:'',image_source:'',...overrides});
const paper=overrides=>({doi:'10.1000/example',title:'A published study',authors:'A Author; B Author',journal:'Journal',year:2026,context:'in_lab',contribution:'',contribution_en:'',...overrides});
const profile=overrides=>Object.assign(blankProfile(),overrides);

test('blank profiles do not share mutable arrays',()=>{
 const a=blankProfile(),b=blankProfile();a.projects.push(project());assert.deepEqual(b.projects,[]);assert.deepEqual(blankProfile().projects,[]);
});
test('normalization uses editable fields only and isolates nested draft records',()=>{
 const raw={bio:'Original',bio_en:3,role:'admin',projects:[project()],account:{email:'private@example.org'}};
 const normalized=normalizeProfile(raw);raw.projects[0].title='Changed';assert.equal(normalized.projects[0].title,'Research question');assert.equal(normalized.bio_en,'');assert.equal(normalized.role,undefined);assert.equal(normalized.account,undefined);
});
test('DOI identifiers, labels and resolver URLs normalize to one identity',()=>{
 for(const value of ['10.1000/ABC',' DOI: 10.1000/ABC ','https://doi.org/10.1000/ABC','http://dx.doi.org/10.1000/ABC','DOI: https://doi.org/10.1000/ABC'])assert.equal(normalizeDoi(value),'10.1000/abc');
 assert.equal(normalizeDoi('https://doi.org/10.1000/A%28B%29'),'10.1000/a(b)');
});
test('DOI query fragments, quotes, controls and foreign URLs are rejected',()=>{
 for(const value of ['10.1000/a?x=1','10.1000/a#part',"10.1000/a'b",'10.1000/a"b','10.1000/a\\b','10.1000/a b','javascript:alert(1)','https://elsewhere.example/10.1000/a','https://doi.org/10.1000/a?utm=x','https://doi.org/10.1000/%0a'])assert.throws(()=>normalizeDoi(value),value);
});
test('DOI suffix length follows the database limit',()=>{
 assert.equal(normalizeDoi('10.1000/'+'x'.repeat(240)).length,248);assert.throws(()=>normalizeDoi('10.1000/'+'x'.repeat(241)));
});
test('HTTPS and single-address mailto links are accepted',()=>{
 assert.equal(safeLink('https://example.org/path?q=1'),'https://example.org/path?q=1');assert.equal(safeLink('mailto:researcher+lab@example.org'),'mailto:researcher+lab@example.org');
});
test('unsafe or ambiguous external link forms are rejected',()=>{
 for(const value of ['javascript:alert(1)','data:text/html,x','http://example.org','//example.org','/local','https://user:pass@example.org','https://example.org/\n','https://example.org\\@evil.example','mailto:a@example.org?bcc=other@example.org','mailto:a%0dbcc@example.org','mailto:a%7fbcc@example.org'])assert.equal(safeLink(value),'',value);
});
test('all six long biography fields accept their boundary and reject overflow',()=>{
 for(const key of ['bio','bio_en','interests','interests_en','education','education_en']){assert.doesNotThrow(()=>validateProfile(profile({[key]:'字'.repeat(3000)})));assert.throws(()=>validateProfile(profile({[key]:'字'.repeat(3001)})));}
});
test('plain authored content preserves scientific inequalities but rejects HTML and controls',()=>{
 assert.doesNotThrow(()=>validateProfile(profile({bio:'Measured p <0.05; n >5.\nNext observation.'})));
 for(const bio of ['<script>bad()</script>','Text\u0000text','<b>Markup</b>'])assert.throws(()=>validateProfile(profile({bio})));
});
test('public email rejects control escapes without publishing login fields',()=>{
 assert.doesNotThrow(()=>validateProfile(profile({public_email:'researcher+lab@example.org'})));
 for(const public_email of ['invalid','a%0Abcc@example.org','a%0dbcc@example.org','a%7fbcc@example.org','x'.repeat(245)+'@example.org'])assert.throws(()=>validateProfile(profile({public_email})));
 assert.throws(()=>validateProfile({...profile(),account_email:'secret@example.org'}));
});
test('paper field limits preserve full long titles and fail on overflow',()=>{
 for(const [key,limit]of [['title',1000],['authors',2000],['journal',200],['contribution',3000],['contribution_en',3000]]){assert.doesNotThrow(()=>validateProfile(profile({papers:[paper({[key]:'x'.repeat(limit)})]})));assert.throws(()=>validateProfile(profile({papers:[paper({[key]:'x'.repeat(limit+1)})]})));}
});
test('paper identity, context, year and normalized duplicate checks prevent ambiguous submissions',()=>{
 for(const invalid of [{title:''},{authors:''},{journal:''},{context:'other'},{year:1899},{year:2026.5},{year:new Date().getFullYear()+2}])assert.throws(()=>validateProfile(profile({papers:[paper(invalid)]})));
 assert.throws(()=>validateProfile(profile({papers:[paper(),paper({doi:'HTTPS://DOI.ORG/10.1000/EXAMPLE'})]})));
 assert.equal(validateProfile(profile({papers:[paper({doi:'DOI: 10.1000/ABC',context:'before_lab'})]})).papers[0].doi,'10.1000/abc');
});
test('record count boundaries match project, paper and link contracts',()=>{
 for(const [key,max,maker]of [['projects',3,i=>project({id:'p'+i})],['papers',30,i=>paper({doi:'10.1000/p'+i})],['links',5,i=>({label:'Link '+i,url:'https://example.org/'+i})]]){assert.doesNotThrow(()=>validateProfile(profile({[key]:Array.from({length:max},(_,i)=>maker(i))})));assert.throws(()=>validateProfile(profile({[key]:Array.from({length:max+1},(_,i)=>maker(i))})));}
});
test('project title and text boundaries, unique IDs, and unknown fields are enforced',()=>{
 for(const [key,limit]of [['title',200],['title_en',200],['question',3000],['approach_en',3000],['image_source',3000]]){assert.doesNotThrow(()=>validateProfile(profile({projects:[project({[key]:'x'.repeat(limit)})]})));assert.throws(()=>validateProfile(profile({projects:[project({[key]:'x'.repeat(limit+1)})]})));}
 assert.throws(()=>validateProfile(profile({projects:[project(),project()]})));assert.throws(()=>validateProfile(profile({projects:[project({id:'../other'})]})));assert.throws(()=>validateProfile(profile({projects:[project({reviewed:true})]})));
});
test('project images require a caption in either language and an explicit source',()=>{
 assert.doesNotThrow(()=>validateProfile(profile({projects:[project({image_path:image,image_caption:'科研示意图',image_source:'本人绘制'})]})));
 assert.doesNotThrow(()=>validateProfile(profile({projects:[project({image_path:image,image_caption_en:'Research illustration',image_source:'Own work'})]})));
 for(const props of [{image_path:image},{image_path:image,image_caption:'Caption'},{image_path:image,image_source:'Source',image_caption:'  '}])assert.throws(()=>validateProfile(profile({projects:[project(props)]})));
});
test('draft image paths are private immutable upload names, never public or arbitrary URLs',()=>{
 assert.doesNotThrow(()=>validateProfile(profile({avatar_path:image})));
 for(const avatar_path of ['../file.png','https://example.org/a.png','assets/images/member-projects/member-15/a.png','member-15/file.svg','member-15/../member-16/file.png'])assert.throws(()=>validateProfile(profile({avatar_path})));
});
test('academic link labels and URLs obey length limits',()=>{
 assert.doesNotThrow(()=>validateProfile(profile({links:[{label:'x'.repeat(200),url:'https://example.org'}]})));
 assert.throws(()=>validateProfile(profile({links:[{label:'x'.repeat(201),url:'https://example.org'}]})));
 assert.throws(()=>validateProfile(profile({links:[{label:'x',url:'https://example.org/'+'a'.repeat(2048)}]})));
});
test('bibliographic cleanup removes real and encoded JATS while preserving scientific comparisons',()=>{
 assert.equal(plainBibliographic('<jats:italic>Aβ</jats:italic> &amp; p &lt;5'),'Aβ & p <5');
 assert.equal(plainBibliographic('&lt;i&gt;A&amp;B&lt;/i&gt;'),'A&B');
 assert.equal(plainBibliographic('&amp;lt;sub&amp;gt;2&amp;lt;/sub&amp;gt;'),'2');
 assert.equal(plainBibliographic('a <5 and b >2'),'a <5 and b >2');
 assert.equal(plainBibliographic('&beta; &#x03B1; &#946; &#0;'),'β α β');
});
test('Crossref parsing cleans titles, journal and individual/group authors',()=>{
 const p=paperFromCrossref({DOI:'10.1000/ABC',title:['<i>Aβ</i> <5'],author:[{given:'A &amp; B',family:'Author'},{name:'Research &amp; Imaging Consortium'}],'container-title':['<i>Journal</i> &amp; Review'],'published-online':{'date-parts':[[2025,12,1]]},'published-print':{'date-parts':[[2026,1,1]]}},'10.1000/abc');
 assert.equal(p.title,'Aβ <5');assert.equal(p.journal,'Journal & Review');assert.equal(p.authors,'A & B Author; Research & Imaging Consortium');assert.equal(p.year,2026);assert.equal(p.context,'in_lab');
 assert.doesNotThrow(()=>validateProfile(profile({papers:[p]})));
});
test('missing bibliographic facts remain empty and require review',()=>{
 const p=paperFromCrossref({},'10.1000/example');assert.equal(p.year,'');assert.equal(p.authors,'');assert.equal(p.title,'');assert.throws(()=>validateProfile(profile({papers:[p]})));
});

// Header-only fixtures exercise format dispatch and animation/dimension markers.
// Full image decoding is deliberately the responsibility of browser/export QA.
import {rasterHeaderError} from '../members/model.mjs';
function pngChunk(kind,data=[]){const body=Buffer.from(data),head=Buffer.alloc(8);head.writeUInt32BE(body.length);head.write(kind,4);return Buffer.concat([head,body,Buffer.alloc(4)]);}
function png(extra=[],width=1,height=1){const header=Buffer.alloc(13);header.writeUInt32BE(width);header.writeUInt32BE(height,4);header[8]=8;header[9]=6;return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),pngChunk('IHDR',header),...extra,pngChunk('IDAT',[1,2,3]),pngChunk('IEND')]);}
function webpChunk(kind,data=[]){const body=Buffer.from(data),head=Buffer.alloc(8);head.write(kind);head.writeUInt32LE(body.length,4);return Buffer.concat([head,body,Buffer.alloc(body.length%2)]);}
function webp(chunks){const body=Buffer.concat([Buffer.from('WEBP'),...chunks]),head=Buffer.alloc(8);head.write('RIFF');head.writeUInt32LE(body.length,4);return Buffer.concat([head,body]);}
function jpeg(width=1,height=1){return Buffer.from([0xff,0xd8,0xff,0xc0,0,11,8,height>>8,height&255,width>>8,width&255,1,1,0x11,0,0xff,0xda,0,8,1,1,0,0,63,0,0x12,0xff,0xd9]);}

test('raster headers recognize the three allowed static formats',()=>{
 assert.equal(rasterHeaderError(png(),'image/png'),'');assert.equal(rasterHeaderError(jpeg(),'image/jpeg'),'');assert.equal(rasterHeaderError(webp([webpChunk('VP8L',[0x2f,0,0,0,0])]),'image/webp'),'');
});
test('raster MIME mismatches, empty data, truncation and oversized files fail before upload',()=>{
 for(const [data,mime]of [[png(),'image/jpeg'],[Buffer.from('<svg/>'),'image/png'],[Buffer.alloc(0),'image/png'],[png().subarray(0,20),'image/png'],[Buffer.alloc(5*1024*1024+1),'image/png'],[png(),'image/gif']])assert.notEqual(rasterHeaderError(data,mime),'');
});
test('APNG chunks and both WebP animation markers are rejected',()=>{
 assert.match(rasterHeaderError(png([pngChunk('acTL',Buffer.alloc(8))]),'image/png'),/动画/);
 assert.match(rasterHeaderError(webp([webpChunk('ANIM',Buffer.alloc(6))]),'image/webp'),/动画/);
 const extended=Buffer.alloc(10);extended[0]=2;assert.match(rasterHeaderError(webp([webpChunk('VP8X',extended)]),'image/webp'),/动画/);
});
test('animation-like bytes inside PNG pixel chunks do not trigger substring false positives',()=>{
 assert.equal(rasterHeaderError(png([pngChunk('IDAT',Buffer.from('ordinary acTL bytes'))]),'image/png'),'');
});
test('header dimensions enforce the same 10000-pixel edge and 20MP export limits',()=>{
 assert.equal(rasterHeaderError(png([],10000,2000),'image/png'),'');assert.match(rasterHeaderError(png([],10001,1),'image/png'),/10000/);assert.match(rasterHeaderError(png([],5000,4001),'image/png'),/2000万/);assert.match(rasterHeaderError(jpeg(10001,1),'image/jpeg'),/10000/);
});
