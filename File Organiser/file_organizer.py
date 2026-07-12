"""
File Organizer
A little desktop tool that sorts messy folders (like Downloads) into
subfolders based on the subject in the filename, renames files, and
skips duplicates.

Made with Python + Tkinter.
"""

import os
import re
import json
import shutil
import hashlib
import threading
import platform
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

UNDO_FILE = ".undo_log.json"

# which extensions belong to which general category
FILE_TYPES = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", "mpo"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"],
    "Audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".java", ".cpp", ".c", ".js", ".html", ".css", ".json", ".ipynb"],
}

# subjects we can recognize just from the filename
# feel free to add your own course codes here
SUBJECTS = {
    "dbms": "DBMS",
    "java": "Java",
    "toc": "TOC",
    "matlab": "MATLAB",
    "circuit": "Circuits",
    "circuits": "Circuits",
    "dlcd": "DLCD",
    "dlc": "DLC",
    "dsa": "DSA",
    "ds": "DS",
    "dm": "Discrete Maths",
    "os": "Operating Systems",
    "cn": "Computer Networks",
    "ai": "AI",
    "ml": "ML",
    "oop": "OOP",
    "python": "Python",
    "cpp": "CPP",
}

# words that show up in filenames but don't say anything about the subject
SKIP_WORDS = {
    "file", "files", "unit", "cover", "covers", "expt", "experiment",
    "experiments", "viva", "ques", "question", "questions", "sem",
    "class", "notes", "scan", "adobe", "doc", "docx", "pdf", "the",
    "of", "and", "for", "to", "new", "copy", "final", "img", "image",
    "whatsapp", "screenshot", "document", "documents",
}


def get_file_type(ext):
    ext = ext.lower()
    for category, extensions in FILE_TYPES.items():
        if ext in extensions:
            return category
    return "Others"


def get_words(name):
    words = re.split(r"[^a-zA-Z]+", name.lower())
    return [w for w in words if len(w) > 1 and w not in SKIP_WORDS]


def find_subject(words):
    for w in words:
        if w in SUBJECTS:
            return SUBJECTS[w]
    return None


def get_photo_date(path):
    # try to get the actual date a photo was taken from exif data
    # falls back to None if pillow isn't installed or there's no exif
    if not HAS_PIL:
        return None
    try:
        img = Image.open(path)
        exif = img._getexif()
        if not exif:
            return None
        for tag_id, value in exif.items():
            if TAGS.get(tag_id) == "DateTimeOriginal":
                return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None
    return None


def hash_file(path):
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def open_folder(path):
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


