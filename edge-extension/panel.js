import {inspectPage,readPosting,openPosting} from './extract.js';
const source=Number(new URLSearchParams(location.search).get('source'));
const $=id=>document.getElementById(id);
let stopped=false,running=false;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function log(s){$('log').textContent+=s+'\n';$('log').scrollTop=$('log').scrollHeight;}
async function inject(tabId,func,args=[]){const result=await chrome.scripting.executeScript({target:{tabId},func,args});return result[0].result;}
async function records(){return (await chrome.storage.local.get('jobs')).jobs||{};}
async function collection(){return (await chrome.storage.local.get('collection')).collection||{ids:[],complete:false,startedAt:new Date().toISOString(),scope:'selected-pages'};}
async function saveRecord(job){const jobs=await records();jobs[job.id]={...jobs[job.id],...job};const c=await collection();if(!c.ids.includes(job.id))c.ids.push(job.id);await chrome.storage.local.set({jobs,collection:c});await count();}
async function count(){$('count').textContent=(await collection()).ids.length+' in current collection · '+Object.keys(await records()).length+' in saved history.';}
function classify(j){
 const evidence=[j.description,j.method,...(j.sections||[]).map(s=>s.text)].join('\n').split(/[\n.!?]+/).filter(x=>/cover[\s-]*letter/i.test(x)).map(x=>x.trim());
 const required=/cover[\s-]*letter/i.test(j.documents);
 const optional=evidence.some(x=>/optional|not required|not necessary/i.test(x));
 const no=evidence.some(x=>/do not (include|submit)|no cover[\s-]*letter/i.test(x));
 const demand=evidence.some(x=>/required|must|please (include|submit)/i.test(x)&&!/not required|optional|do not/i.test(x));
 j.coverLetter=(required||demand)&&(optional||no)?'Review conflict':required||demand?'Required':optional?'Optional':no?'Not requested':evidence.length?'Review wording':j.documents?'Not requested':'Unclear';
 j.evidence=['Application Documents Required: '+j.documents,...evidence];return j;
}
async function popupFor(job){
 let timer,listener;
 const opened=new Promise((resolve,reject)=>{
  listener=tab=>{if(tab.openerTabId===source){clearTimeout(timer);chrome.tabs.onCreated.removeListener(listener);resolve(tab.id);}};
  chrome.tabs.onCreated.addListener(listener);
  timer=setTimeout(()=>{chrome.tabs.onCreated.removeListener(listener);reject(Error('No job tab opened. Your browser may have blocked the popup. Nothing was submitted.'));},15000);
 });
 // Attach rejection handler immediately, including when clicking fails.
 opened.catch(()=>{});
 try{await inject(source,openPosting,[job.id,job.title]);return await opened;}
 catch(e){clearTimeout(timer);chrome.tabs.onCreated.removeListener(listener);throw e;}
}
async function readLoaded(id,expected){
 for(let n=0;n<40;n++){
  if(stopped)throw Error('Stopped. Completed jobs are saved.');
  const tab=await chrome.tabs.get(id);
  if(tab.url&&tab.url!=='about:blank'){
   if(new URL(tab.url).hostname!=='myexperience.sfu.ca')throw Error('Login or another website opened. Collection stopped.');
   if(tab.status==='complete'){const job=await inject(id,readPosting,[expected]);if(job)return job;}
  }
  await pause(500);
 }
 throw Error('Job did not finish loading. Completed jobs are saved; try that job separately.');
}
async function run(single){
 if(running)return;const c=await collection();c.complete=false;await chrome.storage.local.set({collection:c});running=true;stopped=false;$('one').disabled=$('all').disabled=true;$('stop').disabled=false;
 try{
  const tab=await chrome.tabs.get(source);
  if(!tab.url||new URL(tab.url).hostname!=='myexperience.sfu.ca')throw Error('Click the extension button while your SFU tab is selected.');
  const state=await inject(source,inspectPage);
  if(state.kind==='detail'){
   const j=await inject(source,readPosting);if(!j)throw Error('Posting is still loading. Try again after it finishes.');await saveRecord(classify(j));log(j.id+' - '+j.coverLetter);
  }else{
   const jobs=state.jobs.filter(j=>j.status!=='Already submitted');
   if(!jobs.length)throw Error('No unsubmitted jobs found on this page.');
   for(const job of single?jobs.slice(0,1):jobs){
    if(stopped)break;
    $('status').textContent='Reading '+job.title;
    const id=await popupFor(job);
    // Only close the specific popup after successful identity verification.
    const full=classify({...job,...await readLoaded(id,job.id)});
    await saveRecord(full);await chrome.tabs.remove(id);log(full.id+' - '+full.coverLetter);
   }
  }
  const finished=await collection();finished.complete=!stopped&&!single;finished.lastRunAt=new Date().toISOString();await chrome.storage.local.set({collection:finished});$('status').textContent=stopped?'Stopped. Completed jobs are saved.':'Done. Click Save jobs file.';
 }catch(e){$('status').textContent='Collection stopped.';log(e.message);}
 finally{running=false;$('one').disabled=$('all').disabled=false;$('stop').disabled=true;}
}
$('one').onclick=()=>run(true);$('all').onclick=()=>run(false);$('stop').onclick=()=>{stopped=true;};
$('save').onclick=async()=>{
 if(running){log('Stop or finish collection before exporting.');return;}const c=await collection(),saved=await records();const jobs=$('history').checked?Object.values(saved):c.ids.map(id=>saved[id]).filter(Boolean);if(!jobs.length){log('Collect a posting first.');return;}
 const blob=new Blob([JSON.stringify({jobs,collection:$('history').checked?{complete:false,scope:'history'}:c,exportedAt:new Date().toISOString()},null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='SFU-favourites.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
};
count();

$('fresh').onclick=async()=>{if(running)return;if(!confirm('Start an empty current collection? Saved history stays.'))return;await chrome.storage.local.set({collection:{ids:[],complete:false,startedAt:new Date().toISOString(),scope:'selected-pages'}});await count();log('New collection started. Collect each favourites page you want to include.');};
$('clear').onclick=async()=>{if(running)return;if(!confirm('Clear this extension’s collected job history? Export a copy first if needed. Application Desk data is not affected.'))return;await chrome.storage.local.remove(['jobs','collection']);await count();};
