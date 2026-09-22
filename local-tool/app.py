"""Local desktop application. Launch with Start.cmd."""
from pathlib import Path
import sys,json,threading,queue,os,traceback
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from core import ROOT,Store,packet,pasted_posting
from documents import render

class App:
    def __init__(self,root):
        self.root=root;root.title('Application Desk');root.geometry('1120x760');root.minsize(900,600)
        self.store=Store();self.profile=ROOT/'profile.json';self.events=queue.Queue();self.worker=None
        self.ready=threading.Event();self.stop=threading.Event()
        if not self.profile.exists():
            import shutil
            shutil.copyfile(ROOT/'profile.example.json',self.profile)
        style=ttk.Style();style.theme_use('clam');style.configure('Treeview',rowheight=29,font=('Segoe UI',10));style.configure('TButton',padding=7)
        top=ttk.Frame(root,padding=14);top.pack(fill='x')
        ttk.Label(top,text='Application Desk',font=('Segoe UI',20,'bold')).pack(side='left')
        ttk.Label(top,text='Local files • No AI calls • Review before submitting',font=('Segoe UI',10)).pack(side='right')
        tabs=ttk.Notebook(root);tabs.pack(fill='both',expand=True,padx=14,pady=(0,14))
        jobs=ttk.Frame(tabs,padding=10);docs=ttk.Frame(tabs,padding=14);tabs.add(jobs,text='Jobs and collection');tabs.add(docs,text='PDF documents');self.tabs=tabs;self.docs=docs
        bar=ttk.Frame(jobs);bar.pack(fill='x')
        self.connect_button=ttk.Button(bar,text='Extension folder',command=lambda:os.startfile(str(ROOT.parent/'edge-extension')));self.connect_button.pack(side='left')
        self.scan_button=ttk.Button(bar,text='Import collected jobs',command=self.import_json);self.scan_button.pack(side='left',padx=5)
        # Collection now runs through the Edge extension.
        ttk.Button(bar,text='Import JSON',command=self.import_json).pack(side='right')
        ttk.Button(bar,text='Paste posting',command=self.paste_posting).pack(side='right',padx=5)
        ttk.Label(jobs,text='In normal Edge: open SFU Favourites, click the Collector extension, save the jobs file, then import it here.').pack(anchor='w',pady=8)
        filterbar=ttk.Frame(jobs);filterbar.pack(fill='x')
        self.query=tk.StringVar();self.query.trace_add('write',lambda *_:self.refresh())
        ttk.Label(filterbar,text='Search:').pack(side='left');ttk.Entry(filterbar,textvariable=self.query,width=40).pack(side='left',padx=5)
        self.hide=tk.BooleanVar(value=True);ttk.Checkbutton(filterbar,text='Hide submitted / skipped',variable=self.hide,command=self.refresh).pack(side='left')
        self.letter_filter=tk.StringVar(value='All letters')
        ttk.Combobox(filterbar,textvariable=self.letter_filter,values=['All letters','Required','Not requested','Optional','Needs checking'],state='readonly',width=17).pack(side='right')
        self.letter_filter.trace_add('write',lambda *_:self.refresh())
        self.hide_past=tk.BooleanVar(value=False)
        ttk.Checkbutton(filterbar,text='Hide past deadlines',variable=self.hide_past,command=self.refresh).pack(side='right',padx=5)
        self.summary=tk.StringVar();ttk.Label(jobs,textvariable=self.summary).pack(anchor='w',pady=4)
        columns=('id','employer','title','deadline','coverLetter','status')
        frame=ttk.Frame(jobs);frame.pack(fill='both',expand=True,pady=8)
        self.table=ttk.Treeview(frame,columns=columns,show='headings',selectmode='extended')
        for name,width in zip(columns,[70,145,300,155,140,110]):self.table.heading(name,text={'coverLetter':'Cover letter'}.get(name,name.title()));self.table.column(name,width=width,minwidth=60)
        self.table.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(frame,command=self.table.yview);scroll.pack(side='right',fill='y');self.table.configure(yscrollcommand=scroll.set)
        self.table.bind('<<TreeviewSelect>>',self.details)
        actions=ttk.Frame(jobs);actions.pack(fill='x')
        ttk.Button(actions,text='Export selected for AI (max 5)',command=self.export).pack(side='left')
        self.status=tk.StringVar(value='To review');ttk.Combobox(actions,textvariable=self.status,values=['To review','Draft prepared','Ready','Already submitted','Skip'],state='readonly',width=19).pack(side='left',padx=8)
        ttk.Button(actions,text='Set status',command=self.set_status).pack(side='left')
        from backup import backup_dialog
        ttk.Button(actions,text='Back up data',command=lambda:backup_dialog(self)).pack(side='right',padx=5)
        ttk.Button(actions,text='Open saved files',command=lambda:os.startfile(str(ROOT))).pack(side='right')
        batchbar=ttk.Frame(jobs);batchbar.pack(fill='x',pady=5)
        from review import open_review
        from draft_import import import_window
        ttk.Button(batchbar,text='Import drafted letters',command=lambda:import_window(self)).pack(side='right')
        ttk.Button(batchbar,text='Review & edit draft',command=lambda:open_review(self)).pack(side='left',padx=(0,8))
        self.table.bind('<Double-1>',lambda e:open_review(self))
        ttk.Button(batchbar,text='Prepare selected applications',command=self.prepare_batch).pack(side='left')
        ttk.Button(batchbar,text='Prepare all visible jobs',command=lambda:self.prepare_batch(True)).pack(side='left',padx=8)
        self.detail=tk.Text(jobs,height=6,wrap='word',font=('Segoe UI',10));self.detail.pack(fill='x',pady=8)
        self.log=tk.Text(jobs,height=4,wrap='word',font=('Consolas',9));self.log.pack(fill='x')
        ttk.Label(docs,text='Create a PDF from saved content',font=('Segoe UI',15,'bold')).pack(anchor='w')
        ttk.Label(docs,text='Resume presets reuse your saved facts. Letters use the text you paste below. No text is sent online.').pack(anchor='w',pady=8)
        r=ttk.Frame(docs);r.pack(fill='x');self.preset=tk.StringVar(value='software')
        ttk.Combobox(r,textvariable=self.preset,values=['hardware','software','form'],state='readonly').pack(side='left')
        ttk.Button(r,text='Generate resume PDF',command=self.resume).pack(side='left',padx=8)
        ttk.Button(r,text='Open profile file',command=lambda:os.startfile(str(self.profile))).pack(side='right')
        ttk.Separator(docs).pack(fill='x',pady=15)
        ttk.Label(docs,text='Letter subject').pack(anchor='w');self.subject=tk.StringVar();ttk.Entry(docs,textvariable=self.subject).pack(fill='x')
        ttk.Label(docs,text='Recipient and address (optional)').pack(anchor='w',pady=(7,0));self.recipient=tk.Text(docs,height=3,font=('Segoe UI',10));self.recipient.pack(fill='x')
        ttk.Label(docs,text='Reviewed letter text, including greeting and sign-off').pack(anchor='w',pady=(7,0));self.letter=tk.Text(docs,wrap='word',font=('Segoe UI',11));self.letter.pack(fill='both',expand=True)
        buttons=ttk.Frame(docs);buttons.pack(fill='x',pady=8)
        ttk.Button(buttons,text='Load letter text',command=self.load_letter).pack(side='left');ttk.Button(buttons,text='Generate letter PDF',command=self.cover).pack(side='right')
        self.refresh();self.say('Loaded your saved shortlist. Seed records need a fresh scan for full posting descriptions.')
        root.after(150,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)
    def say(self,text):self.log.insert('end',text+'\n');self.log.see('end')
    def poll(self):
        try:
            while True:self.say(self.events.get_nowait());self.refresh()
        except queue.Empty:pass
        if self.worker and not self.worker.is_alive():self.connect_button.configure(state='normal');self.scan_button.configure(state='disabled')
        self.root.after(150,self.poll)
    def refresh(self):
        selected=self.table.selection();self.table.delete(*self.table.get_children())
        from batch import deadline
        from datetime import date
        for j in sorted(self.store.all(),key=lambda item:(deadline(item.get('deadline')) or date.max,item.get('title',''))):
            due=deadline(j.get('deadline'))
            if j.get('archived'):continue
            if self.hide_past.get() and due is not None and due<date.today():continue
            letter_mode=self.letter_filter.get()
            if letter_mode=='Needs checking' and j.get('coverLetter') in ['Required','Not requested','Optional']:continue
            if letter_mode not in ['All letters','Needs checking'] and j.get('coverLetter')!=letter_mode:continue
            if self.hide.get() and j['status'] in ['Already submitted','Skip']:continue
            if self.query.get().lower() not in json.dumps(j).lower():continue
            self.table.insert('', 'end',iid=j['id'],values=[j.get(k,'') for k in ('id','employer','title','deadline','coverLetter','status')])
        self.summary.set(f'{len(self.table.get_children())} jobs shown  |  earliest parsed deadline first  |  double-click a job to edit its draft')
        for id in selected:
            if self.table.exists(id):self.table.selection_add(id)
    def details(self,event=None):
        ids=self.table.selection();self.detail.delete('1.0','end')
        if len(ids)!=1:return
        j=self.store.get(ids[0]);self.detail.insert('end',f"{j['title']} ({j['id']})\nDocuments: {j.get('documents','Refresh posting for complete document list')}\n{j.get('method','')}\n"+'\n'.join(j.get('evidence',[]))+f"\n{j.get('note','')}\nEmployer forms and attachments not checked.")
    def connect(self):
        if self.worker and self.worker.is_alive():return
        self.ready.clear();self.stop.clear();self.connect_button.configure(state='disabled');self.scan_button.configure(state='normal')
        def work():
            try:
                from collector import collect
                collect(self.store,self.ready,self.stop,self.events.put)
            except Exception as e:self.events.put('Collector stopped: '+str(e))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def scan(self):self.ready.set();self.scan_button.configure(state='disabled')
    def import_json(self):
        f=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if f:
            try:self.say(f'Imported {self.store.import_file(f)} new/changed jobs.');self.refresh()
            except Exception as e:messagebox.showerror('Import failed',str(e))
    def paste_posting(self):
        w=tk.Toplevel(self.root);w.title('Paste a posting from your working browser');w.geometry('760x600')
        ttk.Label(w,text='Copy the full posting, including Application Information. No browser connection is needed.',wraplength=720).pack(padx=12,pady=10)
        entries={}
        for key,label in [('id','SFU job ID'),('title','Job title'),('employer','Employer')]:
            ttk.Label(w,text=label).pack(anchor='w',padx=12);e=ttk.Entry(w);e.pack(fill='x',padx=12);entries[key]=e
        chosen=self.table.selection()
        if len(chosen)==1:
            j=self.store.get(chosen[0])
            for k,e in entries.items():e.insert(0,j.get(k,''))
        text=tk.Text(w,wrap='word');text.pack(fill='both',expand=True,padx=12,pady=10)
        def save():
            try:
                record=pasted_posting(**{k:e.get() for k,e in entries.items()},text=text.get('1.0','end'))
                old=self.store.get(record['id'])
                if old:
                    for k in ['resumeBase','note','fitReview','preparedFiles','preparationStatus']:
                        if k in old:record[k]=old[k]
                self.store.save(record);self.refresh();self.say('Saved pasted posting '+record['id']+'. Check its extracted document fields.');w.destroy()
            except Exception as e:messagebox.showerror('Could not save',str(e),parent=w)
        ttk.Button(w,text='Save posting locally',command=save).pack(pady=10)
    def export(self):
        ids=self.table.selection()
        if not 1<=len(ids)<=5:messagebox.showinfo('Select jobs','Select one to five jobs using Ctrl-click.');return
        f=filedialog.asksaveasfilename(initialdir=ROOT,initialfile='application-batch.json',defaultextension='.json')
        if f:
            try:n=packet(self.store,ids,self.profile,f);self.say(f'Saved batch ({n:,} characters). Attach it for tailored writing.');messagebox.showinfo('Batch ready','Saved. Attach this JSON in your AI conversation.')
            except Exception as e:messagebox.showerror('Export failed',str(e))
    def prepare_batch(self,all_visible=False):
        ids=self.table.get_children() if all_visible else self.table.selection()
        if not ids:messagebox.showinfo('Choose jobs','Select jobs or use Prepare all visible jobs.');return
        parent=filedialog.askdirectory(title='Choose where to save the application batch')
        if not parent:return
        try:
            from batch import prepare
            from datetime import datetime
            folder=Path(parent)/('applications-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
            from review import load
            saved={id:load(self.store,id) for id in ids}
            with self.store.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS resume_drafts (job_id TEXT PRIMARY KEY, text TEXT NOT NULL, updated TEXT NOT NULL)')
                resume_drafts=dict(db.execute('SELECT job_id,text FROM resume_drafts'))
            count=prepare([self.store.get(id) for id in ids],json.loads(self.profile.read_text(encoding='utf-8-sig')),folder,drafts=saved,resume_drafts=resume_drafts)
            self.say(f'Prepared {count} jobs: {folder}. Open index.html for the queue; letter starters need editing.')
            os.startfile(str(folder/'index.html'))
        except Exception as e:messagebox.showerror('Could not prepare batch',str(e))
    def set_status(self):
        for id in self.table.selection():self.store.set_status(id,self.status.get())
        self.refresh()
    def resume(self):
        f=filedialog.asksaveasfilename(initialdir=ROOT,initialfile='resume_'+self.preset.get()+'.pdf',defaultextension='.pdf')
        if f:self.make_pdf(f,kind=self.preset.get())
    def load_letter(self):
        f=filedialog.askopenfilename(filetypes=[('Text','*.txt')])
        if f:self.letter.delete('1.0','end');self.letter.insert('1.0',Path(f).read_text(encoding='utf-8-sig'))
    def cover(self):
        f=filedialog.asksaveasfilename(initialdir=ROOT,initialfile='cover_letter.pdf',defaultextension='.pdf')
        if f:self.make_pdf(f,letter_text=self.letter.get('1.0','end'),subject=self.subject.get(),recipient=self.recipient.get('1.0','end'))
    def make_pdf(self,f,**kwargs):
        try:pages=render(self.profile,f,**kwargs);messagebox.showinfo('PDF ready',f'Saved {pages}-page PDF. Review it and check the posting’s page limits before submitting.');os.startfile(f)
        except Exception as e:messagebox.showerror('Could not create PDF',str(e))
    def close(self):self.stop.set();self.root.destroy()

if __name__=='__main__':
    from workspace import Workspace
    root=tk.Tk();Workspace(root);root.mainloop()
