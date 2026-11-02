"""Offline batch review of AI suggestions; decisions remain human and explicit."""
import copy
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from scripts.research_eval.contracts import (
    EvaluationError, SHA, IDENTIFIER, obj, array, string, digest, encoded,
    load_corpus, read_json, validate_corpus, write_json,
)
from scripts.research_eval.development import prepare_gold_review


SUGGESTIONS_SCHEMA = obj(dict(
    schema_version=dict(const=1), authoring_kind=dict(const='ai_assisted'), proposal_sha256=SHA,
    judgments=array(obj(dict(case_id=IDENTIFIER, case_sha256=SHA,
        suggested_action=dict(enum=['keep', 'revise', 'check']),
        priority=dict(enum=['normal', 'high']), notes=string(4000), case=dict(type='object'))), 60, 1)))


def validate_suggestions(corpus, suggestions):
    if list(Draft202012Validator(SUGGESTIONS_SCHEMA).iter_errors(suggestions)):
        raise EvaluationError('Batch suggestions schema failed.')
    if corpus['kind'] != 'development' or any(c['label']['kind'] != 'unreviewed' for c in corpus['cases']):
        raise EvaluationError('Batch review needs an unreviewed development proposal.')
    if suggestions['proposal_sha256'] != digest(encoded(corpus)):
        raise EvaluationError('Batch suggestions belong to a changed or different corpus.')
    originals = {c['id']: c for c in corpus['cases']}
    rows = suggestions['judgments']
    if len(rows) != len(originals) or {r['case_id'] for r in rows} != set(originals):
        raise EvaluationError('Batch suggestions must retain every case exactly once.')
    by_id = {r['case_id']: r for r in rows}
    candidate = copy.deepcopy(corpus)
    for index, original in enumerate(corpus['cases']):
        row = by_id[original['id']]
        if row['case_sha256'] != digest(encoded(original)):
            raise EvaluationError('A batch case fingerprint is stale.')
        edited = row['case']
        if any(edited.get(key) != original[key] for key in ('id', 'source_ids', 'split', 'label')):
            raise EvaluationError('Batch suggestions cannot alter case identity, scope, split or label.')
        if edited.get('eligible') != original['eligible'] or edited.get('exclusion_reason') != original['exclusion_reason']:
            raise EvaluationError('Exclusions require an explicit human decision, not a proposed hidden exclusion.')
        if row['suggested_action'] == 'keep' and edited != original:
            raise EvaluationError('Changed cases must use revise or check.')
        if row['suggested_action'] == 'revise' and edited == original:
            raise EvaluationError('A revise suggestion must actually change the case.')
        if edited.get('answerability') == 'unanswerable' and row['suggested_action'] != 'check':
            raise EvaluationError('Proposed absence labels must retain the full-source check flag.')
        candidate['cases'][index] = copy.deepcopy(edited)
    validate_corpus(candidate)
    return [by_id[c['id']] for c in corpus['cases']]


