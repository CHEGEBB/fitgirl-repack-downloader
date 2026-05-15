# FitGirl Repack Downloader
# github.com/CHEGEBB/fitgirl-repack-downloader

import os, re, requests, time, json, glob
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from queue import Queue, Empty

RETRY_LIMIT = 3
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.5',
    'referer': 'https://fitgirl-repacks.site/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
}

BG     = "#0d1117"
CARD   = "#161b22"
GREEN  = "#3fb950"
DGREEN = "#238636"
WHITE  = "#e6edf3"
DIM    = "#8b949e"
YELLOW = "#d29922"
RED    = "#f85149"
BLUE   = "#58a6ff"
FONT   = ("Consolas", 10)

# ── helpers ───────────────────────────────────────────────

def default_folder():
    return os.path.join(os.path.expanduser("~"), "Downloads", "FitGirl")

def game_slug(url):
    return url.rstrip("/").split("/")[-1]

def game_name(url):
    return game_slug(url).replace("-", " ").title()

def links_file(slug):
    return f"{slug}.txt"

def session_file(slug):
    return f"{slug}.session.json"

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

def is_selective(url):
    fn = get_filename(url).lower()
    return "fg-optional" in fn or "fg-selective" in fn

def fetch_all_links(fitgirl_url):
    r = requests.get(fitgirl_url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    all_links = [
        a["href"]
        for div in soup.find_all("div", class_="dlinks")
        for a in div.find_all("a", href=True)
        if a["href"].startswith("https://fuckingfast.co/")
    ]
    main_links      = [l for l in all_links if not is_selective(l)]
    selective_links = [l for l in all_links if is_selective(l)]
    return main_links, selective_links

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

def save_links(slug, links):
    with open(links_file(slug), 'w') as f:
        for l in links:
            f.write(l + "\n")

def load_links(slug):
    lf = links_file(slug)
    if not os.path.exists(lf):
        return []
    with open(lf) as f:
        return [l.strip() for l in f if l.strip()]

def remove_link(slug, link):
    try:
        lf = links_file(slug)
        with open(lf) as f:
            lines = f.readlines()
        with open(lf, 'w') as f:
            for l in lines:
                if l.strip() != link:
                    f.write(l)
    except: pass

def delete_game_files(slug):
    for f in [links_file(slug), session_file(slug)]:
        if os.path.exists(f):
            try: os.remove(f)
            except: pass

def save_session(slug, folder, batch):
    with open(session_file(slug), 'w') as f:
        json.dump({"folder": folder, "batch": batch, "slug": slug}, f)

def load_session(slug):
    sf = session_file(slug)
    if os.path.exists(sf):
        with open(sf) as f:
            return json.load(f)
    return None

def find_saved_games():
    """Find all .txt files that look like game link files"""
    files = glob.glob("*.txt")
    games = []
    for f in files:
        slug = f.replace(".txt", "")
        links = load_links(slug)
        if links and "fuckingfast.co" in links[0]:
            session = load_session(slug)
            games.append({"slug": slug, "name": slug.replace("-", " ").title(),
                          "links": links, "session": session})
    return games

# ── File Row Widget ───────────────────────────────────────

class FileRow(tk.Frame):
    def __init__(self, parent, filename, **kw):
        super().__init__(parent, bg=CARD, pady=3, **kw)
        short = filename[:50] + "…" if len(filename) > 53 else filename
        tk.Label(self, text=short, font=("Consolas", 9),
                 bg=CARD, fg=WHITE, anchor="w", width=53).pack(side="left", padx=(8,4))
        self.status_lbl = tk.Label(self, text="WAIT", font=("Consolas", 9, "bold"),
                                    bg=CARD, fg=DIM, width=6)
        self.status_lbl.pack(side="left", padx=4)
        self.mb_lbl = tk.Label(self, text="", font=("Consolas", 9),
                                bg=CARD, fg=DIM, width=14)
        self.mb_lbl.pack(side="left", padx=2)
        style = ttk.Style()
        style.theme_use('default')
        style.configure("f.Horizontal.TProgressbar", troughcolor=BG,
                        background=GREEN, thickness=8)
        self.bar = ttk.Progressbar(self, style="f.Horizontal.TProgressbar",
                                    length=160, maximum=100)
        self.bar.pack(side="left", padx=(2,6))
        self.pct_lbl = tk.Label(self, text="", font=("Consolas", 9),
                                  bg=CARD, fg=DIM, width=5)
        self.pct_lbl.pack(side="left")

    def update_progress(self, dl, total):
        pct = dl / total * 100
        self.bar["value"] = pct
        self.pct_lbl.config(text=f"{pct:.0f}%")
        self.mb_lbl.config(text=f"{dl/1048576:.0f}/{total/1048576:.0f} MB")
        self.status_lbl.config(text="DOWN", fg=BLUE)

    def set_status(self, s):
        c = {"DONE":GREEN,"FAIL":RED,"SKIP":DIM,"LINK":YELLOW,"WAIT":DIM,"DOWN":BLUE}
        self.status_lbl.config(text=s, fg=c.get(s, WHITE))
        if s == "DONE":
            self.bar["value"] = 100
            self.pct_lbl.config(text="100%")

# ── Selective Files Dialog ────────────────────────────────

class SelectiveDialog(tk.Toplevel):
    def __init__(self, parent, selective_links):
        super().__init__(parent)
        self.title("Optional / Selective Files")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.result = []
        self.checks = {}

        tk.Label(self, text="OPTIONAL & SELECTIVE FILES",
                 font=("Consolas", 11, "bold"), bg=BG, fg=GREEN).pack(pady=(16,4))
        tk.Label(self, text="This game has optional files (language packs, 4K videos, etc).\nTick only what you need. Check the FitGirl page if unsure.",
                 font=("Consolas", 9), bg=BG, fg=DIM, justify="center").pack(pady=(0,8))

        note = tk.Frame(self, bg="#1c2128", padx=12, pady=8)
        note.pack(fill="x", padx=16, pady=(0,10))
        tk.Label(note, text="⚠  If the game requires at least one speech pack, make sure you tick it.\n   Check fitgirl-repacks.site for the selective download notes.",
                 font=("Consolas", 8), bg="#1c2128", fg=YELLOW, justify="left").pack(anchor="w")

        scroll_outer = tk.Frame(self, bg=CARD)
        scroll_outer.pack(fill="both", expand=True, padx=16, pady=(0,10))
        canvas = tk.Canvas(scroll_outer, bg=CARD, highlightthickness=0, height=200)
        sb = ttk.Scrollbar(scroll_outer, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=CARD)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for link in selective_links:
            fn = get_filename(link)
            var = tk.BooleanVar(value=False)
            self.checks[link] = var
            tk.Checkbutton(inner, text=fn, variable=var,
                           font=("Consolas", 9), bg=CARD, fg=WHITE,
                           selectcolor=DGREEN, activebackground=CARD,
                           activeforeground=GREEN).pack(anchor="w", padx=8, pady=2)

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="Skip All", font=FONT, bg="#21262d", fg=WHITE,
                  relief="flat", padx=16, cursor="hand2",
                  command=self._skip).pack(side="left", padx=8)
        tk.Button(btn_row, text="Download Selected", font=("Consolas", 10, "bold"),
                  bg=DGREEN, fg=WHITE, relief="flat", padx=16, cursor="hand2",
                  command=self._confirm).pack(side="left", padx=8)

        self.geometry("520x420")
        self.wait_window()

    def _confirm(self):
        self.result = [l for l, v in self.checks.items() if v.get()]
        self.destroy()

    def _skip(self):
        self.result = []
        self.destroy()