class Organizer:
    def __init__(self, folder, log_fn, progress_fn):
        self.folder = Path(folder)
        self.log_fn = log_fn
        self.progress_fn = progress_fn
        self.seen_hashes = {}
        self.moved = 0
        self.duplicates = 0
        self.skipped = 0
        self.move_history = []

    def run(self):
        files = [f for f in self.folder.iterdir() if f.is_file()]
        total = len(files) or 1

        # figure out subject for each file first
        plan = []
        leftovers = {}
        for f in files:
            file_type = get_file_type(f.suffix)
            words = get_words(f.stem)
            subject = find_subject(words)
            entry = {"path": f, "type": file_type, "subject": subject}
            plan.append(entry)
            if subject is None:
                leftovers.setdefault(file_type, []).append((f, words))

        # for files that didn't match a known subject, group by whatever
        # word repeats between them, otherwise dump in Misc
        for file_type, items in leftovers.items():
            word_counts = Counter()
            for _, words in items:
                word_counts.update(set(words))

            for entry in plan:
                if entry["type"] != file_type or entry["subject"] is not None:
                    continue
                words = get_words(entry["path"].stem)
                candidates = [w for w in words if word_counts.get(w, 0) >= 2]
                if candidates:
                    best = max(candidates, key=lambda w: word_counts[w])
                    entry["subject"] = best.capitalize()
                else:
                    entry["subject"] = "Misc"

        for i, entry in enumerate(plan, start=1):
            try:
                self.process_file(entry["path"], entry["subject"])
            except Exception as e:
                self.skipped += 1
                self.log_fn(f"skipped {entry['path'].name}: {e}")
            self.progress_fn(i / total * 100)

        self.log_fn(f"\ndone. moved {self.moved}, duplicates {self.duplicates}, skipped {self.skipped}")
        self.save_undo_log()

    def process_file(self, path, subject):
        file_hash = hash_file(path)
        if file_hash and file_hash in self.seen_hashes:
            self.duplicates += 1
            self.log_fn(f"duplicate of {self.seen_hashes[file_hash]}: {path.name}")
            return
        if file_hash:
            self.seen_hashes[file_hash] = path.name

        dest_folder = self.folder / subject
        dest_folder.mkdir(parents=True, exist_ok=True)

        # for photos, use the exif date if we can get one, otherwise
        # just use when the file was last modified
        photo_date = get_photo_date(path) if get_file_type(path.suffix) == "Images" else None
        mod_time = photo_date or datetime.fromtimestamp(path.stat().st_mtime)
        date_str = mod_time.strftime("%Y%m%d")

        new_name = f"{subject}_{date_str}_{path.stem}{path.suffix}"
        dest_path = dest_folder / new_name

        counter = 1
        while dest_path.exists():
            new_name = f"{subject}_{date_str}_{path.stem}_{counter}{path.suffix}"
            dest_path = dest_folder / new_name
            counter += 1

        shutil.move(str(path), str(dest_path))
        self.move_history.append((str(path), str(dest_path)))
        self.moved += 1
        self.log_fn(f"{path.name} -> {subject}/{new_name}")

    def save_undo_log(self):
        if not self.move_history:
            return
        try:
            with open(self.folder / UNDO_FILE, "w") as f:
                json.dump(self.move_history, f, indent=2)
        except OSError:
            pass


def undo_last_run(folder, log_fn):
    folder = Path(folder)
    undo_path = folder / UNDO_FILE

    if not undo_path.exists():
        log_fn("nothing to undo here")
        return

    try:
        with open(undo_path) as f:
            moves = json.load(f)
    except (OSError, json.JSONDecodeError):
        log_fn("undo file is broken, can't undo")
        return

    restored = 0
    folders_touched = set()
    for original, new in reversed(moves):
        new_path = Path(new)
        original_path = Path(original)
        if new_path.exists():
            try:
                shutil.move(str(new_path), str(original_path))
                restored += 1
                folders_touched.add(new_path.parent)
                log_fn(f"restored {new_path.name}")
            except OSError as e:
                log_fn(f"couldn't restore {new_path.name}: {e}")

    # remove empty subject folders left behind
    for folder_path in folders_touched:
        try:
            if folder_path.exists() and not any(folder_path.iterdir()):
                folder_path.rmdir()
        except OSError:
            pass

    undo_path.unlink(missing_ok=True)
    log_fn(f"\nundo done, restored {restored} file(s)")


# ---------------- GUI ----------------