def prepare_batch_review(corpus_path, suggestions_path, output):
    corpus = load_corpus(corpus_path)
    suggestions = read_json(suggestions_path, 16 * 1024 * 1024)
    rows = validate_suggestions(corpus, suggestions)
    # Validate everything before creating the new destination. Existing packets
    # and the original proposal are never overwritten.
    output = Path(output)
    prepare_gold_review(corpus_path, output)
    review = read_json(output / 'gold-review.json')
    suggestions = dict(suggestions, judgments=rows)
    write_json(output / 'suggestions.json', suggestions)
    payload = json.dumps(dict(corpus=corpus, review=review, suggestions=suggestions), ensure_ascii=False).replace('<', '\\u003c')
    (output / 'batch-review.html').write_text(PAGE.replace('PAYLOAD_JSON', payload), encoding='utf-8')
    counts = dict(Counter(r['suggested_action'] for r in rows))
    result = dict(cases=len(rows), source_families=len({c['story_group'] for c in corpus['cases']}),
        suggested_actions=counts, high_priority=sum(r['priority'] == 'high' for r in rows),
        human_labels_created=0, quality_gate='not_established', output=str(output))
    write_json(output / 'batch-summary.json', result)
    (output / 'START_HERE.md').write_text(
        '# Batch review\n\nOpen `batch-review.html` in a browser. All cases start pending. '
        'Read the original/proposed comparisons and linked full saved copies, then select the cases you have checked. '
        'Record selected suggestions together, or exclude them with a reason. Flagged cases need an explicit full-scope confirmation. '
        'Enter your own reviewer name; download review JSON to save progress and load it here to resume. '
        'There is no automatic saving or server.\n\n'
        'Family grouping is a separate check and is never confirmed automatically. '
        'The download uses the existing gold-review format; apply it to a NEW corpus through `apply-gold-review` only after '
        'all cases and grouping have actually been reviewed. AI suggestions are not human approvals or quality scores.\n',
        encoding='utf-8')
    return result


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Artint · Batch evidence review</title>
<style>
:root{color-scheme:light;--bg:#f7f8f5;--panel:#fff;--ink:#25382e;--muted:#526758;--line:#d6dfd5;--accent:#285447;--warn:#885c1c}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);font:15px/1.6 system-ui,sans-serif}
header,main{max-width:1500px;margin:auto;padding:24px}header{border-bottom:1px solid var(--line)}h1{font-size:28px;margin:0}h2{font-size:20px}h3{font-size:16px;margin:8px 0}p{color:var(--muted)}
button,input,select,textarea{font:inherit;color:inherit}button,select,input[type=checkbox]{cursor:pointer}button,input,select,textarea{background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:8px 12px}button:hover{border-color:var(--accent)}button:disabled{opacity:.5;cursor:default}button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #3972ad;outline-offset:2px}
.primary{background:var(--accent);color:white}.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.toolbar label{display:flex;gap:8px;align-items:center}.summary{display:flex;gap:24px;flex-wrap:wrap;margin:20px 0}.summary strong{font-size:23px;display:block}.summary span{color:var(--muted);font-size:13px}.panel{background:var(--panel);padding:18px;border:1px solid var(--line);border-radius:7px;margin:16px 0}.warning{color:var(--warn)}#message{min-height:24px}#message:empty{display:none}input[type=search]{flex:1;min-width:260px;max-width:480px}a{color:var(--accent);overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{font-size:13px;color:var(--muted)}th:first-child{width:64px}th:nth-child(2){width:20%}th:nth-child(3){width:37%}.group td{background:var(--bg);padding:10px 12px}.group label{font-weight:600}.meta{color:var(--muted);font-size:12px}.notes{margin-top:10px;font-size:13px}ul{padding-left:20px;margin:6px 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:16px}.quote{white-space:pre-wrap;border-left:3px solid var(--line);padding-left:12px;font-size:13px;margin:8px 0}.case-editor{width:100%;min-height:200px;font:12px/1.5 ui-monospace,monospace}.user-notes{width:100%;min-height:70px;margin-top:8px;font-size:13px}.source-copy{white-space:pre-wrap;overflow-wrap:anywhere;max-height:600px;overflow:auto;font-size:14px;padding:16px;background:var(--bg)}summary{cursor:pointer}details{margin-top:10px}textarea{max-width:100%}.family-editor{width:100%;min-height:220px;font:13px/1.5 ui-monospace,monospace}.source{scroll-margin-top:20px}[hidden]{display:none!important}
@media(max-width:760px){header,main{padding:16px}thead{display:none}table,tbody,tr,td{display:block;width:100%}td{padding:10px 12px;border:0}tr:not(.group){border:1px solid var(--line);margin:12px 0;border-radius:6px}td:first-child{padding-bottom:0}.compare{grid-template-columns:1fr}.toolbar{gap:10px}input[type=search]{width:100%;min-width:0;max-width:none}}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#151b17;--panel:#1c2520;--ink:#e5e9df;--muted:#a5b09c;--line:#354237;--accent:#a2c8a6;--warn:#e1ba75}.primary{background:#426d52;color:white}}
</style></head><body>
<header><div class="meta">ARTINT · DEVELOPMENT EVIDENCE</div><h1>Review the batch</h1>
<p>Compare all proposed cases together. AI suggestions remain separate from your decisions. Nothing is sent to a server; download JSON to save progress.</p>
<div class="summary"><div><strong id="total"></strong><span>proposed cases</span></div><div><strong id="suggested"></strong><span>suggested revisions</span></div><div><strong id="flagged"></strong><span>need source checks</span></div><div><strong id="progress" aria-live="polite"></strong><span>human decisions recorded</span></div></div>
<div class="toolbar"><label>Reviewer <input id="reviewer" maxlength="100" autocomplete="off" placeholder="Your name"></label><button id="export" class="primary">Download review JSON</button><button id="import">Load saved review</button><input id="import-file" type="file" accept="application/json" hidden></div>
<p id="message" role="status" aria-live="polite"></p></header>
<main><div class="toolbar"><input id="search" type="search" placeholder="Search questions, facts or issues" aria-label="Search cases"><label>Show <select id="filter"><option value="all">All cases</option><option value="high">High priority</option><option value="revise">Suggested revisions</option><option value="check">Need source checks</option><option value="pending">Pending decisions</option></select></label><label><input id="select-visible" type="checkbox">Select visible cases</label><span id="selection" class="meta"></span></div>
<section class="panel"><div class="toolbar"><button id="approve" class="primary" disabled>Record selected as reviewed</button><button id="exclude" disabled>Exclude selected</button><button id="reset" disabled>Leave selected pending</button></div>
<p>Record only cases you have checked. Changed proposals become <strong>Revise</strong>; unchanged ones become <strong>Accept</strong>. No cases are selected or approved automatically.</p>
<label><input id="scope-confirm" type="checkbox">I checked the full saved scope and capture suitability for the selected flagged cases.</label>
<p><label>Reason for exclusions <input id="exclude-reason" placeholder="Required to exclude cases"></label></p></section>
<table aria-label="Proposed cases and your decisions"><thead><tr><th>Select</th><th>Case / suggestion</th><th>Proposed question and expected facts</th><th>Issues, evidence and your decision</th></tr></thead><tbody id="cases"></tbody></table>
<section class="panel"><h2>Source-family grouping</h2><p>Case review does not automatically certify story families or held-out independence. Related and syndicated copies must be checked separately.</p><details><summary>Review/edit the complete source-family map</summary><textarea id="families" class="family-editor" aria-label="Source-family map"></textarea></details><label><input id="family-confirm" type="checkbox">I checked source-family grouping and related-copy leakage.</label></section>
<section class="panel"><h2>Full saved source copies</h2><p>Source links in each case open these copies. Proposed evidence is shown with each case; read the whole scoped copy before deciding an answer is absent. Saved claims are not independent fact checks.</p><div id="sources"></div></section></main>
<script type="application/json" id="payload">PAYLOAD_JSON</script><script>
(()=>{'use strict';
const data=JSON.parse(document.getElementById('payload').textContent),corpus=data.corpus;
let review=data.review;const proposals=data.suggestions.judgments,originals=new Map(corpus.cases.map(c=>[c.id,c])),sources=new Map(corpus.sources.map(s=>[s.id,s])),selected=new Set();
const $=id=>document.getElementById(id),node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n},clone=v=>JSON.parse(JSON.stringify(v)),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
function message(text,error=false){$('message').textContent=text;$('message').className=error?'warning':''}
function checkCase(c,o){if(!c||typeof c!=='object'||Array.isArray(c))throw Error('Case must be an object');for(const k of ['id','source_ids','split','label'])if(!same(c[k],o[k]))throw Error('Keep '+k+' unchanged');if(typeof c.question!=='string'||!['answerable','unanswerable'].includes(c.answerability))throw Error('Check question/answerability');for(const k of ['evidence','required_facts','acceptable_sets','tags'])if(!Array.isArray(c[k]))throw Error('Check '+k);if(c.evidence.some(e=>!e||typeof e.quote!=='string')||c.required_facts.some(f=>!f||typeof f.text!=='string'))throw Error('Invalid facts/evidence')}
function visible(i){const p=proposals[i],r=review.judgments[i],f=$('filter').value,q=$('search').value.toLowerCase();return(f==='all'||(f==='pending'?r.decision==='pending':f==='high'?p.priority==='high':p.suggested_action===f))&&JSON.stringify([p.case_id,p.case.question,p.case.required_facts,p.notes]).toLowerCase().includes(q)}
function selectedState(){for(const id of ['approve','exclude','reset'])$(id).disabled=!selected.size;$('selection').textContent=selected.size+' selected';const ids=proposals.map((p,i)=>visible(i)?p.case_id:null).filter(Boolean);$('select-visible').checked=ids.length>0&&ids.every(id=>selected.has(id));$('select-visible').indeterminate=ids.some(id=>selected.has(id))&&!$('select-visible').checked;document.querySelectorAll('input[data-family]').forEach(box=>{const group=ids.filter(id=>originals.get(id).story_group===box.dataset.family);box.checked=group.length>0&&group.every(id=>selected.has(id));box.indeterminate=group.some(id=>selected.has(id))&&!box.checked})}
function progress(){$('progress').textContent=review.judgments.filter(r=>r.decision!=='pending').length+' / '+proposals.length;$('suggested').textContent=proposals.filter(p=>p.suggested_action==='revise').length;$('flagged').textContent=proposals.filter(p=>p.suggested_action==='check').length;selectedState()}
function changeSelection(){ $('scope-confirm').checked=false;selectedState() }
function sourceLink(id){const s=sources.get(id),a=node('a',s.title);a.href='#source-'+id;a.onclick=e=>{e.preventDefault();const el=$('source-'+id);el.open=true;el.scrollIntoView()};return a}
function factList(facts){const ul=node('ul');if(!facts.length)ul.append(node('li','Proposed unanswerable: inspect the full source scope before approval.'));else for(const f of facts)ul.append(node('li',f.text));return ul}
function evidenceList(c){const wrap=node('div');for(const e of c.evidence){wrap.append(node('div',e.source_id+' · '+e.start+'–'+e.end,'meta'),node('div',e.quote,'quote'))}return wrap}
function render(){const body=$('cases');body.replaceChildren();const groups=new Map();proposals.forEach((p,i)=>{if(!visible(i))return;const group=originals.get(p.case_id).story_group;if(!groups.has(group))groups.set(group,[]);groups.get(group).push(i)});
for(const [family,indices] of groups){const g=node('tr',undefined,'group'),cell=node('td'),label=node('label'),box=node('input');cell.colSpan=4;box.type='checkbox';box.dataset.family=family;box.setAttribute('aria-label','Select visible family '+family);box.checked=indices.every(i=>selected.has(proposals[i].case_id));box.onchange=()=>{for(const i of indices){const id=proposals[i].case_id;box.checked?selected.add(id):selected.delete(id)}changeSelection();render()};label.append(box,document.createTextNode(' '+family+' · '+indices.length+' cases'));cell.append(label);g.append(cell);body.append(g);
for(const i of indices){const p=proposals[i],r=review.judgments[i],c=p.case,o=originals.get(p.case_id),tr=node('tr');tr.dataset.caseId=p.case_id;
const select=node('td'),check=node('input');check.type='checkbox';check.checked=selected.has(p.case_id);check.setAttribute('aria-label','Select '+p.case_id);check.onchange=()=>{check.checked?selected.add(p.case_id):selected.delete(p.case_id);changeSelection()};select.append(check);
const identity=node('td');identity.append(node('strong',p.case_id),node('div',p.suggested_action==='check'?'Needs source check':p.suggested_action==='revise'?'Suggested revision':'Suggested keep',p.suggested_action==='check'?'warning':'meta'),node('div',p.priority==='high'?'High priority':'Normal priority','meta'));
const proposed=node('td');proposed.append(node('strong',c.question),factList(c.required_facts));
const detail=node('td');detail.append(node('strong','Your decision: '+r.decision),node('div',p.notes,'notes'));
const compare=node('details'),comparison=node('div',undefined,'compare'),before=node('div'),after=node('div');before.append(node('h3','Original'),node('p',o.question),factList(o.required_facts),evidenceList(o));after.append(node('h3','Proposed'),node('p',c.question),factList(c.required_facts),evidenceList(c));comparison.append(before,after);compare.append(node('summary','Compare changes and exact evidence'),comparison);detail.append(compare);
const scope=node('details');scope.append(node('summary','Inspect all '+c.source_ids.length+' scoped copies'));for(const id of c.source_ids){const line=node('p');line.append(sourceLink(id));scope.append(line)}detail.append(scope);
const edit=node('details'),editor=node('textarea'),apply=node('button','Use my edited case');editor.className='case-editor';editor.setAttribute('aria-label','Edit '+p.case_id);editor.value=JSON.stringify(c,null,2);apply.onclick=()=>{try{const value=JSON.parse(editor.value);checkCase(value,o);p.case=value;r.case=clone(value);if(p.suggested_action!=='check')p.suggested_action=same(value,o)?'keep':'revise';render();message('Proposal edited. Your decision remains unchanged until you record it.')}catch(e){message(e.message,true)}};edit.append(node('summary','Edit proposed case'),editor,apply);detail.append(edit);
const notes=node('textarea');notes.className='user-notes';notes.setAttribute('aria-label','Your notes for '+p.case_id);notes.placeholder='Your review notes';notes.value=r.notes;notes.oninput=()=>r.notes=notes.value;detail.append(notes);tr.append(select,identity,proposed,detail);body.append(tr)}}progress()}
function checkedSelection(){if(!$('reviewer').value.trim())throw Error('Enter your reviewer name first.');if(!selected.size)throw Error('Select the cases you checked.');return proposals.map((p,i)=>selected.has(p.case_id)?i:null).filter(i=>i!==null)}
$('approve').onclick=()=>{try{const ids=checkedSelection();if(ids.some(i=>proposals[i].suggested_action==='check'||proposals[i].case.answerability==='unanswerable')&&!$('scope-confirm').checked)throw Error('Confirm the full-source/capture check for selected flagged cases, or leave those cases pending.');for(const i of ids)checkCase(proposals[i].case,originals.get(proposals[i].case_id));for(const i of ids){const p=proposals[i],r=review.judgments[i];r.case=clone(p.case);r.decision=same(p.case,originals.get(p.case_id))?'accept':'revise'}selected.clear();changeSelection();render();message(ids.length+' explicit decisions recorded. Download JSON to save.')}catch(e){message(e.message,true)}};
$('exclude').onclick=()=>{try{const ids=checkedSelection(),reason=$('exclude-reason').value.trim();if(!reason)throw Error('Enter an exclusion reason.');for(const i of ids){const r=review.judgments[i];r.case=clone(originals.get(r.case_id));r.decision='exclude';r.notes=reason}selected.clear();changeSelection();render();message(ids.length+' exclusions recorded; other cases are unchanged.')}catch(e){message(e.message,true)}};
$('reset').onclick=()=>{for(const r of review.judgments)if(selected.has(r.case_id)){r.decision='pending'}selected.clear();changeSelection();render();message('Selected cases left pending.')};
$('select-visible').onchange=()=>{proposals.forEach((p,i)=>{if(visible(i))$('select-visible').checked?selected.add(p.case_id):selected.delete(p.case_id)});changeSelection();render()};for(const id of ['filter','search'])$(id).oninput=()=>{selected.clear();changeSelection();render()};
$('export').onclick=()=>{try{const families=JSON.parse($('families').value);if(!families||Array.isArray(families)||typeof families!=='object'||!same(Object.keys(families).sort(),[...sources.keys()].sort())||Object.values(families).some(v=>typeof v!=='string'||!v))throw Error('Keep a complete valid source-family map.');const graded=review.judgments.some(r=>r.decision!=='pending'),name=$('reviewer').value.trim();if(graded&&!name)throw Error('Enter your reviewer name.');review.source_story_groups=families;review.source_grouping_reviewed=$('family-confirm').checked;review.reviewer=name;review.review_kind=graded?'human':'unreviewed';review.reviewed_at=graded?new Date().toISOString():'';const url=URL.createObjectURL(new Blob([JSON.stringify(review,null,2)+'\n'],{type:'application/json'})),a=node('a');a.href=url;a.download='gold-review.batch.export.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Downloaded review JSON. Pending decisions remain pending. The CLI validates the full contract.')}catch(e){message(e.message,true)}};
$('import').onclick=()=>$('import-file').click();$('import-file').onchange=async()=>{try{const file=$('import-file').files[0];if(!file)return;if(file.size>64*1024*1024)throw Error('Review exceeds 64 MiB.');const next=JSON.parse(await file.text());if(next.proposal_sha256!==review.proposal_sha256||!Array.isArray(next.judgments)||next.judgments.length!==proposals.length)throw Error('Review belongs to another corpus.');next.judgments.forEach((r,i)=>{if(r.case_id!==proposals[i].case_id||r.case_sha256!==proposals[i].case_sha256||!['pending','accept','revise','exclude'].includes(r.decision)||typeof r.notes!=='string')throw Error('Invalid case identity/decision.');checkCase(r.case,originals.get(r.case_id))});review=next;review.judgments.forEach((r,i)=>{if(!same(r.case,originals.get(r.case_id))){proposals[i].case=clone(r.case);if(proposals[i].suggested_action!=='check')proposals[i].suggested_action='revise'}});$('reviewer').value=review.reviewer;$('families').value=JSON.stringify(review.source_story_groups,null,2);$('family-confirm').checked=review.source_grouping_reviewed;selected.clear();changeSelection();render();message('Saved review loaded. The CLI performs authoritative validation.')}catch(e){message('Cannot load review: '+e.message,true)}};
for(const s of corpus.sources){const d=node('details',undefined,'source');d.id='source-'+s.id;d.append(node('summary',s.title),node('p',s.id+' · '+s.captured_at+' · '+s.url,'meta'),node('div',s.text,'source-copy'));$('sources').append(d)}
$('total').textContent=proposals.length;$('suggested').textContent=proposals.filter(p=>p.suggested_action==='revise').length;$('flagged').textContent=proposals.filter(p=>p.suggested_action==='check').length;$('families').value=JSON.stringify(review.source_story_groups,null,2);render();
})();</script></body></html>'''