# ── Resume Dialog ─────────────────────────────────────────

class ResumeDialog(tk.Toplevel):
    def __init__(self, parent, games):
        super().__init__(parent)
        self.title("Resume Download")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.grab_set()
        self.choice = None  # "resume", "new"
        self.selected_game = None

        tk.Label(self, text="IN-PROGRESS DOWNLOADS FOUND",
                 font=("Consolas", 11, "bold"), bg=BG, fg=YELLOW).pack(pady=(16,4))
        tk.Label(self, text="You have unfinished downloads. Resume or start a new game?",
                 font=("Consolas", 9), bg=BG, fg=DIM).pack(pady=(0,12))

        self.selected_var = tk.StringVar()
        for g in games:
            remaining = len(g["links"])
            folder = g["session"]["folder"] if g["session"] else "unknown folder"
            row = tk.Frame(self, bg=CARD, padx=12, pady=8)
            row.pack(fill="x", padx=16, pady=3)
            tk.Radiobutton(row, text=f"{g['name']}  ({remaining} files remaining)",
                           variable=self.selected_var, value=g["slug"],
                           font=("Consolas", 10), bg=CARD, fg=WHITE,
                           selectcolor=DGREEN, activebackground=CARD).pack(anchor="w")
            tk.Label(row, text=f"Saving to: {folder}",
                     font=("Consolas", 8), bg=CARD, fg=DIM).pack(anchor="w")

        if games:
            self.selected_var.set(games[0]["slug"])

        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=16)
        tk.Button(btn_row, text="Start New Game", font=FONT,
                  bg="#21262d", fg=WHITE, relief="flat", padx=16,
                  cursor="hand2", command=self._new).pack(side="left", padx=8)
        tk.Button(btn_row, text="Resume Selected", font=("Consolas", 10, "bold"),
                  bg=DGREEN, fg=WHITE, relief="flat", padx=16,
                  cursor="hand2", command=self._resume).pack(side="left", padx=8)

        self.geometry("500x320")
        self.wait_window()

    def _resume(self):
        self.choice = "resume"
        self.selected_game = self.selected_var.get()
        self.destroy()

    def _new(self):
        self.choice = "new"
        self.destroy()

