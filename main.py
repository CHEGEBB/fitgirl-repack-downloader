# FitGirl Repack Downloader
# github.com/brianchege

import os, re, requests, time, sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from queue import Queue, Empty

RETRY_LIMIT = 3
INPUT_FILE  = "input.txt"
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.5',
    'referer': 'https://fitgirl-repacks.site/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

# ── helpers ───────────────────────────────────────────────

def default_folder():
    return os.path.join(os.path.expanduser("~"), "Downloads", "FitGirl")

def game_name_from_url(url):
    slug = url.rstrip("/").split("/")[-1]
    return slug.replace("-", " ").title()

def get_filename(url):
    return url.split("#")[-1] if "#" in url else url.split("/")[-1]

def is_done(filename, folder):
    p = os.path.join(folder, filename)
    return os.path.exists(p) and not os.path.exists(p + ".part")

def cleanup(filename, folder):
    for ext in ["", ".part"]:
        f = os.path.join(folder, filename + ext)
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def fetch_links(fitgirl_url):
    r = requests.get(fitgirl_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    links = [
        a["href"]
        for div in soup.find_all("div", class_="dlinks")
        for a in div.find_all("a", href=True)
        if a["href"].startswith("https://fuckingfast.co/")
           and "fg-optional" not in a["href"]
    ]
    return links

def get_real_url(page_url):
    for _ in range(RETRY_LIMIT):
        try:
            r = requests.get(page_url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                time.sleep(3); continue
            soup = BeautifulSoup(r.text, 'html.parser')
            meta = soup.find('meta', attrs={'name': 'title'})
            filename = meta['content'] if meta else get_filename(page_url)
            for script in soup.find_all('script'):
                if 'function download' in script.text:
                    m = re.search(r"window\.open\([\"' ](https?://[^\s\"'\)]+)", script.text)
                    if m:
                        return m.group(1).strip(), filename
            return None, filename
        except:
            time.sleep(5)
    return None, get_filename(page_url)

def download_file(real_url, filename, folder, on_progress):
    out = os.path.join(folder, filename)
    tmp = out + ".part"
    for attempt in range(RETRY_LIMIT):
        try:
            r = requests.get(real_url, stream=True, timeout=60)
            if r.status_code != 200:
                time.sleep(5); continue
            total = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(tmp, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        on_progress(downloaded, total)
            os.rename(tmp, out)
            return True
        except Exception:
            if os.path.exists(tmp): os.remove(tmp)
            time.sleep(5)
    cleanup(filename, folder)
    return False

def remove_from_input(link):
    try:
        with open(INPUT_FILE, 'r') as f:
            lines = f.readlines()
        with open(INPUT_FILE, 'w') as f:
            for l in lines:
                if l.strip() != link:
                    f.write(l)
    except: pass

# ── GUI ───────────────────────────────────────────────────

BG     = "#0d1117"
CARD   = "#161b22"
BORDER = "#30363d"
GREEN  = "#3fb950"
DGREEN = "#238636"
WHITE  = "#e6edf3"
DIM    = "#8b949e"
YELLOW = "#d29922"
RED    = "#f85149"
BLUE   = "#58a6ff"
FONT   = ("Consolas", 10)

class FileRow(tk.Frame):
    def __init__(self, parent, filename, **kw):
        super().__init__(parent, bg=CARD, pady=4, **kw)
        short = filename[:52] + "…" if len(filename) > 55 else filename
        self.name_lbl = tk.Label(self, text=short, font=("Consolas", 9),
                                  bg=CARD, fg=WHITE, anchor="w", width=55)
        self.name_lbl.pack(side="left", padx=(8,4))

        self.status_lbl = tk.Label(self, text="WAITING", font=("Consolas", 9, "bold"),
                                    bg=CARD, fg=DIM, width=8)
        self.status_lbl.pack(side="left", padx=4)

        self.speed_lbl = tk.Label(self, text="", font=("Consolas", 9),
                                   bg=CARD, fg=DIM, width=12)
        self.speed_lbl.pack(side="left", padx=4)

        style = ttk.Style()
        style.theme_use('default')
        style.configure("file.Horizontal.TProgressbar",
                        troughcolor=BG, background=GREEN, thickness=8)
        self.bar = ttk.Progressbar(self, style="file.Horizontal.TProgressbar",
                                    length=180, maximum=100)
        self.bar.pack(side="left", padx=(4,8))

        self.pct_lbl = tk.Label(self, text="0%", font=("Consolas", 9),
                                  bg=CARD, fg=DIM, width=5)
        self.pct_lbl.pack(side="left")

    def update_progress(self, downloaded, total):
        pct  = downloaded / total * 100
        mb   = downloaded / 1024 / 1024
        tmb  = total / 1024 / 1024
        self.bar["value"] = pct
        self.pct_lbl.config(text=f"{pct:.0f}%")
        self.speed_lbl.config(text=f"{mb:.0f}/{tmb:.0f} MB")
        self.status_lbl.config(text="DOWN", fg=BLUE)

    def set_status(self, status):
        colors = {"DONE": GREEN, "FAIL": RED, "SKIP": DIM,
                  "LINK": YELLOW, "WAIT": DIM, "DOWN": BLUE}
        self.status_lbl.config(text=status, fg=colors.get(status, WHITE))
        if status == "DONE":
            self.bar["value"] = 100
            self.pct_lbl.config(text="100%")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FitGirl Repack Downloader")
        self.configure(bg=BG)
        self.minsize(780, 500)
        self.geometry("820x680")

        self.save_folder = tk.StringVar(value=default_folder())
        self.game_url    = tk.StringVar()
        self.batch_size  = tk.IntVar(value=1)
        self.running     = False
        self.links       = []
        self.msg_queue   = Queue()
        self.file_rows   = {}

        self._build_ui()
        self._poll_queue()

    def _label(self, parent, text, size=9, color=DIM, bold=False):
        w = "bold" if bold else "normal"
        tk.Label(parent, text=text, font=("Consolas", size, w),
                 bg=parent["bg"], fg=color).pack(anchor="w")

    def _card(self, parent, title, pady=(6,0)):
        outer = tk.Frame(parent, bg=CARD, bd=0)
        outer.pack(fill="x", padx=16, pady=pady)
        # border effect
        inner = tk.Frame(outer, bg=CARD, padx=14, pady=10)
        inner.pack(fill="x")
        tk.Label(inner, text=title, font=("Consolas", 8, "bold"),
                 bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))
        return inner

    def _build_ui(self):
        # ── header
        hdr = tk.Frame(self, bg=BG, pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="FITGIRL REPACK DOWNLOADER",
                 font=("Consolas", 15, "bold"), bg=BG, fg=GREEN).pack()
        tk.Label(hdr, text="github.com/brianchege",
                 font=("Consolas", 9), bg=BG, fg=DIM).pack()

        ttk.Separator(self).pack(fill="x", padx=16)

        # ── step 1
        c1 = self._card(self, "STEP 1 — Paste FitGirl game page URL", pady=(12,0))
        row1 = tk.Frame(c1, bg=CARD)
        row1.pack(fill="x")
        self.url_entry = tk.Entry(row1, textvariable=self.game_url,
                                   font=FONT, bg="#0d1117", fg=WHITE,
                                   insertbackground=WHITE, relief="flat",
                                   bd=6, width=55)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.fetch_btn = tk.Button(row1, text="Fetch Links", font=("Consolas", 10, "bold"),
                                    bg=DGREEN, fg=WHITE, relief="flat",
                                    cursor="hand2", padx=12,
                                    command=self.fetch)
        self.fetch_btn.pack(side="left", padx=(8,0))

        self.fetch_lbl = tk.Label(c1, text="", font=("Consolas", 9),
                                   bg=CARD, fg=DIM)
        self.fetch_lbl.pack(anchor="w", pady=(4,0))

        self.game_lbl = tk.Label(c1, text="", font=("Consolas", 9, "bold"),
                                  bg=CARD, fg=BLUE)
        self.game_lbl.pack(anchor="w")

        # ── step 2
        c2 = self._card(self, "STEP 2 — Save folder  (defaults to Downloads/FitGirl/<game name>)")
        row2 = tk.Frame(c2, bg=CARD)
        row2.pack(fill="x")
        self.folder_entry = tk.Entry(row2, textvariable=self.save_folder,
                                      font=FONT, bg="#0d1117", fg=WHITE,
                                      insertbackground=WHITE, relief="flat", bd=6)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        tk.Button(row2, text="Browse", font=FONT, bg="#21262d", fg=WHITE,
                  relief="flat", cursor="hand2", padx=8,
                  command=self.browse).pack(side="left", padx=(8,0))

        # ── step 3
        c3 = self._card(self, "STEP 3 — Batch size  (how many files download simultaneously)")
        radio_row = tk.Frame(c3, bg=CARD)
        radio_row.pack(fill="x")
        descs = {1:"Full speed — recommended for slow connections",
                 2:"Good balance", 3:"Fast connection",
                 4:"Fast", 5:"Very fast", 6:"Max (risk rate limit)"}
        for i in range(1, 7):
            col = tk.Frame(radio_row, bg=CARD)
            col.pack(side="left", padx=10)
            tk.Radiobutton(col, text=str(i), variable=self.batch_size,
                           value=i, font=("Consolas", 11, "bold"),
                           bg=CARD, fg=WHITE, selectcolor="#238636",
                           activebackground=CARD, activeforeground=GREEN).pack()
            tk.Label(col, text=descs[i][:12], font=("Consolas", 7),
                     bg=CARD, fg=DIM, wraplength=70).pack()

        tk.Label(c3, text="Each file is ~500 MB  |  Do not exceed 5 — fuckingfast.co will rate limit you",
                 font=("Consolas", 8), bg=CARD, fg=YELLOW).pack(anchor="w", pady=(8,0))

        # ── start button
        self.start_btn = tk.Button(self, text="▶   START DOWNLOAD",
                                    font=("Consolas", 12, "bold"),
                                    bg=DGREEN, fg=WHITE, relief="flat",
                                    cursor="hand2", pady=10,
                                    command=self.start)
        self.start_btn.pack(fill="x", padx=16, pady=10)

        # ── overall progress
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=16)
        self.overall_lbl = tk.Label(prog_frame, text="Overall progress",
                                     font=("Consolas", 9), bg=BG, fg=DIM)
        self.overall_lbl.pack(anchor="w")
        style = ttk.Style()
        style.configure("overall.Horizontal.TProgressbar",
                        troughcolor="#21262d", background=GREEN, thickness=14)
        self.overall_bar = ttk.Progressbar(prog_frame,
                                            style="overall.Horizontal.TProgressbar",
                                            length=780, maximum=100)
        self.overall_bar.pack(fill="x", pady=(2,8))

        # ── file list
        list_frame = tk.Frame(self, bg=CARD)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(0,10))
        tk.Label(list_frame, text="FILES", font=("Consolas", 8, "bold"),
                 bg=CARD, fg=DIM).pack(anchor="w", padx=8, pady=(6,0))

        canvas_frame = tk.Frame(list_frame, bg=CARD)
        canvas_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.canvas = tk.Canvas(canvas_frame, bg=CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                   command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=CARD)
        self.scroll_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                action = msg.get("action")
                fn = msg.get("file", "")

                if action == "status" and fn in self.file_rows:
                    self.file_rows[fn].set_status(msg["status"])
                elif action == "progress" and fn in self.file_rows:
                    self.file_rows[fn].update_progress(msg["dl"], msg["total"])
                elif action == "overall":
                    self.overall_bar["value"] = msg["pct"]
                    self.overall_lbl.config(
                        text=f"Overall: {msg['done']}/{msg['total']} files  |  {msg['pct']:.0f}%  |  {msg['failed']} failed")
                elif action == "done_all":
                    self.start_btn.config(state="normal",
                        text="▶   START DOWNLOAD", bg=DGREEN)
                    self.running = False
        except Empty:
            pass
        self.after(100, self._poll_queue)

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.save_folder.get())
        if folder:
            self.save_folder.set(folder)

    def fetch(self):
        url = self.game_url.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a FitGirl game URL"); return
        self.fetch_lbl.config(text="Fetching links...", fg=YELLOW)
        self.fetch_btn.config(state="disabled")
        self.update()

        def _fetch():
            try:
                self.links = fetch_links(url)
                with open(INPUT_FILE, "w") as f:
                    for l in self.links:
                        f.write(l + "\n")
                game = game_name_from_url(url)
                # update save folder with game name
                new_folder = os.path.join(os.path.expanduser("~"), "Downloads", "FitGirl", game)
                self.save_folder.set(new_folder)
                self.fetch_lbl.config(
                    text=f"✓ Found {len(self.links)} files — ready to download", fg=GREEN)
                self.game_lbl.config(text=f"Game: {game}")

                # build file rows
                for w in self.scroll_frame.winfo_children():
                    w.destroy()
                self.file_rows = {}
                for link in self.links:
                    fn = get_filename(link)
                    row = FileRow(self.scroll_frame, fn)
                    row.pack(fill="x", pady=1)
                    self.file_rows[fn] = row

            except Exception as e:
                self.fetch_lbl.config(text=f"✗ Failed: {e}", fg=RED)
            finally:
                self.fetch_btn.config(state="normal")

        Thread(target=_fetch, daemon=True).start()

    def start(self):
        if self.running: return
        if not self.links:
            if os.path.exists(INPUT_FILE):
                with open(INPUT_FILE) as f:
                    self.links = [l.strip() for l in f if l.strip()]
            if not self.links:
                messagebox.showerror("Error", "No links. Fetch links first."); return

        folder = self.save_folder.get().strip()
        os.makedirs(folder, exist_ok=True)
        batch = self.batch_size.get()

        self.running = True
        self.start_btn.config(state="disabled", text="Downloading...", bg="#1f2937")
        Thread(target=self._run, args=(folder, batch), daemon=True).start()

    def _run(self, folder, batch_size):
        q = self.msg_queue
        pending = [l for l in self.links if not is_done(get_filename(l), folder)]
        skipped = len(self.links) - len(pending)
        total   = len(self.links)

        # mark skipped
        for l in self.links:
            fn = get_filename(l)
            if is_done(fn, folder) and fn in self.file_rows:
                q.put({"action":"status","file":fn,"status":"SKIP"})

        if not pending:
            q.put({"action":"overall","pct":100,"done":total,"total":total,"failed":0})
            q.put({"action":"done_all"})
            return

        batches    = [pending[i:i+batch_size] for i in range(0, len(pending), batch_size)]
        done_count = skipped
        fail_count = 0

        for batch in batches:
            with ThreadPoolExecutor(max_workers=batch_size) as ex:
                futures = {ex.submit(self._process, url, folder, q): url for url in batch}
                for future in as_completed(futures):
                    status = future.result()
                    if status == "done":   done_count += 1
                    elif status == "failed": fail_count += 1
                    pct = done_count / total * 100
                    q.put({"action":"overall","pct":pct,
                           "done":done_count,"total":total,"failed":fail_count})
            time.sleep(1)

        q.put({"action":"done_all"})

    def _process(self, page_url, folder, q):
        fn = get_filename(page_url)

        if is_done(fn, folder):
            q.put({"action":"status","file":fn,"status":"SKIP"})
            return "skipped"

        q.put({"action":"status","file":fn,"status":"LINK"})
        real_url, fn = get_real_url(page_url)

        if not real_url:
            q.put({"action":"status","file":fn,"status":"FAIL"})
            return "failed"

        q.put({"action":"status","file":fn,"status":"DOWN"})

        def on_progress(dl, total):
            q.put({"action":"progress","file":fn,"dl":dl,"total":total})

        ok = download_file(real_url, fn, folder, on_progress)

        if ok:
            remove_from_input(page_url)
            q.put({"action":"status","file":fn,"status":"DONE"})
            return "done"
        else:
            q.put({"action":"status","file":fn,"status":"FAIL"})
            return "failed"


if __name__ == "__main__":
    app = App()
    app.mainloop()
