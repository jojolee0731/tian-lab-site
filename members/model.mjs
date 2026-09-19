// Shared pure model: keep limits aligned with member_portal.validate_payload
// and scripts/member_profile.py. Authentication/ownership is enforced by RPCs.
export const EMPTY_PROFILE = Object.freeze({bio:'',bio_en:'',interests:'',interests_en:'',education:'',education_en:'',public_email:'',avatar_path:'',links:[],projects:[],papers:[]});
const LONG_FIELDS=['bio','bio_en','interests','interests_en','education','education_en'];
const PROJECT_FIELDS=['id','title','title_en','question','question_en','approach','approach_en','contribution','contribution_en','progress','progress_en','image_path','image_caption','image_caption_en','image_source'];
const PAPER_FIELDS=['doi','title','authors','journal','year','context','contribution','contribution_en'];
const EMAIL=/^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$/;
const CONTROLS=/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;
const HTML=/<\s*\/?[a-z!][^>]*>/i;
const PRIVATE_IMAGE=/^member-\d{2,}\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp)$/;
const chars=value=>[...value].length;

export function blankProfile(){return structuredClone(EMPTY_PROFILE);}

export function normalizeDoi(value){
  let s=String(value||'').trim().replace(/^doi:\s*/i,'');
  if(/^https?:\/\/(?:dx\.)?doi\.org\//i.test(s)){
    try{const u=new URL(s);if(u.search||u.hash)throw new Error();s=decodeURIComponent(u.pathname.slice(1));}
    catch{throw new Error('DOI链接不能包含查询参数、锚点或无效编码。');}
  }
  if(chars(s)>255||!/^10\.\d{4,9}\/[^\s?#<>"'\\]{1,240}$/i.test(s))throw new Error('请输入有效的 DOI，例如 10.1000/example。');
  return s.toLowerCase();
}

function encodedControls(value){
  // A mail client decodes percent escapes, even though the visible text is safe.
  return /%(?:0[0-9a-f]|1[0-9a-f]|7f)/i.test(value);
}

export function safeLink(value){
  if(typeof value!=='string'||chars(value)>2048||/[\s\\<>]/.test(value))return '';
  try{
    const u=new URL(value);
    if(u.protocol==='mailto:')return !u.search&&!u.hash&&EMAIL.test(u.pathname)&&!encodedControls(u.pathname)?u.href:'';
    if(u.protocol!=='https:'||u.username||u.password||!u.hostname)return '';
    // The SQL allowlist uses ASCII DNS hostnames (IDNs normalize to punycode).
    if(!/^[a-z0-9][a-z0-9.-]*$/i.test(u.hostname))return '';
    return u.href;
  }catch{return '';}
}

export function normalizeProfile(value){
  const p=blankProfile();
  for(const key of Object.keys(p))p[key]=Array.isArray(p[key])?(Array.isArray(value?.[key])?structuredClone(value[key]):[]):(typeof value?.[key]==='string'?value[key]:'');
  return p;
}

function plain(value,label,limit=3000){
  if(value===undefined)return '';
  if(typeof value!=='string'||chars(value)>limit||CONTROLS.test(value)||HTML.test(value))throw new Error(`${label}需为纯文本，且不能超过${limit}字。`);
  return value;
}
function allowed(object,keys,label){
  if(!object||typeof object!=='object'||Array.isArray(object)||Object.keys(object).some(key=>!keys.includes(key)))throw new Error(`${label}包含无效字段。`);
}
function imagePath(value){
  plain(value,'图片路径',150);
  if(value&&!PRIVATE_IMAGE.test(value))throw new Error('图片路径无效，请重新上传图片。');
}

export function validateProfile(p){
  allowed(p,Object.keys(EMPTY_PROFILE),'个人资料');
  for(const key of LONG_FIELDS)plain(p[key],'个人介绍');
  const address=plain(p.public_email,'公开邮箱',254);
  if(address&&(!EMAIL.test(address)||encodedControls(address)))throw new Error('请填写有效的公开邮箱，或留空。');
  imagePath(p.avatar_path);
  for(const[key,max]of [['projects',3],['papers',30],['links',5]])if(!Array.isArray(p[key])||p[key].length>max)throw new Error('最多3项项目、30篇论文及5个链接。');
  const papers=new Set();
  for(const paper of p.papers){
    allowed(paper,PAPER_FIELDS,'论文');
    for(const key of PAPER_FIELDS.filter(k=>k!=='year'))plain(paper[key],'论文字段 '+key,({title:1000,authors:2000,journal:200,doi:255,context:150})[key]||3000);
    paper.doi=normalizeDoi(paper.doi);
    if(papers.has(paper.doi))throw new Error('同一篇论文只需添加一次。');
    papers.add(paper.doi);
    if(!paper.title?.trim()||!paper.journal?.trim()||!paper.authors?.trim())throw new Error('请补全论文题名、期刊和作者。');
    if(!['in_lab','before_lab'].includes(paper.context))throw new Error('请选择论文的成果背景。');
    if(!Number.isInteger(paper.year)||paper.year<1900||paper.year>new Date().getFullYear()+1)throw new Error('请核对论文正式发表年份。');
  }
  for(const link of p.links){
    allowed(link,['label','url'],'学术链接');
    plain(link.label,'链接名称',200);plain(link.url,'链接地址',2048);
    if(!link.label?.trim()||!safeLink(link.url))throw new Error('学术链接需填写名称及完整的 HTTPS 地址或邮箱链接。');
    link.url=safeLink(link.url);
  }
  const projectIds=new Set();
  for(const item of p.projects){
    allowed(item,PROJECT_FIELDS,'科研项目');
    for(const key of PROJECT_FIELDS)plain(item[key],'项目字段 '+key,({id:80,title:200,title_en:200,image_path:150})[key]||3000);
    if(!/^[A-Za-z0-9_-]{1,80}$/.test(item.id||'')||projectIds.has(item.id))throw new Error('项目标识无效或重复，请重新添加该项目。');
    projectIds.add(item.id);
    if(!item.title?.trim())throw new Error('请为每个项目填写名称。');
    imagePath(item.image_path);
    if(item.image_path&&(!(item.image_caption?.trim()||item.image_caption_en?.trim())||!item.image_source?.trim()))throw new Error('项目配图需要图注与来源。');
  }
  return p;
}

const ENTITIES={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' ',ndash:'–',mdash:'—',alpha:'α',beta:'β',gamma:'γ',delta:'δ',mu:'μ',sigma:'σ',Alpha:'Α',Beta:'Β',Gamma:'Γ',Delta:'Δ',Sigma:'Σ'};
function decodeEntities(value){
  return value.replace(/&([a-z]+|#\d+|#x[0-9a-f]+);/gi,(all,entity)=>{
    if(Object.hasOwn(ENTITIES,entity))return ENTITIES[entity];
    if(!entity.startsWith('#'))return all;
    const n=entity[1]?.toLowerCase()==='x'?parseInt(entity.slice(2),16):parseInt(entity.slice(1),10);
    return n>0&&n<=0x10ffff&&!(n>=0xd800&&n<=0xdfff)?String.fromCodePoint(n):'';
  });
}
export function plainBibliographic(value){
  let text=String(value??'');
  // Decode before removing markup, so encoded JATS/HTML cannot reappear later.
  for(let i=0;i<6;i++){const next=decodeEntities(text);if(next===text)break;text=next;}
  return text.replace(/<!--[\s\S]*?-->/g,'').replace(/<\/?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>]*?)?\s*\/?>/g,'').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'').trim();
}
export function paperFromCrossref(record,requestedDoi){
  const dates=record['published-print']?.['date-parts']||record['published-online']?.['date-parts']||record.published?.['date-parts'];
  return {doi:normalizeDoi(record.DOI||requestedDoi),title:plainBibliographic(record.title?.[0]),authors:(record.author||[]).map(a=>plainBibliographic(a.name||[a.given,a.family].filter(Boolean).join(' '))).join('; '),journal:plainBibliographic(record['container-title']?.[0]),year:dates?.[0]?.[0]||'',context:'in_lab',contribution:'',contribution_en:''};
}

