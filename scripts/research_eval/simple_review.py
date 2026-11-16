"""A small, offline human-review screen using the existing gold-review contract."""


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Artint · Quick review</title><style>
:root{color-scheme:light;--bg:#f7f8f5;--panel:#fff;--ink:#25382e;--muted:#526758;--line:#d6dfd5;--accent:#285447;--tint:#eaf2ed;--warn:#885c1c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 system-ui,sans-serif}header,main{max-width:1140px;margin:auto;padding:24px}header{padding-bottom:12px}h1{font-size:32px;line-height:1.2;margin:8px 0}h2{font-size:21px;line-height:1.45;margin:6px 0 20px}h3{font-size:15px;margin:0 0 8px}p{margin:8px 0 16px}.muted{color:var(--muted);font-size:14px}.toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap}button,input,textarea{font:inherit;color:inherit;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:9px 14px}button{cursor:pointer}button:hover{border-color:var(--accent)}button:disabled{opacity:.45;cursor:default}button:focus-visible,input:focus-visible,textarea:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #3972ad;outline-offset:3px}.primary{background:var(--accent);color:#fff}.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:24px;margin:22px 0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:28px}.quote{white-space:pre-wrap;border-left:3px solid var(--line);padding-left:14px;margin:10px 0 16px;font-size:15px;overflow-wrap:anywhere}.source-name{font-size:13px;color:var(--muted);overflow-wrap:anywhere}ul{padding-left:20px;margin:0 0 16px}details{margin:14px 0}summary{cursor:pointer;color:var(--accent)}.source-copy{white-space:pre-wrap;overflow-wrap:anywhere;max-height:420px;overflow:auto;padding:16px;background:var(--bg);border:1px solid var(--line);border-radius:6px;font-size:15px}mark{background:#f5e09b;color:#25251b}textarea{width:100%;min-height:76px;resize:vertical}.checks{display:flex;gap:10px;align-items:flex-start;font-size:14px;margin:16px 0}.checks input{margin-top:6px;flex:none}.actions{padding-top:18px;border-top:1px solid var(--line)}.actions button[aria-pressed=true]{outline:2px solid var(--accent);outline-offset:2px;background:var(--tint)}.state{font-size:14px;color:var(--muted);margin-top:12px;min-height:23px}.warning{color:var(--warn)}#status{min-height:26px}.progress-track{height:5px;background:var(--line);border-radius:4px;overflow:hidden;margin:14px 0}.progress-fill{height:100%;background:var(--accent);transition:width .2s ease}#position{flex:1;text-align:center}.footer{text-align:center;margin:36px 0;color:var(--muted);font-size:14px}a{color:var(--accent)}[hidden]{display:none!important}
@media(max-width:720px){header,main{padding:16px}.card{padding:18px}.columns{grid-template-columns:1fr;gap:18px}h1{font-size:27px}.actions button{flex:1;min-width:130px}.toolbar input{max-width:100%}#position{flex-basis:100%;order:-1}}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#151b17;--panel:#1c2520;--ink:#e5e9df;--muted:#b2bdac;--line:#3d4c40;--accent:#a2c8a6;--tint:#2b4232;--warn:#e1ba75}.primary{background:#426d52;color:#fff}mark{background:#6b5927;color:#fff3c9}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head><body><header>
<div class="muted">ARTINT · QUICK REVIEW</div><h1>Does the source support this answer?</h1>
<p class="muted">Read the question, compare the answer with the saved article, then choose below. Start with these five; you can stop whenever you want.</p>
<p class="muted">These are draft test cases. Some include unrelated stories to check whether search ignores them. Their inclusion does not mean the stories are connected.</p>
<div class="toolbar"><label>Your name <input id="reviewer" maxlength="100" placeholder="Your name" autocomplete="name"></label><button id="export" class="primary">Save progress</button><button id="import">Resume from file</button><input id="import-file" type="file" accept="application/json" hidden></div>
<div class="progress-track"><div id="bar" class="progress-fill"></div></div><div id="progress" class="muted" aria-live="polite"></div>
<p id="status" class="muted" role="status" aria-live="polite"></p>
</header><main><div id="cases"></div><nav class="toolbar" aria-label="Review pages"><button id="previous">Previous five</button><span id="position" class="muted"></span><button id="next" class="primary">Next five</button></nav>
<p class="footer">Your review stays on this device. “Save progress” downloads a backup you can reopen here.<br>Advanced editing and checking related articles can wait. <a href="batch-review.html">Open detailed review</a></p>
</main><script type="application/json" id="payload">PAYLOAD_JSON</script><script>
(()=>{'use strict';
const data=JSON.parse(document.getElementById('payload').textContent),corpus=data.corpus,proposals=data.suggestions.judgments;
const originals=new Map(corpus.cases.map(c=>[c.id,c])),sources=new Map(corpus.sources.map(s=>[s.id,s]));
const $=id=>document.getElementById(id),clone=v=>JSON.parse(JSON.stringify(v)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const storageKey='artint-quick-review-v1-'+data.review.proposal_sha256,limit=5;
let review=clone(data.review),page=0,dirty=false;
function status(text,error=false){$('status').textContent=text;$('status').className=error?'warning':'muted'}
function validate(next){
 if(!next||next.proposal_sha256!==data.review.proposal_sha256||!Array.isArray(next.judgments)||next.judgments.length!==proposals.length)throw Error('This file belongs to a different set of questions.');
 if(typeof next.reviewer!=='string'||typeof next.source_grouping_reviewed!=='boolean'||!next.source_story_groups||Array.isArray(next.source_story_groups)||!same(Object.keys(next.source_story_groups).sort(),[...sources.keys()].sort())||Object.values(next.source_story_groups).some(v=>typeof v!=='string'||!v))throw Error('This progress file has invalid article information.');
 next.judgments.forEach((r,i)=>{const p=proposals[i],o=originals.get(p.case_id),c=r.case;
  if(r.case_id!==p.case_id||r.case_sha256!==p.case_sha256||!['pending','accept','revise','exclude'].includes(r.decision)||typeof r.notes!=='string'||!c||['id','source_ids','split','label'].some(k=>!same(c[k],o[k]))||typeof c.question!=='string'||!['answerable','unanswerable'].includes(c.answerability)||['required_facts','evidence','acceptable_sets','tags'].some(k=>!Array.isArray(c[k]))||c.required_facts.some(f=>!f||typeof f.text!=='string')||c.evidence.some(e=>!e||typeof e.quote!=='string'||!sources.has(e.source_id)))throw Error('This progress file has an invalid question.');
 });
}
function persist(){
 review.reviewer=$('reviewer').value.trim();const done=review.judgments.some(r=>r.decision!=='pending');
 review.review_kind=done?'human':'unreviewed';review.reviewed_at=done?new Date().toISOString():'';
 try{localStorage.setItem(storageKey,JSON.stringify({review,page}));dirty=false;status('Progress saved in this browser. Use Save progress for a backup file.');}
 catch(e){dirty=true;status('Browser saving is unavailable. Use Save progress before closing this page.',true);}
 updateProgress();
}
function updateProgress(){const done=review.judgments.filter(r=>r.decision!=='pending').length,followup=review.judgments.filter(r=>r.decision==='pending'&&/^\[(Needs changes|Not sure)\]/.test(r.notes)).length;
 $('progress').textContent=done+' of '+proposals.length+' confirmed'+(followup?' · '+followup+' left for follow-up':'');$('bar').style.width=100*done/proposals.length+'%';
 $('position').textContent='Questions '+(page*limit+1)+'–'+Math.min((page+1)*limit,proposals.length)+' of '+proposals.length;
 $('previous').disabled=page===0;$('next').disabled=(page+1)*limit>=proposals.length;
}
function candidate(i){const r=review.judgments[i],o=originals.get(r.case_id);return ['accept','revise'].includes(r.decision)||!same(r.case,o)?r.case:proposals[i].case;}
function markedCopy(s,spans){const div=node('div',undefined,'source-copy'),chars=Array.from(s.text);let cursor=0;
 for(const e of spans.filter(e=>Number.isInteger(e.start)&&Number.isInteger(e.end)&&e.start>=0&&e.end>e.start&&e.end<=chars.length&&chars.slice(e.start,e.end).join('')===e.quote).sort((a,b)=>a.start-b.start)){
  if(e.end<=cursor)continue;div.append(document.createTextNode(chars.slice(cursor,Math.max(cursor,e.start)).join('')),node('mark',chars.slice(Math.max(cursor,e.start),e.end).join('')));cursor=e.end;
 }div.append(document.createTextNode(chars.slice(cursor).join('')));return div;
}
function render(){const root=$('cases');root.replaceChildren();
 for(let i=page*limit;i<Math.min((page+1)*limit,proposals.length);i++){
  const p=proposals[i],r=review.judgments[i],c=candidate(i),card=node('article',undefined,'card');card.dataset.caseId=p.case_id;
  card.append(node('div','QUESTION '+(i+1),'muted'),node('h2',c.question));
  const columns=node('div',undefined,'columns'),answer=node('div'),evidence=node('div');answer.append(node('h3','Expected answer'));
  if(c.answerability==='unanswerable')answer.append(node('p','These saved articles do not contain enough information to answer this question.'),node('p','To confirm this, read every selected article below. A short excerpt cannot prove information is missing.','warning'));
  else {const facts=node('ul');for(const f of c.required_facts)facts.append(node('li',f.text));answer.append(facts);}
  if(p.suggested_action==='check'&&c.answerability!=='unanswerable')answer.append(node('p','Check that the saved articles are complete enough to use. If something looks missing or unrelated, choose Needs changes.','warning'));
  evidence.append(node('h3','From the saved article'));
  for(const e of c.evidence){const s=sources.get(e.source_id);evidence.append(node('div',s.title,'source-name'),node('div',e.quote,'quote'));}
  if(!c.evidence.length)evidence.append(node('p','Open the articles below to check.','muted'));
  columns.append(answer,evidence);card.append(columns);
  const other=node('details'),otherIds=c.source_ids.filter(id=>sources.get(id).story_group!==c.story_group);
  other.append(node('summary','Other stories in this test ('+otherIds.length+')'),node('p','These copies test whether retrieval ignores unrelated stories. They are not evidence of a connection. For missing-answer checks, read these too. Story groups are still proposed, not human-approved.','muted'));
  for(const id of c.source_ids){const s=sources.get(id),d=node('details');d.append(node('summary','Read article: '+s.title),node('p',s.url,'source-name'),markedCopy(s,c.evidence.filter(e=>e.source_id===id)));(s.story_group===c.story_group?card:other).append(d);}
  if(otherIds.length)card.append(other);
  const notes=node('textarea');notes.placeholder='Optional: tell me what looks wrong';notes.setAttribute('aria-label','Notes for question '+(i+1));notes.value=r.notes.replace(/^\[(Needs changes|Not sure)\]\s*/, '');
  notes.oninput=()=>{const prefix=r.decision==='pending'?(r.notes.match(/^\[(Needs changes|Not sure)\]/)||[''])[0]:'';r.notes=(prefix?prefix+' ':'')+notes.value;persist()};card.append(notes);
  let confirmed=null;
  if(p.suggested_action==='check'||c.answerability==='unanswerable'){const label=node('label',undefined,'checks');confirmed=node('input');confirmed.type='checkbox';confirmed.setAttribute('aria-label','I checked all selected articles for question '+(i+1));label.append(confirmed,document.createTextNode('I read all selected articles and checked that the saved copies are usable.'));card.append(label);}
  const actions=node('div',undefined,'toolbar actions'),state=node('div',undefined,'state');state.setAttribute('role','status');
  const choices=[['correct','Looks correct'],['changes','Needs changes'],['unsure','Not sure']];
  const buttons=[];
  function showState(){const approved=['accept','revise'].includes(r.decision),choice=approved?'correct':r.decision==='pending'&&r.notes.startsWith('[Needs changes]')?'changes':r.decision==='pending'&&r.notes.startsWith('[Not sure]')?'unsure':'';
   buttons.forEach(([kind,b])=>b.setAttribute('aria-pressed',String(kind===choice)));
   state.textContent=approved?'Confirmed by you.':r.decision==='exclude'?'Excluded in the detailed review.':choice==='changes'?'Left pending — your notes will help us fix it.':choice==='unsure'?'Left pending — we can come back to this.':'Waiting for your review.';
  }
  for(const [kind,text] of choices){const b=node('button',text);b.type='button';b.onclick=()=>{
   if(kind==='correct'){
    if(!$('reviewer').value.trim()){status('Enter your name at the top first.',true);$('reviewer').focus();return;}
    if(confirmed&&!confirmed.checked){state.textContent='Read all selected articles and tick the check above before confirming.';state.classList.add('warning');return;}
    r.case=clone(c);r.decision=same(c,originals.get(r.case_id))?'accept':'revise';r.notes=notes.value;
   }else {r.decision='pending';r.notes='['+(kind==='changes'?'Needs changes':'Not sure')+']'+(notes.value.trim()?' '+notes.value:'');}
   state.classList.remove('warning');showState();persist();
  };buttons.push([kind,b]);actions.append(b);}
  const reset=node('button','Undo');reset.onclick=()=>{r.decision='pending';r.notes=notes.value;showState();persist();};actions.append(reset);showState();card.append(actions,state);root.append(card);
 }updateProgress();
}
for(const [id,offset] of [['previous',-1],['next',1]])$(id).onclick=()=>{page+=offset;render();persist();window.scrollTo(0,0)};
$('reviewer').oninput=persist;
$('export').onclick=()=>{if(review.judgments.some(r=>r.decision!=='pending')&&!$('reviewer').value.trim()){status('Enter your name before saving confirmed decisions.',true);$('reviewer').focus();return;}persist();const url=URL.createObjectURL(new Blob([JSON.stringify(review,null,2)+'\n'],{type:'application/json'})),a=node('a');a.href=url;a.download='artint-review-progress.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status('Progress file downloaded. Keep it; use Resume from file whenever you need it.');};
$('import').onclick=()=>$('import-file').click();$('import-file').onchange=async()=>{try{
 const file=$('import-file').files[0];if(!file)return;if(file.size>64*1024*1024)throw Error('This file is too large.');
 const next=JSON.parse(await file.text());validate(next);
 if(review.judgments.some(r=>r.decision!=='pending'||r.notes)&&!window.confirm('Replace the progress currently on this page with this file?'))return;
 review=clone(next);page=0;$('reviewer').value=review.reviewer;render();persist();status('Your saved progress is loaded.');
 }catch(e){status('Could not load progress: '+e.message,true);}finally{$('import-file').value='';}};
try{const saved=localStorage.getItem(storageKey);if(saved){const value=JSON.parse(saved);validate(value.review);review=clone(value.review);page=Number.isInteger(value.page)?Math.max(0,Math.min(Math.ceil(proposals.length/limit)-1,value.page)):0;status('Your previous progress was restored from this browser.');}}
catch(e){status('Browser progress could not be loaded. You can use Resume from file.',true);}
$('reviewer').value=review.reviewer;render();
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
})();</script></body></html>'''