class App:
    def __init__(self, root):
        self.root = root
        root.title("File Organizer")
        root.geometry("650x500")
        root.resizable(False, False)

        self.folder_var = tk.StringVar()
        self.current_folder = None

        tk.Label(root, text="File Organizer", font=("Arial", 18, "bold")).pack(pady=(20, 5))
        tk.Label(root, text="pick a folder and it'll sort everything into subject folders",
                 fg="gray").pack(pady=(0, 15))

        top_row = tk.Frame(root)
        top_row.pack(pady=5)
        tk.Entry(top_row, textvariable=self.folder_var, width=45).pack(side=tk.LEFT, padx=5)
        tk.Button(top_row, text="Browse", command=self.browse).pack(side=tk.LEFT)

        self.organize_btn = tk.Button(root, text="Organize Now", bg="#4caf50", fg="white",
                                       font=("Arial", 11, "bold"), command=self.start,
                                       padx=20, pady=8)
        self.organize_btn.pack(pady=15)

        self.progress = ttk.Progressbar(root, length=550, mode="determinate")
        self.progress.pack(pady=(0, 5))
        self.progress_label = tk.Label(root, text="ready", fg="gray")
        self.progress_label.pack()

        stats_row = tk.Frame(root)
        stats_row.pack(pady=15)
        self.moved_label = self.make_stat(stats_row, "Moved", "green")
        self.dup_label = self.make_stat(stats_row, "Duplicates", "orange")
        self.skip_label = self.make_stat(stats_row, "Skipped", "red")

        self.status_var = tk.StringVar(value="pick a folder to start")
        tk.Label(root, textvariable=self.status_var, font=("Courier", 9),
                 wraplength=600).pack(pady=15)

        self.done_frame = tk.Frame(root)
        tk.Label(self.done_frame, text="Files organized!", font=("Arial", 13, "bold"),
                 fg="green").pack(pady=5)
        btn_row = tk.Frame(self.done_frame)
        btn_row.pack()
        tk.Button(btn_row, text="Open Folder", command=self.open_folder).pack(side=tk.LEFT, padx=5)
        self.undo_btn = tk.Button(btn_row, text="Undo Last Run", command=self.undo)
        self.undo_btn.pack(side=tk.LEFT, padx=5)

    def make_stat(self, parent, label, color):
        frame = tk.Frame(parent, width=120, height=70, relief=tk.RIDGE, borderwidth=1)
        frame.pack(side=tk.LEFT, padx=8)
        frame.pack_propagate(False)
        value_label = tk.Label(frame, text="0", font=("Arial", 20, "bold"), fg=color)
        value_label.pack(pady=(10, 0))
        tk.Label(frame, text=label, fg="gray", font=("Arial", 9)).pack()
        return value_label

    def browse(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_var.set(path)
            self.done_frame.pack_forget()

    def start(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "pick a valid folder first")
            return

        self.organize_btn.config(state=tk.DISABLED, text="working...")
        self.done_frame.pack_forget()
        self.moved_label.config(text="0")
        self.dup_label.config(text="0")
        self.skip_label.config(text="0")
        self.progress["value"] = 0
        self.current_folder = folder

        def worker():
            org = Organizer(folder, self.log, self.update_progress)
            org.run()
            self.root.after(0, self.finished)

        threading.Thread(target=worker, daemon=True).start()

    def log(self, msg):
        self.root.after(0, self._apply_log, msg)

    def _apply_log(self, msg):
        first_line = msg.strip().splitlines()[0] if msg.strip() else ""
        if first_line:
            self.status_var.set(first_line[:90])
        if "->" in msg:
            self.moved_label.config(text=str(int(self.moved_label.cget("text")) + 1))
        elif "duplicate" in msg:
            self.dup_label.config(text=str(int(self.dup_label.cget("text")) + 1))
        elif "skipped" in msg:
            self.skip_label.config(text=str(int(self.skip_label.cget("text")) + 1))

    def update_progress(self, value):
        self.root.after(0, self._apply_progress, value)

    def _apply_progress(self, value):
        self.progress["value"] = value
        self.progress_label.config(text=f"{value:.0f}%")

    def finished(self):
        self.organize_btn.config(state=tk.NORMAL, text="Organize Now")
        self.status_var.set("all done!")
        self.done_frame.pack(pady=10)
        if self.current_folder:
            open_folder(self.current_folder)

    def open_folder(self):
        if self.current_folder:
            open_folder(self.current_folder)

    def undo(self):
        if not self.current_folder:
            return
        self.undo_btn.config(state=tk.DISABLED, text="undoing...")

        def worker():
            undo_last_run(self.current_folder, self.log)
            self.root.after(0, self._undo_done)

        threading.Thread(target=worker, daemon=True).start()

    def _undo_done(self):
        self.undo_btn.config(state=tk.NORMAL, text="Undo Last Run")
        self.status_var.set("undo complete")
        self.moved_label.config(text="0")
        self.dup_label.config(text="0")
        self.skip_label.config(text="0")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