// Fast metadata check before browser decoding. This is not a substitute for
// createImageBitmap or the server's full decode/re-encode validation.
export function rasterHeaderError(bytes,mime){
  let b;
  if(bytes instanceof ArrayBuffer)b=new Uint8Array(bytes);
  else if(ArrayBuffer.isView(bytes))b=new Uint8Array(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  else return '无法读取图片文件。';
  const type={'image/jpeg':'JPEG','image/png':'PNG','image/webp':'WebP'}[mime];
  if(!type)return '仅支持 JPG、PNG 或 WebP图片。';
  if(!b.length||b.length>5*1024*1024)return '图片应大于0字节且不超过5 MB。';
  const ascii=(at,n)=>String.fromCharCode(...b.subarray(at,at+n));
  const be16=at=>(b[at]<<8)|b[at+1];
  const be32=at=>(b[at]*0x1000000)+(b[at+1]<<16)+(b[at+2]<<8)+b[at+3];
  const le16=at=>b[at]|(b[at+1]<<8);
  const le24=at=>b[at]|(b[at+1]<<8)|(b[at+2]<<16);
  const le32=at=>(b[at]|(b[at+1]<<8)|(b[at+2]<<16)|(b[at+3]<<24))>>>0;
  const dimensions=(w,h)=>!w||!h?'图片尺寸无效。':Math.max(w,h)>10000||w*h>20000000?'图片最长边不能超过10000像素，总像素不能超过2000万。':'';
  const broken='图片文件头不完整或格式与文件类型不一致，请重新导出图片。';
  const animated='暂不支持动画图片，请上传单帧 JPG、PNG 或 WebP。';
  if(mime==='image/png'){
    if(b.length<33||!b.subarray(0,8).every((v,i)=>v===[137,80,78,71,13,10,26,10][i]))return broken;
    let at=8,first=true,hasData=false;
    while(at+12<=b.length){
      const length=be32(at),kind=ascii(at+4,4),body=at+8,end=body+length;
      if(end+4>b.length)return broken;
      if(first){if(kind!=='IHDR'||length!==13)return broken;const error=dimensions(be32(body),be32(body+4));if(error)return error;first=false;}
      if(['acTL','fcTL','fdAT'].includes(kind))return animated;
      if(kind==='IDAT')hasData=true;
      if(kind==='IEND')return length===0&&hasData?'':broken;
      at=end+4;
    }
    return broken;
  }
  if(mime==='image/webp'){
    if(b.length<20||ascii(0,4)!=='RIFF'||ascii(8,4)!=='WEBP')return broken;
    const end=le32(4)+8;if(end>b.length||end<20)return broken;
    let at=12,hasPixels=false;
    while(at+8<=end){
      const kind=ascii(at,4),length=le32(at+4),body=at+8,next=body+length+(length%2);
      if(next>end)return broken;
      if(kind==='ANIM'||kind==='ANMF')return animated;
      if(kind==='VP8X'){
        if(length!==10)return broken;if(b[body]&2)return animated;
        const error=dimensions(le24(body+4)+1,le24(body+7)+1);if(error)return error;
      }else if(kind==='VP8L'){
        if(length<5||b[body]!==0x2f)return broken;
        const bits=le32(body+1),error=dimensions((bits&0x3fff)+1,((bits>>>14)&0x3fff)+1);if(error)return error;hasPixels=true;
      }else if(kind==='VP8 '){
        if(length<10||b[body+3]!==0x9d||b[body+4]!==1||b[body+5]!==0x2a)return broken;
        const error=dimensions(le16(body+6)&0x3fff,le16(body+8)&0x3fff);if(error)return error;hasPixels=true;
      }
      at=next;
    }
    return at===end&&hasPixels?'':broken;
  }
  if(b.length<4||b[0]!==0xff||b[1]!==0xd8)return broken;
  let at=2,hasDimensions=false;
  while(at<b.length){
    if(b[at++]!==0xff)return broken;
    while(at<b.length&&b[at]===0xff)at++;
    const marker=b[at++];if(marker===undefined||marker===0xd9)return broken;
    if(marker===0x01||(marker>=0xd0&&marker<=0xd7))continue;
    if(at+2>b.length)return broken;
    const length=be16(at);if(length<2||at+length>b.length)return broken;
    if([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker)){
      if(length<8)return broken;const error=dimensions(be16(at+5),be16(at+3));if(error)return error;hasDimensions=true;
    }
    if(marker===0xda)return hasDimensions&&at+length<b.length?'':broken;
    at+=length;
  }
  return broken;
}
