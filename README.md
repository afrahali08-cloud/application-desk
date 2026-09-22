# Application Desk

A local Windows desktop workspace for organizing job applications, with an SFU MyExperience browser extension.

## Features
- Import captured postings or paste jobs from other websites.
- Review postings alongside editable resume and cover-letter skeletons.
- Track per-job checklists, application status and reusable answers.
- Prepare batches, export PDFs, and organize files under Desktop/Applications.
- Replace shortlists with reversible Trash and preserve saved drafts.

## Run locally
Requires Windows, Python 3.11 or later with Tkinter, and Edge or Chrome for the optional extension.

1. Install dependencies: `python -m pip install -r requirements.txt`.
2. Copy `local-tool/profile.example.json` to `local-tool/profile.json` and replace placeholders with your own verified facts. Profile presets select project keys; projects have title, meta and bullets; experience has title, dates and bullets; education has title and lines.
3. Run `python local-tool/app.py` or double-click `local-tool/Start.cmd`.
4. For the extension, enable Developer mode on the browser extensions page and load the `edge-extension` folder unpacked. Sign in to SFU manually, open your favourites, and use the extension to collect the pages you choose. Export JSON and import it into Desk.

## Privacy and limitations
Personal profiles, databases, saved answers, generated documents, browser sessions and real postings are excluded from this repository. The app creates local private data when used. Review staged files before publishing changes; gitignore is not a secret scanner. Backups contain personal data. Keep them private.

The extension operates on SFU pages you can access. It does not bypass login or access controls. Other websites use manual text intake. Review all facts, dates, requirements and PDFs before submission. The app does not submit applications. Keyword matching is a review aid, not an ATS score. Automated review packets contain candidate information: share only deliberately.

This is an early Windows release. A clean-machine installation and live portal compatibility still need validation. No affiliation with SFU is implied.
