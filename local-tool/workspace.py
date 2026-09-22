"""A single-window application workspace over the existing local database."""
import json,os,re,tkinter as tk,webbrowser
from datetime import date,datetime
from pathlib import Path
from tkinter import ttk,filedialog,messagebox
from app import App
from core import ROOT,now
from batch import analyse,starter,deadline
from posting import resume_skeleton,contact
from review import load,save
from intake import read_import,preview,import_jobs,archive,external,url

from workflow import Workflow,job_folder,progress,put

class Workspace(Workflow,App):
    def __init__(self,root):
        self.building=True;self.current=None;self.dirty=False;self.pending=None
        super().__init__(root)
        root.title('Application Desk — Your application workspace');root.geometry(f'{min(1440,root.winfo_screenwidth()-80)}x{min(900,root.winfo_screenheight()-120)}+20+20');root.minsize(1000,600)
        self.jobs_frame=self.tabs.nametowidget(self.tabs.tabs()[0])
        for child in self.jobs_frame.winfo_children():child.destroy()
        self.tabs.tab(self.jobs_frame,text='Application workspace');self.tabs.tab(self.docs,text='Standalone PDF tools')
        style=ttk.Style();style.configure('.',font=('Segoe UI',10));style.configure('TFrame',background='#eef2f6');style.configure('TLabel',background='#eef2f6',foreground='#263b50');style.configure('TButton',padding=(10,7));style.configure('Treeview',rowheight=54,font=('Segoe UI',10),background='#ffffff',fieldbackground='#ffffff',borderwidth=0);style.map('Treeview',background=[('selected','#d9e9f7')],foreground=[('selected','#173e61')]);style.configure('Heading.TLabel',font=('Segoe UI',16,'bold'));style.configure('Primary.TButton',font=('Segoe UI',10,'bold'))
        top=ttk.Frame(self.jobs_frame);top.pack(fill='x',pady=(0,10))
        ttk.Button(top,text='Import shortlist',command=self.import_json,style='Primary.TButton').pack(side='left')
        ttk.Button(top,text='+ Outside SFU',command=self.external_form).pack(side='left',padx=6)
        ttk.Button(top,text='Paste SFU posting',command=self.paste_posting).pack(side='left')
        menu=ttk.Menubutton(top,text='Tools & backup');menu.pack(side='right');m=tk.Menu(menu,tearoff=False);menu['menu']=m
        from backup import backup_dialog
        from draft_import import import_window
        m.add_command(label='Import drafted letters',command=lambda:self.import_letters(import_window));m.add_command(label='Prepare all visible jobs',command=lambda:self.prepare_batch(True));m.add_command(label='Back up jobs and drafts',command=lambda:backup_dialog(self));m.add_command(label='Open extension folder',command=lambda:os.startfile(str(ROOT.parent/'edge-extension')));m.add_command(label='Open saved files',command=lambda:os.startfile(str(ROOT)))
        ttk.Label(top,text='Search').pack(side='left',padx=(12,0));self.query=tk.StringVar();search=ttk.Entry(top,textvariable=self.query,width=30);search.pack(side='left',padx=12);search.insert(0,'');self.query.trace_add('write',lambda *_:self.refresh())
        self.view_filter=tk.StringVar(value='Active');self.source_filter=tk.StringVar(value='All sources');self.letter_filter=tk.StringVar(value='All letters')
        filters=ttk.Frame(self.jobs_frame);filters.pack(fill='x',pady=(0,10))
        for label,var,values in [('View',self.view_filter,['Active','Due in 7 days','Ready','Already submitted','All jobs','Trash']),('Source',self.source_filter,['All sources','SFU','External']),('Cover letter',self.letter_filter,['All letters','Required','Not requested','Optional','Needs checking'])]:
            ttk.Label(filters,text=label).pack(side='left',padx=(0,5));box=ttk.Combobox(filters,textvariable=var,values=values,state='readonly',width=17);box.pack(side='left',padx=(0,15));var.trace_add('write',lambda *_:self.refresh())
        self.summary=tk.StringVar();ttk.Label(filters,textvariable=self.summary).pack(side='right')
        self.bulk=ttk.Frame(self.jobs_frame)
        self.bulk_label=ttk.Label(self.bulk);self.bulk_label.pack(side='left',padx=5)
        ttk.Button(self.bulk,text='Prepare selected',command=self.prepare_batch).pack(side='left',padx=4)
        ttk.Button(self.bulk,text='Move selected to Trash',command=self.remove_selected).pack(side='left',padx=4)
        ttk.Button(self.bulk,text='Restore selected',command=lambda:self.remove_selected(True)).pack(side='left',padx=4)
        self.main_panes=ttk.Panedwindow(self.jobs_frame,orient='horizontal');self.main_panes.pack(fill='both',expand=True)
        left=ttk.Frame(self.main_panes,width=300);middle=ttk.Frame(self.main_panes,width=500,padding=(12,0));right=ttk.Frame(self.main_panes,width=480,padding=(8,0));self.main_panes.add(left,weight=2);self.main_panes.add(middle,weight=4);self.main_panes.add(right,weight=4)
        ttk.Label(left,text='Your shortlist',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
        self.table=ttk.Treeview(left,columns=('due',),show='tree headings',selectmode='extended');self.table.heading('#0',text='Role / employer');self.table.column('#0',width=240,minwidth=150);self.table.heading('due',text='Due');self.table.column('due',width=85,minwidth=70,stretch=False)
        scroll=ttk.Scrollbar(left,command=self.table.yview);scroll.pack(side='right',fill='y');self.table.configure(yscrollcommand=scroll.set);self.table.pack(fill='both',expand=True);self.table.bind('<<TreeviewSelect>>',self.details)
        self.table.tag_configure('past',foreground='#925338');self.table.bind('<Control-a>',lambda e:self.select_all())
        self.job_title=tk.StringVar(value='Choose a posting');ttk.Label(middle,textvariable=self.job_title,style='Heading.TLabel',wraplength=440).pack(anchor='w',pady=(0,6))
        self.job_meta=tk.StringVar();ttk.Label(middle,textvariable=self.job_meta,wraplength=440).pack(anchor='w',pady=(0,10))
        self.posting_tabs=ttk.Notebook(middle);self.posting_tabs.pack(fill='both',expand=True)
        self.posting=self.reader(self.posting_tabs,'Posting');self.match=self.reader(self.posting_tabs,'Skill evidence');self.raw=self.reader(self.posting_tabs,'Original text')
        links=ttk.Frame(middle);links.pack(fill='x',pady=8);ttk.Button(links,text='Open source',command=self.open_source).pack(side='left');ttk.Button(links,text='Edit details',command=lambda:self.external_form(self.current)).pack(side='left',padx=5);ttk.Button(links,text='Trash / restore',command=self.toggle_archive).pack(side='right')
        ttk.Label(right,text='Your application',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
        settings=ttk.Frame(right);settings.pack(fill='x');ttk.Label(settings,text='Resume base').pack(side='left');self.editor_preset=tk.StringVar(value='software');combo=ttk.Combobox(settings,textvariable=self.editor_preset,values=['hardware','software','form'],state='readonly',width=12);combo.pack(side='left',padx=8);combo.bind('<<ComboboxSelected>>',lambda e:self.changed())
        ttk.Button(settings,text='Rebuild skeletons',command=self.rebuild).pack(side='right')
        self.editor_tabs=ttk.Notebook(right);self.editor_tabs.pack(fill='both',expand=True,pady=8)
        self.letter_editor=self.editor(self.editor_tabs,'Cover letter');self.resume_editor=self.editor(self.editor_tabs,'Resume');self.notes_editor=self.editor(self.editor_tabs,'Notes & next action')
        self.build_workflow(right)
        self.save_label=tk.StringVar(value='Choose a job to begin.');ttk.Label(right,textvariable=self.save_label,wraplength=430).pack(anchor='w')
        buttons=ttk.Frame(right);buttons.pack(fill='x',pady=8);ttk.Button(buttons,text='Save edits',command=self.save_current).pack(side='left');ttk.Button(buttons,text='Export PDFs',command=self.export_documents,style='Primary.TButton').pack(side='right')
        bottom=ttk.Frame(self.jobs_frame);bottom.pack(fill='x',pady=(10,0));self.status=tk.StringVar(value='To review');ttk.Label(bottom,text='Application status').pack(side='left');ttk.Combobox(bottom,textvariable=self.status,values=['To review','Draft prepared','Ready','Already submitted','Skip'],state='readonly',width=18).pack(side='left',padx=8);ttk.Button(bottom,text='Set for selected',command=self.set_status).pack(side='left');ttk.Button(bottom,text='Next posting →',command=lambda:self.navigate(1)).pack(side='right');ttk.Button(bottom,text='← Previous',command=lambda:self.navigate(-1)).pack(side='right',padx=6)
        self.feedback=tk.StringVar();ttk.Label(self.jobs_frame,textvariable=self.feedback,wraplength=1250).pack(anchor='w',pady=5)
        # Reserve action rows before allocating expanding content.
        bottom.pack_configure(before=self.main_panes)
        buttons.pack_configure(before=self.editor_tabs)
        self.building=False;self.refresh();self.say('Import a shortlist or add an external posting. Select a job to review and edit side by side.');root.bind('<Control-s>',lambda e:self.save_current());root.bind('<Control-f>',lambda e:search.focus_set())
    def say(self,text):
        if hasattr(self,'feedback'):self.feedback.set(text)
    def reader(self,tabs,title):
        frame=ttk.Frame(tabs);tabs.add(frame,text=title);box=tk.Text(frame,wrap='word',font=('Segoe UI',11),background='white',foreground='#253b4c',relief='flat',padx=18,pady=16,spacing3=8,width=35);scroll=ttk.Scrollbar(frame,command=box.yview);scroll.pack(side='right',fill='y');box.configure(yscrollcommand=scroll.set);box.pack(fill='both',expand=True);box.tag_configure('heading',font=('Segoe UI',12,'bold'),foreground='#205e87',spacing1=16,spacing3=8);box.tag_configure('muted',foreground='#647886',font=('Segoe UI',9));box.configure(state='disabled');return box
    def editor(self,tabs,title):
        frame=ttk.Frame(tabs);tabs.add(frame,text=title);box=tk.Text(frame,wrap='word',undo=True,font=('Segoe UI',11),background='#fffefb',relief='flat',padx=14,pady=14,width=35);scroll=ttk.Scrollbar(frame,command=box.yview);scroll.pack(side='right',fill='y');box.configure(yscrollcommand=scroll.set);box.pack(fill='both',expand=True);box.bind('<<Modified>>',lambda e,b=box:self.modified(b));return box
    def modified(self,box):
        if box.edit_modified():
            box.edit_modified(False)
            if not self.building:self.changed()
    def changed(self):
        if not self.current:return
        self.dirty=True;self.save_label.set('Unsaved edits…');self.update_readiness()
        if self.pending:self.root.after_cancel(self.pending)
        self.pending=self.root.after(650,self.save_current)
    def save_current(self):
        if self.pending:self.root.after_cancel(self.pending);self.pending=None
        if not self.current or not self.dirty:return True
        try:
            id=self.current['id'];load(self.store,id)
            with self.store.connect() as db:
                db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?,?,?,?)',(id,self.letter_editor.get('1.0','end-1c'),self.editor_preset.get(),self.notes_editor.get('1.0','end-1c'),now()))
                db.execute('CREATE TABLE IF NOT EXISTS resume_drafts (job_id TEXT PRIMARY KEY,text TEXT NOT NULL,updated TEXT NOT NULL)');db.execute('INSERT OR REPLACE INTO resume_drafts VALUES (?,?,?)',(id,self.resume_editor.get('1.0','end-1c'),now()))
            self.dirty=False;self.save_label.set('Saved locally · status is set separately');return True
        except Exception as e:messagebox.showerror('Could not save',str(e));return False
    def refresh(self):
        if self.building:return
        if not self.save_current():return
        selected=self.table.selection();self.table.delete(*self.table.get_children());self.visible=[]
        for j in sorted(self.store.all(),key=lambda x:(deadline(x.get('deadline')) or date.max,x.get('title',''))):
            mode=self.view_filter.get();due=deadline(j.get('deadline'));archived=j.get('archived',False)
            if mode=='Trash' and not archived:continue
            if mode!='Trash' and archived:continue
            if mode=='Active' and j['status'] in ('Already submitted','Skip'):continue
            if mode in ('Ready','Already submitted') and j['status']!=mode:continue
            if mode=='Due in 7 days' and (due is None or not 0<=(due-date.today()).days<=7 or j['status'] in ('Already submitted','Skip')):continue
            source=self.source_filter.get()
            if source=='SFU' and not j['id'].isdigit():continue
            if source=='External' and j['id'].isdigit():continue
            letter=self.letter_filter.get()
            if letter=='Needs checking' and j.get('coverLetter') in ('Required','Not requested','Optional'):continue
            if letter not in ('All letters','Needs checking') and j.get('coverLetter')!=letter:continue
            if self.query.get().casefold() not in json.dumps(j,ensure_ascii=False).casefold():continue
            self.visible.append(j['id']);self.table.insert('', 'end',iid=j['id'],text=j.get('title','')+'\n'+j.get('employer','')+' · '+j['status'],values=(due.strftime('%b %d') if due else '?',),tags=('past',) if due and due<date.today() else ())
        self.summary.set(str(len(self.visible))+' postings')
        retained=[id for id in selected if id in self.visible]
        if retained:self.table.selection_set(retained)
        elif self.visible:self.table.selection_set(self.visible[0])
        else:self.clear()
    def clear(self):
        self.current=None;self.building=True
        for box in (self.letter_editor,self.resume_editor,self.notes_editor):box.delete('1.0','end');box.edit_modified(False)
        for box in (self.posting,self.match,self.raw):box.configure(state='normal');box.delete('1.0','end');box.configure(state='disabled')
        self.building=False;self.job_title.set('No posting selected');self.job_meta.set('Import jobs, change your filters, or add an external posting.');self.save_label.set('');self.bulk.pack_forget();self.update_readiness()
    def details(self,event=None):
        if self.building:return
        ids=self.table.selection()
        if len(ids)>1:self.bulk.pack(fill='x',before=self.main_panes,pady=(0,8));self.bulk_label.configure(text=f'{len(ids)} selected');return
        self.bulk.pack_forget()
        if len(ids)!=1:return
        if self.current and self.current['id']==ids[0]:return
        if not self.save_current():return
        self.load_job(self.store.get(ids[0]))
    def load_job(self,j):
        self.current=j;self.building=True
        profile=json.loads(self.profile.read_text(encoding='utf-8-sig'));r=analyse(j,profile);draft=load(self.store,j['id']);kind=draft[1] if draft else r['preset'] if r['preset'] in profile['presets'] else 'software'
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS resume_drafts (job_id TEXT PRIMARY KEY,text TEXT NOT NULL,updated TEXT NOT NULL)');resume=db.execute('SELECT text FROM resume_drafts WHERE job_id=?',(j['id'],)).fetchone()
        self.job_title.set(j['title']);self.job_meta.set(j.get('employer','')+'\n'+('External posting' if not j['id'].isdigit() else 'SFU · '+j['id'])+' · '+j['status']);self.status.set(j['status']);self.editor_preset.set(kind)
        for box,text in [(self.letter_editor,draft[0] if draft else starter(r,profile)),(self.resume_editor,resume[0] if resume else resume_skeleton(j,profile,kind)),(self.notes_editor,draft[2] if draft else '')]:box.delete('1.0','end');box.insert('1.0',text);box.edit_modified(False);box.edit_reset()
        self.posting.configure(state='normal');self.posting.delete('1.0','end')
        def section(title,text):self.posting.insert('end',title+'\n','heading');self.posting.insert('end',str(text or 'Not captured — check the original posting.')+'\n')
        section('Application at a glance','Deadline: '+str(j.get('deadline') or 'Unknown')+'\nCover letter: '+str(j.get('coverLetter','Unclear'))+'\nDocuments: '+str(j.get('documents') or 'Check source')+'\nLocation: '+str(j.get('location') or 'Not captured')+'\nDuration: '+str(j.get('duration') or 'Not captured'))
        section('Application instructions',j.get('method'));section('Recipient / contact',contact(j)+'\n'+str(j.get('contactEmail') or ''))
        for part in j.get('sections') or [{'label':'Job description','text':j.get('description','')}]:section(part['label'],part['text'])
        for link in j.get('links',[]):section(link.get('label','Posting link'),link.get('url'))
        self.posting.insert('end','\nSaved snapshot: '+str(j.get('collectedAt') or j.get('lastSeen') or 'Unknown')+'\nExternal pages and attachments are not included.','muted');self.posting.configure(state='disabled');self.posting.yview_moveto(0)
        evidence='\n\n'.join(x['term']+' — '+'; '.join(x['sources']) for x in r['evidence'])
        for box,text in [(self.match,'CHECK BEFORE APPLYING\n'+'\n'.join(r['flags'])+'\n\nSUPPORTED TERMS\n'+evidence+'\n\nNOT IN YOUR SAVED PROFILE\n'+', '.join(r['gaps'])+'\n\nKeyword matches are not an ATS score. Use only skills you can support.'),(self.raw,j.get('rawText') or j.get('description') or 'Not captured')]:box.configure(state='normal');box.delete('1.0','end');box.insert('1.0',text);box.configure(state='disabled')
        self.update_readiness()
        self.building=False;self.dirty=False;self.save_label.set('Saved draft loaded' if draft or resume else 'Skeletons prepared · replace bracketed prompts before PDF export')
    def select_all(self):self.table.selection_set(self.table.get_children());return 'break'
    def navigate(self,offset):
        ids=list(self.table.get_children());chosen=self.table.selection()
        if not ids:return
        at=ids.index(chosen[0]) if chosen and chosen[0] in ids else 0;id=ids[max(0,min(len(ids)-1,at+offset))];self.table.selection_set(id);self.table.see(id)
    def rebuild(self):
        if not self.current:return
        if not messagebox.askyesno('Rebuild skeletons?','Replace both editor documents with new skeletons from your saved profile? Your custom wording will be replaced.'):return
        p=json.loads(self.profile.read_text(encoding='utf-8-sig'));r=analyse(self.current,p)
        for box,text in [(self.letter_editor,starter(r,p)),(self.resume_editor,resume_skeleton(self.current,p,self.editor_preset.get()))]:box.delete('1.0','end');box.insert('1.0',text)
        self.changed()
    def import_json(self):
        if not self.save_current():return
        f=filedialog.askopenfilename(filetypes=[('Collected jobs','*.json')])
        if not f:return
        try:jobs,meta=read_import(f);summary=preview(self.store,jobs)
        except Exception as e:messagebox.showerror('Import rejected',str(e));return
        w=tk.Toplevel(self.root);w.title('Preview shortlist import');w.geometry('580x400');w.transient(self.root);w.grab_set()
        ttk.Label(w,text=f"{len(jobs)} incoming postings\n{summary['new']} new · {summary['updated']} existing",font=('Segoe UI',15,'bold')).pack(anchor='w',padx=20,pady=20)
        choice=tk.StringVar(value='merge');ttk.Radiobutton(w,text='Update/add — keep the existing shortlist',variable=choice,value='merge').pack(anchor='w',padx=20,pady=8)
        allowed=bool(jobs) and all(j['id'].isdigit() for j in jobs) and meta.get('collection',{}).get('complete') is not False
        ttk.Radiobutton(w,text=f"Replace active SFU shortlist — move {len(summary['archive'])} absent jobs to Trash",variable=choice,value='replace',state='normal' if allowed else 'disabled').pack(anchor='w',padx=20,pady=8)
        confirmed=tk.BooleanVar();ttk.Checkbutton(w,text='This file covers my complete intended SFU shortlist, not just one page/test.',variable=confirmed).pack(anchor='w',padx=20,pady=12)
        ttk.Label(w,text='Drafts and external jobs stay. Submitted jobs stay in history. Trash is reversible. An incomplete collection cannot replace your shortlist.',wraplength=510).pack(anchor='w',padx=20,pady=8)
        def apply():
            if choice.get()=='replace' and not confirmed.get():messagebox.showinfo('Confirm collection scope','Check that the file covers your intended shortlist, or choose Update/add.',parent=w);return
            try:import_jobs(self.store,jobs,choice.get()=='replace');w.destroy();self.current=None;self.refresh();self.say('Imported '+str(len(jobs))+' jobs. Saved drafts retained.')
            except Exception as e:messagebox.showerror('Import failed',str(e),parent=w)
        ttk.Button(w,text='Import',command=apply).pack(side='right',padx=20,pady=15);ttk.Button(w,text='Cancel',command=w.destroy).pack(side='right')
    def external_form(self,job=None):
        if not self.save_current():return
        w=tk.Toplevel(self.root);w.title('Edit posting details' if job else 'Add a job from any website');w.geometry(f'820x{min(800,self.root.winfo_screenheight()-120)}+40+30');w.transient(self.root);w.grab_set();fields={}
        ttk.Label(w,text='Paste the full posting once. It will use the same drafts, PDFs and tracking as SFU jobs.',wraplength=760).pack(anchor='w',padx=14,pady=12)
        for key,label in [('title','Job title'),('employer','Employer'),('sourceUrl','Original posting URL'),('deadline','Deadline (YYYY-MM-DD if known)'),('documents','Required documents (copy the exact wording)'),('contactName','Cover-letter recipient (if listed)')]:
            row=ttk.Frame(w);row.pack(fill='x',padx=14,pady=3);ttk.Label(row,text=label,width=39).pack(side='left');entry=ttk.Entry(row);entry.pack(side='left',fill='x',expand=True);entry.insert(0,str(job.get(key,'') or '') if job else '');fields[key]=entry
        text=tk.Text(w,wrap='word',font=('Segoe UI',11));text.pack(fill='both',expand=True,padx=14,pady=12)
        if job:text.insert('1.0',job.get('description',''))
        def add():
            try:
                record=external(fields['title'].get(),fields['employer'].get(),text.get('1.0','end'),fields['sourceUrl'].get(),fields['deadline'].get(),fields['documents'].get(),fields['contactName'].get())
                if job:record={**job,**record,'id':job['id'],'sourceType':'SFU' if job['id'].isdigit() else 'external','sections':[{'label':'Locally edited posting','text':text.get('1.0','end').strip()}]}
                elif self.store.get(record['id']) and not messagebox.askyesno('Posting already exists','Update the existing posting? Its drafts and status will stay.',parent=w):return
                self.store.save(record);w.destroy();self.current=None;self.view_filter.set('Active');self.source_filter.set('All sources');self.query.set('');self.refresh()
                if self.table.exists(record['id']):self.table.selection_set(record['id'])
                self.say('Posting saved. Review the extracted cover-letter requirement and deadline.')
            except Exception as e:messagebox.showerror('Could not save posting',str(e),parent=w)
        ttk.Button(w,text='Save posting',command=add).pack(pady=12)
    def remove_selected(self,restore=False):
        if not self.save_current():return
        ids=self.table.selection()
        if not ids:return
        archive(self.store,ids,restore);self.current=None;self.refresh();self.say(('Restored ' if restore else 'Moved to Trash: ')+str(len(ids))+' postings. Drafts retained.')
    def toggle_archive(self):self.remove_selected(bool(self.current and self.current.get('archived')))
    def set_status(self):
        if not self.save_current():return
        ids=self.table.selection()
        if self.status.get()=='Already submitted' and not messagebox.askyesno('Record submission?',f'Mark {len(ids)} selected posting(s) as submitted? This records your action; it does not submit anything.'):return
        for id in ids:self.store.set_status(id,self.status.get())
        self.current=None;self.refresh()
    def open_source(self):
        if not self.current:return
        target=self.current.get('sourceUrl','')
        if not target:messagebox.showinfo('No source link','This posting has no direct link. Search SFU using ID '+self.current['id']);return
        try:webbrowser.open(url(target))
        except Exception as e:messagebox.showerror('Invalid link',str(e))
    def prepare_batch(self,all_visible=False):
        if self.save_current():super().prepare_batch(all_visible)
    def import_letters(self,fn):
        if not self.save_current():return
        before=set(self.root.winfo_children());fn(self)
        windows=[w for w in self.root.winfo_children() if w not in before and isinstance(w,tk.Toplevel)]
        if windows:self.root.wait_window(windows[0])
        self.current=None;self.refresh()
    def export_documents(self):
        if not self.current or not self.save_current():return
        w=tk.Toplevel(self.root);w.title('Export application documents');w.geometry('520x260');w.transient(self.root);w.grab_set();resume=tk.BooleanVar(value=True);letter=tk.BooleanVar(value=self.current.get('coverLetter')=='Required')
        ttk.Label(w,text='Saves on your Desktop inside Applications / Employer - Role - ID. Each export gets its own dated folder. Replace bracketed prompts first. Longer documents continue onto additional pages.',wraplength=460).pack(padx=20,pady=20)
        ttk.Checkbutton(w,text='Resume PDF',variable=resume).pack(anchor='w',padx=20);ttk.Checkbutton(w,text='Cover-letter PDF',variable=letter).pack(anchor='w',padx=20)
        def create():
            if not resume.get() and not letter.get():return
            from documents import render
            import tempfile,shutil
            j=self.current
            try:parent=job_folder(self.store,j)
            except Exception as e:messagebox.showerror('Folder unavailable',str(e),parent=w);return
            folder=parent/('Export-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            try:
                texts=[self.resume_editor.get('1.0','end-1c')] if resume.get() else []
                if letter.get():texts.append(self.letter_editor.get('1.0','end-1c'))
                if any(not t.strip() or re.search(r'\[[^\]]*\]|DRAFT BLOCKED|UNFINISHED DRAFT',t) for t in texts):raise ValueError('Finish or remove the bracketed prompts in your selected documents first.')
                with tempfile.TemporaryDirectory(dir=parent) as tmp:
                    tmp=Path(tmp);page_counts=[]
                    if resume.get():page_counts.append('Resume: '+str(render(self.profile,tmp/'resume.pdf',resume_text=self.resume_editor.get('1.0','end-1c')))+' page(s)')
                    if letter.get():page_counts.append('Cover letter: '+str(render(self.profile,tmp/'cover-letter.pdf',letter_text=self.letter_editor.get('1.0','end-1c'),subject=j['title']+' — '+j['id'],recipient=contact(j)))+' page(s)')
                    (tmp/'submission-checklist.txt').write_text('Role: '+j['title']+'\nEmployer: '+j['employer']+'\nSource: '+str(j.get('sourceUrl',''))+'\nDeadline: '+str(j.get('deadline','Unknown'))+'\nRequired documents: '+str(j.get('documents','Check source'))+'\n\nReview both PDFs, verify dates/recipient, attach any other required documents, and submit through the source site. Then mark submitted in Application Desk.\n',encoding='utf-8')
                    shutil.copytree(tmp,folder)
                p=progress(self.store,j['id']);p['exported']=now();put(self.store,j['id'],p)
                w.destroy();messagebox.showinfo('PDFs exported','\n'.join(page_counts)+'\n\nReview all pages and check any page limits in the posting.');self.say('Exported documents to '+str(folder)+'. No application was submitted.');os.startfile(str(folder))
            except Exception as e:messagebox.showerror('Export stopped',str(e),parent=w)
        ttk.Button(w,text='Export selected PDFs',command=create).pack(pady=18)
    def close(self):
        if not self.save_current():return
        self.stop.set();self.root.destroy()
