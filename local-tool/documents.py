"""PDF rendering only: no model calls, no generated claims."""
import json,re
from pathlib import Path
from io import BytesIO
from html import escape
from datetime import date
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,HRFlowable,KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from pypdf import PdfReader

def render(profile_path,output,kind='software',letter_text=None,subject='',recipient='',resume_text=None):
    d=json.loads(Path(profile_path).read_text(encoding='utf-8'));candidate=d['candidate']
    navy=HexColor('#203e59')
    def style(name,size=9.4,leading=12.5,**kwargs):return ParagraphStyle(name,fontName='Helvetica',fontSize=size,leading=leading,spaceAfter=4,**kwargs)
    styles={'body':style('body'),'title':style('title',9.8,13),'meta':style('meta',9,12),'name':style('name',21,25,alignment=1,textColor=navy),'contact':style('contact',9,12,alignment=1),'section':style('section',10,13,textColor=navy,spaceBefore=9),'letter':style('letter',10.5,15.5)}
    for k in ['title','name','section']:styles[k].fontName='Helvetica-Bold'
    styles['meta'].fontName='Helvetica-Oblique';styles['letter'].spaceAfter=13
    def para(text,kind='body'):
        text=text.replace('\u2011','-').replace('\u2013','-').replace('\u2014','-')
        return Paragraph(escape(text).replace('\n','<br/>'),styles[kind])
    def sec(text):return [para(text,'section'),HRFlowable(width='100%',thickness=.5,color=HexColor('#b4c0c9')),Spacer(1,5)]
    story=[para(candidate['name'],'name')]+[para(x,'contact') for x in candidate['headerLines']]
    if resume_text is not None:
        if letter_text is not None:raise ValueError('Choose a resume or a letter, not both.')
        if not resume_text.strip() or len(resume_text)>30000:raise ValueError('Resume must contain 1–30,000 characters.')
        if re.search(r'\[[^\]]*\]',resume_text):raise ValueError('Replace or remove bracketed prompts before exporting the resume PDF.')
        lines=resume_text.strip().splitlines()
        story=[para(lines[0].strip(),'name')]
        headings={'TECHNICAL SKILLS','SKILLS','PROJECTS','EXPERIENCE','EDUCATION','SUMMARY','PROFILE','CERTIFICATIONS','AWARDS','VOLUNTEERING','RELEVANT EXPERIENCE'}
        in_header=True;previous_blank=False;section=''
        for raw in lines[1:]:
            line=raw.strip()
            if not line:
                in_header=False;previous_blank=True
                continue
            if line.upper() in headings:
                in_header=False;section=line.upper();story+=sec(section);previous_blank=True
            elif in_header:story.append(para(line,'contact'))
            else:
                if previous_blank and section in {'PROJECTS','EXPERIENCE','EDUCATION','RELEVANT EXPERIENCE'}:
                    story.append(para(line,'title'))
                elif line.startswith(('• ','- ')):story.append(para('- '+line[2:]))
                else:story.append(para(line))
                previous_blank=False
    elif letter_text is not None:
        if not letter_text.strip():raise ValueError('Paste a reviewed letter first. This tool formats text; it does not write letters.')
        if len(letter_text)>12000:raise ValueError('Letter is too long. Shorten it before rendering.')
        story += [Spacer(1,22),para(date.today().strftime('%B %d, %Y'),'letter')]
        if recipient.strip():story.append(para(recipient,'letter'))
        if subject.strip():story += [para(subject,'title'),Spacer(1,10)]
        story += [para(x.strip(),'letter') for x in re.split(r'\n\s*\n',letter_text) if x.strip()]
    else:
        preset=d['presets'][kind]
        story+=sec('TECHNICAL SKILLS')+[para(x) for x in d['skills'][kind]]+sec('PROJECTS')
        for key in preset['projects']:
            project=d['projects'][key];bullets=project['bullets'][:preset.get('maxBullets',99)]
            story.append(KeepTogether([para(project['title'],'title'),para(project['meta'],'meta')]+[para('- '+x) for x in bullets]))
        story+=sec('EXPERIENCE')
        for e in d['experience']:story += [para(e['title'],'title'),para(e['dates'],'meta')]+[para('- '+b) for b in e['bullets']]
        story+=sec('EDUCATION')
        for e in d['education']:story += [para(e['title'],'title')]+[para(x) for x in e['lines']]
    buf=BytesIO();SimpleDocTemplate(buf,pagesize=letter,leftMargin=42,rightMargin=42,topMargin=35,bottomMargin=35).build(story)
    data=buf.getvalue();pages=len(PdfReader(BytesIO(data)).pages)
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(target)
    return pages
