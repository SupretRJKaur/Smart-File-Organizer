
const COUNTER_NAMESPACE = "supretrjkaur-smart-file-organizer";
const COUNTER_KEY = "files-organized";

function updateCounterUI(value) {
  const counterNumEl = document.getElementById('useCountNumber');
  if (counterNumEl && value !== undefined && value !== null) {
    counterNumEl.textContent = value;
  }
}

// on page load, just READ the current global count (this does not add to it,
// it only shows what other people have already run)
function loadCurrentCount() {
  fetch(`https://abacus.jasoncameron.dev/get/${COUNTER_NAMESPACE}/${COUNTER_KEY}`)
    .then(res => {
      if (!res.ok) throw new Error("counter not created yet");
      return res.json();
    })
    .then(data => updateCounterUI(data.value))
    .catch(() => updateCounterUI(0)); // first ever visit, nothing created yet
}

// actually increments the global count by 1, for everyone
function bumpGlobalCount() {
  fetch(`https://abacus.jasoncameron.dev/hit/${COUNTER_NAMESPACE}/${COUNTER_KEY}`)
    .then(res => res.json())
    .then(data => updateCounterUI(data.value))
    .catch(() => {}); // if the counter service is down, just don't update - no big deal
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadCurrentCount);
} else {
  loadCurrentCount();
}

// list of subjects we can recognize from the filename
// add more keywords here if your files use different course codes
const subjects = {
  dbms: "DBMS",
  java: "Java",
  toc: "TOC",
  matlab: "MATLAB",
  circuit: "Circuits",
  circuits: "Circuits",
  dlcd: "DLCD",
  dlc: "DLC",
  dsa: "DSA",
  ds: "DS",
  dm: "Discrete Maths",
  os: "Operating Systems",
  cn: "Computer Networks",
  ai: "AI",
  ml: "ML",
  oop: "OOP",
  python: "Python",
  cpp: "CPP",
};

// words that show up in filenames but don't tell us the subject
const skipWords = new Set([
  "file", "files", "unit", "cover", "covers", "expt", "experiment",
  "experiments", "viva", "ques", "question", "questions", "sem",
  "class", "notes", "scan", "adobe", "doc", "docx", "pdf", "the",
  "of", "and", "for", "to", "new", "copy", "final", "img", "image",
  "whatsapp", "screenshot", "document", "documents",
]);

const fileTypes = {
  Images: ["jpg", "jpeg", "png", "gif", "bmp", "webp", "svg", "heic"],
  Documents: ["pdf", "doc", "docx", "txt", "xls", "xlsx", "ppt", "pptx", "csv"],
  Videos: ["mp4", "mkv", "mov", "avi", "webm", "flv"],
  Audio: ["mp3", "wav", "aac", "flac", "ogg", "m4a"],
  Archives: ["zip", "rar", "7z", "tar", "gz"],
  Code: ["py", "java", "cpp", "c", "js", "html", "css", "json", "ipynb"],
};

function getFileType(ext) {
  ext = ext.toLowerCase();
  for (let type in fileTypes) {
    if (fileTypes[type].includes(ext)) return type;
  }
  return "Others";
}

// break a filename into words, ignoring numbers and skip words
function getWords(name) {
  let words = name.toLowerCase().split(/[^a-z]+/i);
  return words.filter(w => w.length > 1 && !skipWords.has(w));
}

function findSubject(words) {
  for (let w of words) {
    if (subjects[w]) return subjects[w];
  }
  return null;
}

// go through all files and figure out which subject folder each one belongs to
// files that don't match a known subject get grouped by whatever word repeats
// across other unmatched files, otherwise they go in Misc
function groupFiles(files) {
  let plan = files.map(f => ({ ...f, subject: findSubject(f.words) }));

  let leftoverByType = {};
  for (let f of plan) {
    if (!f.subject) {
      if (!leftoverByType[f.type]) leftoverByType[f.type] = [];
      leftoverByType[f.type].push(f);
    }
  }

  for (let type in leftoverByType) {
    let items = leftoverByType[type];
    let counts = {};
    for (let f of items) {
      let uniqueWords = new Set(f.words);
      uniqueWords.forEach(w => counts[w] = (counts[w] || 0) + 1);
    }
    for (let f of items) {
      let repeated = f.words.filter(w => counts[w] >= 2);
      if (repeated.length > 0) {
        let best = repeated[0];
        for (let w of repeated) {
          if (counts[w] > counts[best]) best = w;
        }
        f.subject = best[0].toUpperCase() + best.slice(1);
      } else {
        f.subject = "Misc";
      }
    }
  }

  return plan;
}

async function getFileHash(file) {
  let buffer = await file.arrayBuffer();
  let hashBuffer = await crypto.subtle.digest("SHA-256", buffer);
  let bytes = Array.from(new Uint8Array(hashBuffer));
  return bytes.map(b => b.toString(16).padStart(2, "0")).join("");
}

