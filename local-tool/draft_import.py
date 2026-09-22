"""Validated, previewed batch draft imports; never changes application statuses."""
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from core import now
from review import load

def validate(payload,store):
    entries=payload.get('drafts') if isinstance(payload,dict) else None
    if not isinstance(entries,list) or not 1<=len(entries)<=100:raise ValueError('Expected {"drafts": [...]} containing 1–100 drafts.')
    known={j['id']:j for j in store.all()};seen=set();result=[]
    for item in entries:
        if not isinstance(item,dict):raise ValueError('Every draft must be an object.')
        id=str(item.get('id',''));text=item.get('letter');resume=item.get('resume','software')
        if id in seen:raise ValueError('Duplicate job ID: '+id)
        if id not in known:raise ValueError('Job ID is not in your imported jobs: '+id)
        if known[id].get('status')=='Already submitted':raise ValueError('Exclude already-submitted job '+id)
        if not isinstance(text,str) or not text.strip() or len(text)>30000:raise ValueError('Letter must contain 1–30,000 characters for '+id)
        if '\x00' in text or resume not in ('hardware','software','form'):raise ValueError('Invalid letter or resume choice for '+id)
        prior=load(store,id)
        result.append({'id':id,'letter':text,'resume':resume,'notes':prior[2] if prior else '', 'previous':prior,'title':known[id].get('title',''),'employer':known[id].get('employer','')});seen.add(id)
    return result

def commit(entries,store):
    # Recheck draft values inside the transaction to avoid overwriting edits made after preview.
    with store.connect() as db:
        for entry in entries:
            current=db.execute('SELECT text,resume,notes FROM drafts WHERE job_id=?',(entry['id'],)).fetchone()
            if current!=entry['previous']:raise ValueError('Draft changed since preview: '+entry['id']+'. Reopen the import.')
            status=db.execute('SELECT status FROM jobs WHERE id=?',(entry['id'],)).fetchone()
            if not status or status[0]=='Already submitted':raise ValueError('Job status changed since preview. Reopen the import.')
        for entry in entries:
            db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?,?,?,?)',(entry['id'],entry['letter'],entry['resume'],entry['notes'],now()))

def import_window(app):
    file=filedialog.askopenfilename(title='Import drafted letters from AI review',filetypes=[('JSON','*.json')])
    if not file:return
    try:
        from pathlib import Path
        path=Path(file)
        if path.stat().st_size>5*1024*1024:raise ValueError('Choose a JSON file under 5 MB.')
        entries=validate(json.loads(path.read_text(encoding='utf-8-sig')),app.store)
    except Exception as e:messagebox.showerror('Import rejected',str(e));return
    w=tk.Toplevel(app.root);w.title('Preview imported drafts');w.geometry('1100x720')
    changed=sum(x['previous'] is not None for x in entries)
    ttk.Label(w,text=f'{len(entries)} drafts proposed; {changed} existing drafts would be replaced. Nothing saved yet.',wraplength=1000).pack(anchor='w',padx=12,pady=12)
    select=ttk.Combobox(w,state='readonly',values=[x['id']+' · '+x['employer']+' · '+x['title'] for x in entries]);select.pack(fill='x',padx=12);select.current(0)
    pane=ttk.Panedwindow(w,orient='horizontal');pane.pack(fill='both',expand=True,padx=12,pady=12)
    boxes=[]
    for title in ['Existing saved draft','Proposed replacement']:
        frame=ttk.Frame(pane);pane.add(frame,weight=1);ttk.Label(frame,text=title).pack(anchor='w');box=tk.Text(frame,wrap='word',font=('Segoe UI',10));box.pack(fill='both',expand=True);boxes.append(box)
    def show(event=None):
        item=entries[select.current()]
        for box,text in zip(boxes,[item['previous'][0] if item['previous'] else '(No existing draft)',item['letter']]):box.configure(state='normal');box.delete('1.0','end');box.insert('1.0',text);box.configure(state='disabled')
    select.bind('<<ComboboxSelected>>',show);show()
    def accept():
        if not messagebox.askyesno('Save these drafts?',f'Save {len(entries)} drafts and replace {changed} existing drafts? Review the proposed text first. Application statuses stay unchanged.',parent=w):return
        try:commit(entries,app.store);app.say(f'Imported {len(entries)} drafts. Review each before PDF export.');w.destroy()
        except Exception as e:messagebox.showerror('Nothing imported',str(e),parent=w)
    buttons=ttk.Frame(w);buttons.pack(fill='x',padx=12,pady=12);ttk.Button(buttons,text='Cancel',command=w.destroy).pack(side='right');ttk.Button(buttons,text='Save these drafts',command=accept).pack(side='right',padx=8)
