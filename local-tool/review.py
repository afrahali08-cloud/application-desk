"""Per-posting draft workspace. Drafts are independent of collected postings."""
import json
import tkinter as tk
from tkinter import ttk, messagebox
from batch import analyse, starter
from core import now
from posting import display,contact,resume_skeleton

def load(store,id):
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS drafts (job_id TEXT PRIMARY KEY, text TEXT NOT NULL, resume TEXT NOT NULL, notes TEXT NOT NULL, updated TEXT NOT NULL)')
        row=db.execute('SELECT text,resume,notes FROM drafts WHERE job_id=?',(id,)).fetchone()
    return row

def save(store,id,text,resume,notes):
    load(store,id)
    with store.connect() as db:
        db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?,?,?,?)',(id,text,resume,notes,now()))

def open_review(app):
    ids=app.table.selection()
    if len(ids)!=1:
        messagebox.showinfo('Choose one job','Select one posting to review and edit its draft.');return
    job=app.store.get(ids[0]);profile=json.loads(app.profile.read_text(encoding='utf-8-sig'));result=analyse(job,profile)
    prior=load(app.store,job['id'])
    w=tk.Toplevel(app.root);w.title('Review — '+job.get('title','Posting'));w.geometry('1180x800')
    ttk.Label(w,text=job.get('title','')+' · '+job.get('employer',''),font=('Segoe UI',15,'bold'),wraplength=1100).pack(anchor='w',padx=15,pady=10)
    ttk.Label(w,text='Deadline: '+str(job.get('deadline','Check portal'))+'   |   Cover letter: '+result['letter'],wraplength=1100).pack(anchor='w',padx=15)
    panes=ttk.Panedwindow(w,orient='horizontal');panes.pack(fill='both',expand=True,padx=15,pady=10)
    left=ttk.Frame(panes);right=ttk.Frame(panes);panes.add(left,weight=1);panes.add(right,weight=1)
    tabs=ttk.Notebook(left);tabs.pack(fill='both',expand=True)
    def read_tab(title,text):
        frame=ttk.Frame(tabs);tabs.add(frame,text=title)
        box=tk.Text(frame,wrap='word',font=('Segoe UI',10));bar=ttk.Scrollbar(frame,command=box.yview);box.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');box.pack(fill='both',expand=True);box.insert('1.0',text);box.configure(state='disabled')
    read_tab('Posting',display(job))
    read_tab('Original text',str(job.get('rawText') or job.get('description') or 'Not captured in this older export.'))
    evidence='\n\n'.join(e['term']+'\n  '+'\n  '.join(e['sources']) for e in result['evidence'])
    read_tab('Skills & checks','\n'.join(result['flags'])+'\n\nSUPPORTED POSTING TERMS\n'+evidence+'\n\nNOT FOUND IN SAVED PROFILE\n'+', '.join(result['gaps'])+'\n\nThese are keyword matches, not an ATS score or proof that a skill is required. Use only claims you can support.\n\nDOCUMENTS\n'+str(job.get('documents','Check portal'))+'\n\nAPPLICATION METHOD\n'+str(job.get('method','Check portal')))
    controls=ttk.Frame(right);controls.pack(fill='x')
    ttk.Label(controls,text='Resume base:').pack(side='left');preset=tk.StringVar(value=prior[1] if prior else (result['preset'] if result['preset'] in ('hardware','software','form') else 'software'))
    ttk.Combobox(controls,textvariable=preset,values=['hardware','software','form'],state='readonly',width=14).pack(side='left',padx=8)
    ttk.Button(controls,text='Resume skeleton',command=lambda:resume_window(app,job,profile,preset.get())).pack(side='right')
    ttk.Label(right,text='Letter draft — edit all bracketed prompts before creating a PDF').pack(anchor='w',pady=8)
    letter=tk.Text(right,wrap='word',font=('Segoe UI',11),undo=True);letter.pack(fill='both',expand=True)
    letter.insert('1.0',prior[0] if prior else starter(result,profile))
    ttk.Label(right,text='Your notes / next action').pack(anchor='w',pady=(8,0));notes=tk.Text(right,height=3,wrap='word');notes.pack(fill='x');notes.insert('1.0',prior[2] if prior else '')
    status=tk.StringVar(value='Saved draft loaded.' if prior else 'New starter — not saved yet.');ttk.Label(right,textvariable=status).pack(anchor='w',pady=6)
    snapshot=[(letter.get('1.0','end-1c'),preset.get(),notes.get('1.0','end-1c')) if prior else None]
    def values():return (letter.get('1.0','end-1c'),preset.get(),notes.get('1.0','end-1c'))
    def commit():
        try:
            save(app.store,job['id'],*values());snapshot[0]=values();status.set('Draft saved locally. Application status unchanged.');return True
        except Exception as e:messagebox.showerror('Save failed',str(e),parent=w);return False
    def regenerate():
        if not messagebox.askyesno('Replace draft?','Replace this editor text with a new starter from the current posting? Save your existing text first if needed.',parent=w):return
        letter.delete('1.0','end');letter.insert('1.0',starter(result,profile));status.set('Starter replaced — save to keep it.')
    def to_pdf():
        text=letter.get('1.0','end-1c')
        if not text.strip() or 'DRAFT BLOCKED' in text or '[' in text or 'UNFINISHED DRAFT' in text or 'Relevant experience to develop:' in text:
            messagebox.showinfo('Finish the draft','Remove the starter instructions and replace bracketed prompts with reviewed text first.',parent=w);return
        if not commit():return
        app.subject.set(job.get('title','')+' — '+job['id']);app.preset.set(preset.get());app.recipient.delete('1.0','end');app.recipient.insert('1.0',contact(job));app.letter.delete('1.0','end');app.letter.insert('1.0',text);app.tabs.select(app.docs);w.destroy()
    buttons=ttk.Frame(right);buttons.pack(fill='x',pady=8)
    ttk.Button(buttons,text='Save draft',command=commit).pack(side='left')
    ttk.Button(buttons,text='Rebuild starter',command=regenerate).pack(side='left',padx=5)
    ttk.Button(buttons,text='Send to PDF editor',command=to_pdf).pack(side='right')
    w.bind('<Control-s>',lambda e:commit())
    def close():
        if values()!=snapshot[0]:
            answer=messagebox.askyesnocancel('Unsaved draft','Save this draft before closing?',parent=w)
            if answer is None or (answer and not commit()):return
        w.destroy()
    w.protocol('WM_DELETE_WINDOW',close)


