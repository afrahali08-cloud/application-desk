"""Persistent application checklists, answer snippets and organized folders."""
import hashlib,json,re,os,shutil
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from core import ROOT,now

STEPS=[('requirements','Read requirements and confirm eligibility'),('resume','Review and tailor resume'),('letter','Review cover letter / confirm not needed'),('extras','Gather other required documents'),('final','Check final files and application answers')]
def init(store):
 with store.connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS application_progress (job_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
  c.execute('CREATE TABLE IF NOT EXISTS quick_answers (label TEXT PRIMARY KEY,answer TEXT NOT NULL)')
def progress(store,id):
 init(store)
 with store.connect() as c:r=c.execute('SELECT payload FROM application_progress WHERE job_id=?',(id,)).fetchone()
 return json.loads(r[0]) if r else {}
def put(store,id,p):
 init(store)
 with store.connect() as c:c.execute('INSERT OR REPLACE INTO application_progress VALUES (?,?)',(id,json.dumps(p)))
def fingerprint(text):return hashlib.sha256(text.encode()).hexdigest()
def applications_root():
 # Respect Windows Desktop redirection, including OneDrive.
 if os.name=='nt':
  import winreg
  try:
   with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
    desktop=Path(os.path.expandvars(winreg.QueryValueEx(key,'Desktop')[0]))
   if desktop.is_absolute() and desktop.is_dir():return desktop/'Applications'
  except OSError:pass
 for desktop in (Path.home()/'OneDrive'/'Desktop',Path.home()/'Desktop'):
  if desktop.is_dir():return desktop/'Applications'
 raise OSError('Could not locate your Desktop. No files were exported.')

def job_folder(store,job):
 p=progress(store,job['id']);root=applications_root();root.mkdir(parents=True,exist_ok=True)
 name=p.get('folder')
 if not name:
  def safe(s):return re.sub(r'[^\w .-]','_',str(s))[:45].strip(' .') or 'Application'
  name=safe(job['employer'])+' - '+safe(job['title'])+' - '+safe(job['id']);p['folder']=name;put(store,job['id'],p)
 if Path(name).name!=name:raise ValueError('Invalid saved folder name')
 target=root/name;target.mkdir(exist_ok=True);return target

class Workflow:
 def build_workflow(self,right):
  init(self.store)
  self.readiness=tk.StringVar(value='Choose a posting')
  card=ttk.Frame(right,padding=8);card.pack(fill='x',before=self.editor_tabs)
  ttk.Label(card,textvariable=self.readiness,font=('Segoe UI',10,'bold'),wraplength=390).pack(anchor='w')
  self.progress_bar=ttk.Progressbar(card,maximum=5);self.progress_bar.pack(fill='x',pady=5)
  actions=ttk.Frame(card);actions.pack(fill='x')
  ttk.Button(actions,text='✓ Checklist',command=self.show_checklist).pack(side='left')
  ttk.Button(actions,text='Open job folder',command=self.open_job_folder).pack(side='left',padx=4)
  ttk.Button(actions,text='Quick answers',command=self.quick_answers).pack(side='left')
  for box in (self.resume_editor,self.letter_editor):
   bar=ttk.Frame(box.master);bar.pack(fill='x',before=box)
   ttk.Button(bar,text='Next missing item →',command=lambda b=box:self.next_placeholder(b)).pack(side='left')
   box.tag_configure('placeholder',background='#fff0bb',foreground='#735000')
 def update_readiness(self):
  if not hasattr(self,'readiness'):return
  if not self.current:self.readiness.set('Choose a posting');self.progress_bar['value']=0;return
  p=progress(self.store,self.current['id']);checks=p.get('checks',{})
  # A review check applies to the exact text reviewed, not a later edit.
  invalid=False
  for key,box in [('resume',self.resume_editor),('letter',self.letter_editor)]:
   if checks.get(key) and p.get(key+'_hash')!=fingerprint(box.get('1.0','end-1c')):checks[key]=False;invalid=True
   box.tag_remove('placeholder','1.0','end')
   for m in re.finditer(r'\[[^\]]*\]',box.get('1.0','end-1c')):box.tag_add('placeholder',f'1.0+{m.start()}c',f'1.0+{m.end()}c')
  if invalid:checks['final']=False;p['checks']=checks;put(self.store,self.current['id'],p)
  count=sum(bool(checks.get(k)) for k,_ in STEPS);self.progress_bar['value']=count
  resume=self.resume_editor.get('1.0','end-1c');letter=self.letter_editor.get('1.0','end-1c')
  texts=[resume]+([letter] if self.current.get('coverLetter')!='Not requested' else [])
  gaps=sum(len(re.findall(r'\[[^\]]*\]',t)) for t in texts)
  if gaps:state=f'{gaps} placeholders to resolve'
  elif any(not t.strip() or 'DRAFT BLOCKED' in t for t in texts):state='Document text needs attention'
  elif count<5:state='Next: '+next(label for key,label in STEPS if not checks.get(key))
  else:state='Review checklist complete · export and submit'
  self.readiness.set(f'{count}/5 reviewed · {state}')
 def next_placeholder(self,box):
  text=box.get('1.0','end-1c');matches=list(re.finditer(r'\[[^\]]*\]',text))
  if not matches:self.say('No bracketed prompts in this document. Review its wording and facts.');return
  at=len(box.get('1.0','insert'));m=next((m for m in matches if m.start()>at),matches[0]);start=f'1.0+{m.start()}c';end=f'1.0+{m.end()}c'
  box.tag_remove('sel','1.0','end');box.tag_add('sel',start,end);box.mark_set('insert',start);box.see(start);box.focus_set()
 def open_job_folder(self):
  if self.current:
   try:os.startfile(str(job_folder(self.store,self.current)))
   except Exception as e:messagebox.showerror('Folder unavailable',str(e))
 def show_checklist(self):
  if not self.current:return
  self.save_current();self.update_readiness();j=dict(self.current);p=progress(self.store,j['id']);checks=p.setdefault('checks',{})
  w=tk.Toplevel(self.root);w.title('Application checklist');w.geometry('600x480');w.transient(self.root);w.grab_set()
  ttk.Label(w,text=j['employer']+' — '+j['title'],font=('Segoe UI',13,'bold'),wraplength=540).pack(anchor='w',padx=18,pady=16)
  ttk.Label(w,text='Your review checks are saved separately for this job.',wraplength=540).pack(anchor='w',padx=18,pady=4)
  def change(key,var):
   checks[key]=var.get()
   if key in ('resume','letter'):p[key+'_hash']=fingerprint(getattr(self,key+'_editor').get('1.0','end-1c'))
   put(self.store,j['id'],p);self.update_readiness()
  for key,label in STEPS:
   var=tk.BooleanVar(value=bool(checks.get(key)));ttk.Checkbutton(w,text=label,variable=var,command=lambda k=key,v=var:change(k,v)).pack(anchor='w',padx=18,pady=7)
  ttk.Label(w,text='Required documents: '+str(j.get('documents') or 'Check original posting'),wraplength=540).pack(anchor='w',padx=18,pady=10)
  ttk.Label(w,text='Last PDF export: '+p.get('exported','Not exported')+'\nSubmission: '+j['status'],wraplength=540).pack(anchor='w',padx=18,pady=6)
  def attach():
   files=filedialog.askopenfilenames(parent=w,title='Add transcripts or other supporting files')
   if not files:return
   target=job_folder(self.store,j)/'Supporting files';target.mkdir(exist_ok=True)
   try:
    for f in files:
     source=Path(f);dest=target/source.name
     if dest.exists():dest=target/(source.stem+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+source.suffix)
     shutil.copy2(source,dest)
    self.say('Supporting files copied to this application folder.')
   except Exception as e:messagebox.showerror('Copy failed',str(e),parent=w)
  ttk.Button(w,text='+ Add supporting files',command=attach).pack(side='left',padx=18,pady=12)
  ttk.Button(w,text='Done',command=w.destroy).pack(side='right',padx=18,pady=12)
 def quick_answers(self):
  w=tk.Toplevel(self.root);w.title('Reusable answers');w.geometry('620x500');w.transient(self.root)
  ttk.Label(w,text='Save common answers once; select and copy them for application forms.',wraplength=560).pack(padx=15,pady=12)
  label=tk.StringVar();combo=ttk.Combobox(w,textvariable=label);combo.pack(fill='x',padx=15)
  text=tk.Text(w,wrap='word',height=10,font=('Segoe UI',11));text.pack(fill='both',expand=True,padx=15,pady=10)
  def reload():
   with self.store.connect() as c:combo['values']=[r[0] for r in c.execute('SELECT label FROM quick_answers ORDER BY label')]
  def choose(e=None):
   with self.store.connect() as c:r=c.execute('SELECT answer FROM quick_answers WHERE label=?',(label.get(),)).fetchone()
   text.delete('1.0','end');text.insert('1.0',r[0] if r else '')
  def save_answer():
   if not label.get().strip():messagebox.showinfo('Name this answer','Enter a short name, such as Availability.',parent=w);return
   with self.store.connect() as c:c.execute('INSERT OR REPLACE INTO quick_answers VALUES (?,?)',(label.get().strip(),text.get('1.0','end-1c')))
   reload();self.say('Reusable answer saved locally.')
  def copy():self.root.clipboard_clear();self.root.clipboard_append(text.get('1.0','end-1c'));self.say('Answer copied. Check it suits this application before pasting.')
  def delete():
   with self.store.connect() as c:c.execute('DELETE FROM quick_answers WHERE label=?',(label.get(),))
   label.set('');text.delete('1.0','end');reload()
  combo.bind('<<ComboboxSelected>>',choose);reload()
  bar=ttk.Frame(w);bar.pack(fill='x',padx=15,pady=12)
  for name,fn in [('Save answer',save_answer),('Copy answer',copy),('Remove',delete)]:ttk.Button(bar,text=name,command=fn).pack(side='left',padx=4)
  ttk.Label(w,text='Stored locally in the app database. Avoid storing passwords here.').pack(pady=6)