function twoDigits(n) {
  return n < 10 ? "0" + n : "" + n;
}

function getDateString(date) {
  return "" + date.getFullYear() + twoDigits(date.getMonth() + 1) + twoDigits(date.getDate());
}

// ---------- everything below hooks up the page ----------

let chosenFiles = [];

const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const folderInput = document.getElementById("folderInput");
const fileCount = document.getElementById("fileCount");
const organizeBtn = document.getElementById("organizeBtn");
const progressBox = document.getElementById("progressBox");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const statusText = document.getElementById("statusText");
const resultsBox = document.getElementById("resultsBox");
const folderList = document.getElementById("folderList");
const downloadBtn = document.getElementById("downloadBtn");

document.getElementById("pickFilesBtn").onclick = () => fileInput.click();
document.getElementById("pickFolderBtn").onclick = () => folderInput.click();

fileInput.onchange = e => setFiles(Array.from(e.target.files));
folderInput.onchange = e => setFiles(Array.from(e.target.files));

dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});
dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  let files = Array.from(e.dataTransfer.files);
  if (files.length) setFiles(files);
});

function setFiles(files) {
  chosenFiles = files;
  fileCount.textContent = files.length ? files.length + " file(s) selected" : "";
  organizeBtn.disabled = files.length === 0;
  resultsBox.classList.add("hidden");
}

organizeBtn.onclick = organizeFiles;

async function organizeFiles() {
  organizeBtn.disabled = true;
  organizeBtn.textContent = "Working...";
  progressBox.classList.remove("hidden");
  resultsBox.classList.add("hidden");

  if (chosenFiles && chosenFiles.length > 0) {
    bumpGlobalCount();
  }

  let seenHashes = {};
  let movedCount = 0;
  let dupCount = 0;
  let errCount = 0;

  let fileData = chosenFiles.map(file => {
    let name = file.name;
    let dotIndex = name.lastIndexOf(".");
    let stem = dotIndex >= 0 ? name.slice(0, dotIndex) : name;
    let ext = dotIndex >= 0 ? name.slice(dotIndex + 1) : "";
    return {
      file: file,
      name: name,
      stem: stem,
      ext: ext,
      type: getFileType(ext),
      words: getWords(stem),
    };
  });

  let plan = groupFiles(fileData);

  let zip = new JSZip();
  let usedNames = {};
  let folderCounts = {};

  for (let i = 0; i < plan.length; i++) {
    let item = plan[i];
    statusText.textContent = "Checking " + item.name + "...";

    try {
      let hash = await getFileHash(item.file);

      if (seenHashes[hash]) {
        dupCount++;
        statusText.textContent = "Duplicate: " + item.name + " (skipped)";
      } else {
        seenHashes[hash] = item.name;

        let modDate = item.file.lastModified ? new Date(item.file.lastModified) : new Date();
        let dateStr = getDateString(modDate);
        let subject = item.subject;

        if (!usedNames[subject]) usedNames[subject] = new Set();

        let newName = subject + "_" + dateStr + "_" + item.stem + "." + item.ext;
        let counter = 1;
        while (usedNames[subject].has(newName)) {
          newName = subject + "_" + dateStr + "_" + item.stem + "_" + counter + "." + item.ext;
          counter++;
        }
        usedNames[subject].add(newName);

        let buffer = await item.file.arrayBuffer();
        zip.folder(subject).file(newName, buffer);

        folderCounts[subject] = (folderCounts[subject] || 0) + 1;
        movedCount++;
        statusText.textContent = item.name + " -> " + subject + "/" + newName;
      }
    } catch (err) {
      errCount++;
      statusText.textContent = "Error with " + item.name;
    }

    let percent = Math.round(((i + 1) / plan.length) * 100);
    progressFill.style.width = percent + "%";
    progressText.textContent = percent + "% done";
  }

  // show the results
  folderList.innerHTML = "";
  for (let subject in folderCounts) {
    let div = document.createElement("div");
    div.className = "folder-item";
    div.innerHTML = "<b>" + subject + "</b>" + folderCounts[subject] + " file(s)";
    folderList.appendChild(div);
  }

  document.getElementById("movedCount").textContent = movedCount;
  document.getElementById("dupCount").textContent = dupCount;
  document.getElementById("errCount").textContent = errCount;

  resultsBox.classList.remove("hidden");
  statusText.textContent = "All done!";
  organizeBtn.disabled = false;
  organizeBtn.textContent = "Organize Files";

  downloadBtn.onclick = async () => {
    downloadBtn.disabled = true;
    downloadBtn.textContent = "Zipping...";
    let blob = await zip.generateAsync({ type: "blob" });
    let url = URL.createObjectURL(blob);
    let a = document.createElement("a");
    a.href = url;
    a.download = "organized_files.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    downloadBtn.disabled = false;
    downloadBtn.textContent = "Download ZIP";
  };
}