def resume_window(app,job,profile,kind):
    from tkinter import filedialog
    from pathlib import Path
    with app.store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS resume_drafts (job_id TEXT PRIMARY KEY, text TEXT NOT NULL, updated TEXT NOT NULL)')
        row=db.execute('SELECT text FROM resume_drafts WHERE job_id=?',(job['id'],)).fetchone()
    w=tk.Toplevel(app.root);w.title('Resume skeleton — '+job.get('title',''));w.geometry('850x760')
    ttk.Label(w,text='Edit the saved facts and replace/remove bracketed prompts. Export editable text or a PDF of these exact edits.',wraplength=800).pack(padx=12,pady=12)
    text=tk.Text(w,wrap='word',undo=True,font=('Segoe UI',11));text.pack(fill='both',expand=True,padx=12);text.insert('1.0',row[0] if row else resume_skeleton(job,profile,kind))
    saved=[row[0] if row else None]
    def save_resume():
        value=text.get('1.0','end-1c')
        try:
            with app.store.connect() as db:db.execute('INSERT OR REPLACE INTO resume_drafts VALUES (?,?,?)',(job['id'],value,now()))
            saved[0]=value;status.set('Saved for this posting. Your base profile is unchanged.');return True
        except Exception as e:messagebox.showerror('Save failed',str(e),parent=w);return False
    def export_resume():
        f=filedialog.asksaveasfilename(parent=w,initialfile='resume-'+job['id']+'.txt',defaultextension='.txt',filetypes=[('Text skeleton','*.txt')])
        if f:
            try:Path(f).write_text(text.get('1.0','end-1c'),encoding='utf-8');save_resume()
            except Exception as e:messagebox.showerror('Export failed',str(e),parent=w)
    def export_pdf():
        value=text.get('1.0','end-1c')
        import re,os
        if not value.strip() or re.search(r'\[[^\]]*\]',value):
            messagebox.showinfo('Finish the resume','Replace or remove bracketed prompts before creating the PDF.',parent=w);return
        f=filedialog.asksaveasfilename(parent=w,initialfile='resume-'+job['id']+'.pdf',defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
        if not f:return
        try:
            from documents import render
            pages=render(app.profile,f,resume_text=value)
            save_resume();messagebox.showinfo('PDF ready',f'Saved {pages}-page PDF from your edited resume. Review it and check any posting page limits.',parent=w);os.startfile(f)
        except Exception as e:messagebox.showerror('Could not create PDF',str(e),parent=w)
    status=tk.StringVar(value='Saved version loaded.' if row else 'New skeleton; edits are not saved yet.');ttk.Label(w,textvariable=status).pack(anchor='w',padx=12,pady=8)
    buttons=ttk.Frame(w);buttons.pack(fill='x',padx=12,pady=12);ttk.Button(buttons,text='Save resume draft',command=save_resume).pack(side='left');ttk.Button(buttons,text='Export PDF',command=export_pdf).pack(side='right',padx=6);ttk.Button(buttons,text='Export editable text',command=export_resume).pack(side='right')
    def close():
        if text.get('1.0','end-1c')!=saved[0]:
            answer=messagebox.askyesnocancel('Save resume?','Save this resume draft before closing?',parent=w)
            if answer is None or (answer and not save_resume()):return
        w.destroy()
    w.protocol('WM_DELETE_WINDOW',close);w.bind('<Control-s>',lambda e:save_resume())
