# 🗂️ Smart File Organizer

A tool that takes a messy folder full of badly named files (`Documents_20250219_dbms expt 9 10.pdf`, `IMG_4821.jpg`, stuff like that) and sorts it into clean folders by subject. No manual renaming, no dragging files around by hand.

It comes in two versions that use the same core logic:

- **`file_organizer.py`** :- a desktop app (Python + Tkinter) that organizes files directly on your computer
- **A small web app** (`index.html`, `script.js`, `styles.css`) :- drop files in, get back an organized ZIP. Runs entirely in your browser, nothing gets uploaded anywhere. Hosted on Vercel.

---

## Why I made this

Files from downloads or exports almost never have clean names. Sorting them by file type just shoves every PDF into one giant "Documents" folder, which doesn't actually fix anything. This tool reads the actual filename, figures out what subject it's about, and groups similar files together — so all your notes and similar content files end up in one folder, all your TOC files in another, and so on.

---

## How it figures out the sorting

For each file, it:

1. **Checks for a known subject first.** It splits the filename into words, ignores filler words like "unit", "expt", "cover", "viva", and checks the rest against a list of known subjects (dbms, java, toc, matlab, dsa, os, etc). If it finds a match, that's the folder.

2. **If nothing matches, it looks for repeated words.** Say a bunch of files don't match anything in the list — it checks if they share some other word in common. If two or more files repeat the same word, they get grouped under that word. Anything with no pattern at all just goes into a `Misc` folder instead of getting its own random folder.

It also checks the actual content of each file (not just the name) to catch exact duplicates, so you don't end up with the same file copied twice under two different names.

---

## Tech Stack

**Desktop app (`file_organizer.py`)**
- Python 3 + Tkinter for the interface
- `threading` so the app doesn't freeze while sorting a big folder
- `hashlib` (MD5) for catching duplicate files
- `json` to keep a log of the last run, so it can be undone
- `shutil` / `pathlib` for the actual moving and renaming of files

**Web app**
- Just plain HTML, CSS, and JavaScript — no framework
- `crypto.subtle` (Web Crypto API) for hashing files to catch duplicates, done fully in the browser
- The File API for drag-and-drop and folder selection
- JSZip to bundle everything into a downloadable ZIP

---

## Features

- Groups files by subject, not just by file type
- Skips exact duplicate files instead of copying them twice
- Renames files to `Subject_YYYYMMDD_originalname.ext` so everything stays sorted by date within its folder
- Reads real photo dates from EXIF data when available (desktop version)
- Undo button — every run gets logged, so you can put everything back exactly where it was
- Desktop version opens the folder automatically once it's done
- Web version never uploads anything — everything happens locally in your browser

---

## Running the Desktop App

```bash
python3 file_organizer.py
```
That's it. Pick a folder, hit Organize, done. 

---

## The Web App

Live and hosted on Vercel. Drop your files in, hit organize, download the ZIP.

---

## Project Structure

```
file_organizer.py     # desktop app

index.html            # web app page
script.js             # sorting logic + drag-and-drop + zip export
styles.css            # styling
```

---

## Known Limitations

- The subject list is fixed — it won't recognize a subject it doesn't know unless a few files repeat the same word (the fallback grouping)
- The web version can't sort files in place on your actual computer — browsers don't allow that, so it always hands back a ZIP instead
- EXIF-based photo dating only works in the desktop version
- Duplicate detection only catches exact same-content files, not two slightly different versions of the same thing

---

## Ideas for Later

- Let people edit the subject list from inside the app instead of editing the code
- Add a preview step before files actually get moved
- Bring EXIF photo dating to the web version too
- Package the desktop app as a standalone executable so people don't need Python installed to run it
- global user count update 