# ── Main App ──────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FitGirl Repack Downloader")
        self.configure(bg=BG)
        self.minsize(800, 560)
        self.geometry("840x700")

        self.save_folder  = tk.StringVar(value=default_folder())
        self.game_url     = tk.StringVar()
        self.batch_size   = tk.IntVar(value=1)
        self.running      = False
        self.links        = []
        self.current_slug = None
        self.msg_queue    = Queue()
        self.file_rows    = {}

        self._build_ui()
        self._poll_queue()
        self.after(200, self._check_resume)

    # ── UI build ─────────────────────────────────────────

    def _card(self, parent, title, pady=(6,0)):
        outer = tk.Frame(parent, bg=CARD)
        outer.pack(fill="x", padx=16, pady=pady)
        inner = tk.Frame(outer, bg=CARD, padx=14, pady=10)
        inner.pack(fill="x")
        tk.Label(inner, text=title, font=("Consolas", 8, "bold"),
                 bg=CARD, fg=DIM).pack(anchor="w", pady=(0,6))
        return inner

    def _build_ui(self):
        hdr = tk.Frame(self, bg=BG, pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="FITGIRL REPACK DOWNLOADER",
                 font=("Consolas", 15, "bold"), bg=BG, fg=GREEN).pack()
        tk.Label(hdr, text="github.com/CHEGEBB/fitgirl-repack-downloader",
                 font=("Consolas", 9), bg=BG, fg=DIM).pack()

        ttk.Separator(self).pack(fill="x", padx=16)

        # step 1
        c1 = self._card(self, "STEP 1 — Paste FitGirl game page URL", pady=(12,0))
        row1 = tk.Frame(c1, bg=CARD)
        row1.pack(fill="x")
        tk.Entry(row1, textvariable=self.game_url, font=FONT,
                 bg="#0d1117", fg=WHITE, insertbackground=WHITE,
                 relief="flat", bd=6).pack(side="left", fill="x", expand=True)
        self.fetch_btn = tk.Button(row1, text="Fetch Links",
                                    font=("Consolas", 10, "bold"),
                                    bg=DGREEN, fg=WHITE, relief="flat",
                                    cursor="hand2", padx=12, command=self.fetch)
        self.fetch_btn.pack(side="left", padx=(8,0))
        self.fetch_lbl = tk.Label(c1, text="", font=("Consolas", 9), bg=CARD, fg=DIM)
        self.fetch_lbl.pack(anchor="w", pady=(4,0))
        self.game_lbl = tk.Label(c1, text="", font=("Consolas", 9, "bold"),
                                  bg=CARD, fg=BLUE)
        self.game_lbl.pack(anchor="w")

        # step 2
        c2 = self._card(self, "STEP 2 — Save folder  (auto-set from game name)")
        row2 = tk.Frame(c2, bg=CARD)
        row2.pack(fill="x")
        tk.Entry(row2, textvariable=self.save_folder, font=FONT,
                 bg="#0d1117", fg=WHITE, insertbackground=WHITE,
                 relief="flat", bd=6).pack(side="left", fill="x", expand=True)
        tk.Button(row2, text="Browse", font=FONT, bg="#21262d", fg=WHITE,
                  relief="flat", cursor="hand2", padx=8,
                  command=self.browse).pack(side="left", padx=(8,0))

        # step 3
        c3 = self._card(self, "STEP 3 — Batch size  (files downloading at the same time)")
        radio_row = tk.Frame(c3, bg=CARD)
        radio_row.pack(fill="x")
        descs = {1:"Full speed\nBest for slow\nconnections",
                 2:"Good\nbalance","3":"Fast\nconnection",
                 4:"Fast", 5:"Very fast", 6:"Max\n(rate limit\nrisk)"}
        for i in range(1, 7):
            col = tk.Frame(radio_row, bg=CARD)
            col.pack(side="left", padx=12)
            tk.Radiobutton(col, text=str(i), variable=self.batch_size, value=i,
                           font=("Consolas", 12, "bold"), bg=CARD, fg=WHITE,
                           selectcolor=DGREEN, activebackground=CARD,
                           activeforeground=GREEN).pack()
            tk.Label(col, text=descs.get(i, ""), font=("Consolas", 7),
                     bg=CARD, fg=DIM, justify="center").pack()
        tk.Label(c3,
                 text="⚡ Each file ~500 MB  |  1 = full bandwidth to one file  |  max 5 (above 5 risks rate limiting)",
                 font=("Consolas", 8), bg=CARD, fg=YELLOW).pack(anchor="w", pady=(8,0))

        # start
        self.start_btn = tk.Button(self, text="▶   START DOWNLOAD",
                                    font=("Consolas", 12, "bold"),
                                    bg=DGREEN, fg=WHITE, relief="flat",
                                    cursor="hand2", pady=10, command=self.start)
        self.start_btn.pack(fill="x", padx=16, pady=10)

        # overall bar
        pf = tk.Frame(self, bg=BG)
        pf.pack(fill="x", padx=16)
        self.overall_lbl = tk.Label(pf, text="Overall progress",
                                     font=("Consolas", 9), bg=BG, fg=DIM)
        self.overall_lbl.pack(anchor="w")
        style = ttk.Style()
        style.theme_use('default')
        style.configure("ov.Horizontal.TProgressbar",
                        troughcolor="#21262d", background=GREEN, thickness=14)
        self.overall_bar = ttk.Progressbar(pf, style="ov.Horizontal.TProgressbar",
                                            maximum=100)
        self.overall_bar.pack(fill="x", pady=(2,8))

        # file list
        lf = tk.Frame(self, bg=CARD)
        lf.pack(fill="both", expand=True, padx=16, pady=(0,10))
        tk.Label(lf, text="FILES", font=("Consolas", 8, "bold"),
                 bg=CARD, fg=DIM).pack(anchor="w", padx=8, pady=(6,0))
        cf = tk.Frame(lf, bg=CARD)
        cf.pack(fill="both", expand=True, padx=8, pady=4)
        self.canvas = tk.Canvas(cf, bg=CARD, highlightthickness=0)
        sb = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=CARD)
        self.scroll_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.scroll_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ── queue polling ─────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                a  = msg.get("action")
                fn = msg.get("file", "")
                if a == "status" and fn in self.file_rows:
                    self.file_rows[fn].set_status(msg["status"])
                elif a == "progress" and fn in self.file_rows:
                    self.file_rows[fn].update_progress(msg["dl"], msg["total"])
                elif a == "overall":
                    self.overall_bar["value"] = msg["pct"]
                    self.overall_lbl.config(
                        text=f"Overall: {msg['done']}/{msg['total']} files  |  {msg['pct']:.0f}%  |  {msg['failed']} failed")
                elif a == "done_all":
                    self._on_done_all(msg.get("failed", 0))
        except Empty:
            pass
        self.after(100, self._poll_queue)

    # ── startup resume check ──────────────────────────────

    def _check_resume(self):
        games = find_saved_games()
        if not games:
            return
        dlg = ResumeDialog(self, games)
        if dlg.choice == "resume" and dlg.selected_game:
            slug = dlg.selected_game
            game = next(g for g in games if g["slug"] == slug)
            self.current_slug = slug
            self.links = game["links"]
            session = game["session"]
            if session:
                self.save_folder.set(session.get("folder", default_folder()))
                self.batch_size.set(session.get("batch", 1))
            self.game_url.set(f"https://fitgirl-repacks.site/{slug}/")
            self.fetch_lbl.config(
                text=f"✓ Resumed — {len(self.links)} files remaining", fg=GREEN)
            self.game_lbl.config(text=f"Game: {game['name']}")
            self._build_file_rows(self.links)
        # if "new" — do nothing, fresh start

    # ── actions ───────────────────────────────────────────

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

        def _fetch():
            try:
                main_links, selective_links = fetch_all_links(url)
                slug = game_slug(url)
                self.current_slug = slug
                name = game_name(url)

                # show selective dialog if any
                chosen_selective = []
                if selective_links:
                    dlg = SelectiveDialog(self, selective_links)
                    chosen_selective = dlg.result

                self.links = main_links + chosen_selective
                save_links(slug, self.links)

                folder = os.path.join(os.path.expanduser("~"), "Downloads", "FitGirl", name)
                self.save_folder.set(folder)
                save_session(slug, folder, self.batch_size.get())

                self.fetch_lbl.config(
                    text=f"✓ {len(main_links)} main files  +  {len(chosen_selective)} optional selected", fg=GREEN)
                self.game_lbl.config(text=f"Game: {name}")
                self._build_file_rows(self.links)

            except Exception as e:
                self.fetch_lbl.config(text=f"✗ Failed: {e}", fg=RED)
            finally:
                self.fetch_btn.config(state="normal")

        Thread(target=_fetch, daemon=True).start()

    def _build_file_rows(self, links):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.file_rows = {}
        for link in links:
            fn = get_filename(link)
            row = FileRow(self.scroll_frame, fn)
            row.pack(fill="x", pady=1)
            self.file_rows[fn] = row

    def start(self):
        if self.running: return
        if not self.links:
            messagebox.showerror("Error", "No links found. Fetch links first."); return
        folder = self.save_folder.get().strip()
        os.makedirs(folder, exist_ok=True)
        batch = self.batch_size.get()
        save_session(self.current_slug, folder, batch)
        self.running = True
        self.start_btn.config(state="disabled", text="Downloading...", bg="#1f2937")
        Thread(target=self._run, args=(folder, batch), daemon=True).start()

    # ── download engine ───────────────────────────────────

    def _run(self, folder, batch_size):
        q    = self.msg_queue
        slug = self.current_slug
        pending  = [l for l in self.links if not is_done(get_filename(l), folder)]
        skipped  = len(self.links) - len(pending)
        total    = len(self.links)

        for l in self.links:
            fn = get_filename(l)
            if is_done(fn, folder) and fn in self.file_rows:
                q.put({"action":"status","file":fn,"status":"SKIP"})

        if not pending:
            q.put({"action":"overall","pct":100,"done":total,"total":total,"failed":0})
            q.put({"action":"done_all","failed":0})
            return

        batches    = [pending[i:i+batch_size] for i in range(0, len(pending), batch_size)]
        done_count = skipped
        fail_count = 0

        for batch in batches:
            with ThreadPoolExecutor(max_workers=batch_size) as ex:
                futures = {ex.submit(self._process, url, folder, slug, q): url for url in batch}
                for future in as_completed(futures):
                    status = future.result()
                    if status == "done":    done_count += 1
                    elif status == "failed": fail_count += 1
                    pct = done_count / total * 100
                    q.put({"action":"overall","pct":pct,
                           "done":done_count,"total":total,"failed":fail_count})
            time.sleep(1)

        q.put({"action":"done_all","failed":fail_count})

    def _process(self, page_url, folder, slug, q):
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
            remove_link(slug, page_url)
            q.put({"action":"status","file":fn,"status":"DONE"})
            return "done"
        q.put({"action":"status","file":fn,"status":"FAIL"})
        return "failed"

    def _on_done_all(self, failed):
        self.running = False
        self.start_btn.config(state="normal", text="▶   START DOWNLOAD", bg=DGREEN)
        if failed == 0:
            # clean up — all done
            delete_game_files(self.current_slug)
            messagebox.showinfo("Done!",
                f"All files downloaded successfully!\n\nSaved to:\n{self.save_folder.get()}")
        else:
            messagebox.showwarning("Almost done",
                f"{failed} file(s) failed after all retries.\nClick START DOWNLOAD again to retry them.")


if __name__ == "__main__":
    app = App()
    app.mainloop()