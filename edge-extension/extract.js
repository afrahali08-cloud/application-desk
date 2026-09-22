// Functions are self-contained because Chrome copies them into the target page.
export function inspectPage() {
  if(location.hostname!=='myexperience.sfu.ca')throw Error('Open SFU myExperience first.');
  const text=document.body.innerText;
  if(/Sorry, you have been blocked|Just a moment|Verify you are human/i.test(text)||document.querySelector('iframe[src*="challenges.cloudflare.com"]'))throw Error('A security check is showing. Collection stopped.');
  const heading=[...document.querySelectorAll('h1')].map(x=>x.innerText.trim());
  if(heading.some(x=>/^\d+\s*-/.test(x)))return {kind:'detail'};
  if(!heading.includes('Search Results - Shortlist'))throw Error('Sign in, open Co-op > Job Postings > Favourite, then try again.');
  const rows=[...document.querySelectorAll('tr')].map(r=>[...r.querySelectorAll(':scope > td')].map(c=>c.innerText.trim())).filter(c=>c.length>=13&&/^\d{3,12}$/.test(c[4]));
  return {kind:'shortlist',jobs:rows.map(c=>({id:c[4],title:c[5],employer:c[6],term:c[3],deadline:c[12],status:/Application Submitted/.test(c[1])?'Already submitted':'To review'}))};
}
export function readPosting(expectedId) {
  if(location.hostname!=='myexperience.sfu.ca')throw Error('Posting left SFU; collection stopped.');
  const text=document.body.innerText;
  if(/Sorry, you have been blocked|Just a moment|Verify you are human/i.test(text)||document.querySelector('iframe[src*="challenges.cloudflare.com"]'))throw Error('A security check is showing. Collection stopped.');
  const heading=[...document.querySelectorAll('h1')].map(x=>x.innerText.trim()).find(x=>/^\d+\s*-/.test(x));
  if(!heading)return null;
  const match=heading.match(/^(\d+)\s*-\s*([\s\S]+)/);
  if(expectedId&&match[1]!==expectedId)throw Error('Different posting opened; collection stopped.');
  const fields={},sections=[],links=[];
  function capture(label,node){
    label=label.replace(/\s+/g,' ').trim().replace(/:$/,'');const value=node.innerText.trim();
    if(!label||!value)return;
    sections.push({label,text:value});fields[label]=fields[label]?fields[label]+'\n\n'+value:value;
    for(const a of node.querySelectorAll('a[href]')){try{const url=new URL(a.getAttribute('href'),location.href);if(['https:','http:','mailto:'].includes(url.protocol)&&!links.some(x=>x.url===url.href))links.push({label:a.innerText.trim()||label,url:url.href,section:label})}catch{}}
  }
  for(const row of document.querySelectorAll('tr')){
    const cells=[...row.querySelectorAll(':scope > td, :scope > th')];if(cells.length===2)capture(cells[0].innerText,cells[1]);
  }
  for(const dt of document.querySelectorAll('dt'))if(dt.nextElementSibling?.tagName==='DD')capture(dt.innerText,dt.nextElementSibling);
  const field=(...names)=>{for(const name of names){const key=Object.keys(fields).find(k=>k.toLowerCase()===name.toLowerCase());if(key)return fields[key]}return ''};
  const description=field('Job Description','Position Description','Description');
  if(!description&&!field('Application Documents Required'))return null;
  return {id:match[1],title:match[2].replace(/\s+/g,' ').trim(),employer:field('Organization','Employer','Company'),documents:field('Application Documents Required','Required Documents'),description,deadline:field('Application Deadline'),method:field('Application Method'),duration:field('Duration','Work Term Duration'),location:field('Job Location','Location','City'),qualifications:field('Job Requirements','Qualifications','Required Qualifications'),responsibilities:field('Job Responsibilities','Responsibilities'),contactName:field('Cover Letter Addressed To','Address Cover Letter To','Contact Name','Application Contact'),contactTitle:field('Contact Title'),contactEmail:field('Contact Email','Application Email'),contactAddress:field('Contact Address','Mailing Address'),fields,sections,links,rawText:(document.querySelector('main,[role="main"]')||document.body).innerText,sourceUrl:location.href,collectedAt:new Date().toISOString(),schemaVersion:2,source:'SFU browser extension; visible posting snapshot. External forms and attachment contents not inspected'};

}
export function openPosting(id,title) {
  if(location.hostname!=='myexperience.sfu.ca')throw Error('Open SFU first.');
  if(![...document.querySelectorAll('h1')].some(h=>h.innerText.trim()==='Search Results - Shortlist'))throw Error('Favourites page changed. Stop and reopen it.');
  const rows=[...document.querySelectorAll('tr')].filter(r=>{const c=r.querySelectorAll(':scope > td');return c.length>=13&&c[4].innerText.trim()===id;});
  if(rows.length!==1)throw Error('Could not identify job '+id);
  const buttons=[...rows[0].querySelectorAll('button,[role="button"]')].filter(b=>b.innerText.replace(/\s+/g,' ').trim()===title.replace(/\s+/g,' ').trim());
  if(buttons.length!==1)throw Error('Could not identify job-title button.');
  buttons[0].click();
}
