"""Portable local backup of Application Desk jobs, drafts and candidate facts."""
import sqlite3, tempfile, zipfile, os
from pathlib import Path
from contextlib import closing

def export_backup(store,profile,destination):
    destination=Path(destination)
    # Build beside the destination, then replace only after the ZIP is complete.
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.application-backup-') as tmp:
        tmp=Path(tmp);database=tmp/'jobs.sqlite3'
        with closing(sqlite3.connect(store.path)) as source,closing(sqlite3.connect(database)) as target:
            source.backup(target)
        archive=tmp/'backup.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(database,'data/jobs.sqlite3');z.write(profile,'profile.json')
            z.writestr('RESTORE.txt','Application Desk backup: jobs, application statuses, saved drafts and candidate profile.\nTo restore: close Application Desk, back up its current data/jobs.sqlite3 and profile.json, then replace them with these files in local-tool/. Restart Application Desk.\nThis backup contains personal information. It does not contain browser sessions, credentials, exported PDFs or resumes outside the profile.\n')
        os.replace(archive,destination)

def backup_dialog(app):
    from tkinter import filedialog,messagebox
    from datetime import datetime
    target=filedialog.asksaveasfilename(title='Back up jobs, drafts and profile',initialfile='application-desk-'+datetime.now().strftime('%Y-%m-%d')+'.zip',defaultextension='.zip',filetypes=[('ZIP backup','*.zip')])
    if not target:return
    try:export_backup(app.store,app.profile,target);app.say('Saved backup: '+target);messagebox.showinfo('Backup saved','Your jobs, statuses, letter drafts and profile are backed up. The ZIP includes restore instructions.')
    except Exception as e:messagebox.showerror('Backup failed',str(e))
