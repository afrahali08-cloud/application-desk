"""Validated imports, local shortlist management, and non-SFU postings."""
import hashlib,json,re
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from core import classify,now

def valid_id(value):return bool(re.fullmatch(r'(?:\d{3,12}|ext-[a-f0-9]{24})',str(value)))
def url(value):
    value=value.strip()
    if not value:return ''
    p=urlsplit(value)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:raise ValueError('Use a full http or https posting link.')
    return value
def external(title,employer,text,source_url='',deadline='',documents='',contact_name=''):
    if not title.strip() or not employer.strip() or len(text.strip())<40:raise ValueError('Enter the title, employer, and the full posting text (at least 40 characters).')
    source_url=url(source_url)
    if source_url:
        p=urlsplit(source_url);identity=urlunsplit((p.scheme,p.netloc.lower(),p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]),''))
    else:identity=employer.strip().casefold()+'|'+title.strip().casefold()
    status,evidence=classify(documents,text)
    return {'id':'ext-'+hashlib.sha256(identity.encode()).hexdigest()[:24],'title':title.strip(),'employer':employer.strip(),'description':text.strip(),'rawText':text.strip(),'sourceUrl':source_url,'deadline':deadline.strip(),'documents':documents.strip(),'contactName':contact_name.strip(),'coverLetter':status,'evidence':evidence,'sourceType':'external','source':'User pasted external posting; source fields must be checked.','collectedAt':now(),'sections':[{'label':'Job posting','text':text.strip()}]}

def read_import(path):
    p=Path(path)
    if p.stat().st_size>30*1024*1024:raise ValueError('Import file exceeds 30 MB.')
    payload=json.loads(p.read_text(encoding='utf-8-sig'));jobs=payload.get('jobs') if isinstance(payload,dict) else payload
    if not isinstance(jobs,list) or len(jobs)>5000:raise ValueError('Expected a list of up to 5,000 jobs.')
    if isinstance(payload,dict) and 'collection' in payload and not isinstance(payload['collection'],dict):raise ValueError('Invalid collection metadata.')
    seen=set()
    for j in jobs:
        if not isinstance(j,dict) or not valid_id(j.get('id')):raise ValueError('Invalid posting ID.')
        j['id']=str(j['id'])
        if j['id'] in seen:raise ValueError('Duplicate posting ID '+j['id'])
        seen.add(j['id'])
        for k in ('title','employer','description','documents','deadline','method','sourceUrl','contactName','rawText'):
            if k in j and not isinstance(j[k],str):raise ValueError('Invalid '+k+' in '+j['id'])
        if not j.get('title','').strip() or not j.get('employer','').strip():raise ValueError('Title and employer are required for '+j['id'])
        if 'sections' in j and (not isinstance(j['sections'],list) or any(not isinstance(x,dict) or not isinstance(x.get('label'),str) or not isinstance(x.get('text'),str) for x in j['sections'])):raise ValueError('Invalid sections.')
        if 'links' in j and (not isinstance(j['links'],list) or any(not isinstance(x,dict) or not isinstance(x.get('url'),str) for x in j['links'])):raise ValueError('Invalid links.')
        if len(json.dumps(j))>1000000:raise ValueError('Posting is too large: '+j['id'])
    return jobs,payload if isinstance(payload,dict) else {}

def preview(store,jobs):
    old={j['id']:j for j in store.all()};ids={j['id'] for j in jobs}
    missing=[j['id'] for j in old.values() if j['id'].isdigit() and j['id'] not in ids and not j.get('archived') and j['status']!='Already submitted']
    return {'new':sum(j['id'] not in old for j in jobs),'updated':sum(j['id'] in old for j in jobs),'archive':missing}

def import_jobs(store,jobs,replace=False):
    if replace and (not jobs or any(not j['id'].isdigit() for j in jobs)):raise ValueError('Replace shortlist needs a nonempty SFU-only collection.')
    with store.connect() as c:
        # Same transaction for every update and archive: errors cannot leave a partial import.
        old={r[0]:json.loads(r[1]) for r in c.execute('SELECT id,payload FROM jobs')}
        for source in jobs:
            j=dict(source)
            for k in ('resumeBase','note','fitReview','preparedFiles','preparationStatus'):
                if k not in j and k in old.get(j['id'],{}):j[k]=old[j['id']][k]
            store._save(j,c)
            if replace:c.execute('DELETE FROM archived_jobs WHERE job_id=?',(j['id'],))
        if replace:
            ids={j['id'] for j in jobs}
            for id,status in c.execute('SELECT id,status FROM jobs').fetchall():
                if id.isdigit() and id not in ids and status!='Already submitted':c.execute('INSERT OR REPLACE INTO archived_jobs VALUES (?,?)',(id,now()))
    return len(jobs)

def archive(store,ids,restore=False):
    with store.connect() as c:
        for id in ids:
            if restore:c.execute('DELETE FROM archived_jobs WHERE job_id=?',(id,))
            else:c.execute('INSERT OR REPLACE INTO archived_jobs VALUES (?,?)',(id,now()))
