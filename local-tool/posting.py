"""Faithful local posting views and fact-based document skeletons."""
def contact(job):
    return '\n'.join(str(job.get(k) or '').strip() for k in ('contactName','contactTitle','employer','contactAddress') if job.get(k))

def display(job):
    lines=[str(job.get('title','')),str(job.get('employer','')),'Posting ID: '+str(job.get('id','')),
           'Saved: '+str(job.get('collectedAt') or job.get('lastSeen') or 'Unknown'),
           'Source: '+str(job.get('sourceUrl') or 'SFU MyExperience; search using the posting ID'),
           '\nAPPLICATION','Deadline: '+str(job.get('deadline') or 'Not captured'),
           'Documents: '+str(job.get('documents') or 'Not captured'),
           'Cover letter: '+str(job.get('coverLetter') or 'Unclear'),
           'Recipient (as listed): '+str(job.get('contactName') or 'Not captured; check posting'),
           'Method: '+str(job.get('method') or 'Not captured')]
    sections=job.get('sections') or [{'label':k,'text':v} for k,v in (job.get('fields') or {}).items()]
    if sections:
        for item in sections:lines+=['\n'+str(item.get('label','')).upper(),str(item.get('text',''))]
    else:lines+=['\nDESCRIPTION',str(job.get('description') or 'No full description. Recollect this posting with the updated extension.')]
    if job.get('links'):
        lines+=['\nPOSTING LINKS — CONTENTS NOT COLLECTED']
        lines += [str(x.get('label',''))+'\n'+str(x.get('url','')) for x in job['links']]
    lines+=['\nThis is a saved snapshot, not a live posting. Missing fields are not inferred. Verify exact deadlines and recipient instructions before applying.']
    return '\n'.join(lines)

def resume_skeleton(job,profile,kind):
    preset=profile['presets'][kind];c=profile['candidate']
    lines=[c['name'],*c.get('headerLines',[]),'','[OPTIONAL TARGETED SUMMARY: connect your verified experience to '+str(job.get('title','this role'))+'; remove this section if unnecessary.]','','TECHNICAL SKILLS',*profile['skills'][kind],'','PROJECTS']
    for key in preset['projects']:
        p=profile['projects'][key];lines += [p['title'],p['meta'],*['• '+x for x in p['bullets'][:preset.get('maxBullets',99)]],'']
    lines+=['EXPERIENCE']
    for e in profile.get('experience',[]):lines += [e['title'],e.get('dates',''),*['• '+b for b in e.get('bullets',[])],'']
    lines+=['EDUCATION']
    for e in profile.get('education',[]):lines += [e['title'],*e.get('lines',[]),'']
    return '\n'.join(lines)

def letter_skeleton(result,profile):
    job=result['job'];c=profile['candidate']
    if len(str(job.get('description') or '').strip())<100:return 'DRAFT BLOCKED: Recollect the full posting before tailoring this letter.\n'
    greeting='Dear '+job['contactName'].strip()+',' if job.get('contactName') else 'Dear Hiring Team,'
    paragraphs=[greeting,
        f"I am applying for the {job.get('title','[role]')} position at {job.get('employer','[employer]')} (posting {job.get('id','[ID]')}). I am pursuing {c.get('degree','[degree]')} at {c.get('institution','[institution]')} and am available from {c.get('availability','[availability]')}.",
        '[WHY THIS ROLE: add one specific reason this work or organisation interests you.]']
    for p in result.get('projects',[])[:2]:
        paragraphs.append('My relevant experience includes '+p['title']+'. '+' '.join(p.get('bullets',[])[:2])+' [CONNECT: explain how this work relates to one responsibility in this posting.]')
    if not result.get('projects'):paragraphs.append('[EVIDENCE: describe a verified project or experience relevant to the main requirement.]')
    paragraphs += ['Thank you for considering my application. I would welcome the opportunity to discuss how my experience could contribute to your team.','Sincerely,\n'+c.get('name','[name]')]
    return '\n\n'.join(paragraphs)+'\n'
