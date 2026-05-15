# FitGirl Repack Downloader

A simple GUI tool to automatically download FitGirl repacks from fuckingfast.co.  
No IDM needed. Just paste a link and go.

---

## How It Works

### Step 1 — Find your game on FitGirl Repacks

![FitGirl Page](<Screenshot 2026-05-15 085354.png>)

Go to [fitgirl-repacks.site](https://fitgirl-repacks.site), find your game, click it, and copy the page URL from your browser address bar.

![Uploading Screenshot 2026-05-15 085446.png…]()

Use the **FuckingFast** mirror links — that's what this tool downloads from.

---

### Step 2 — Paste URL and download

<img width="1070" height="844" alt="Screenshot 2026-05-15 091014" src="https://github.com/user-attachments/assets/b1dd316f-3a05-47d3-ae32-2c19659a0bde" />


1. Paste the game page URL → click **Fetch Links**
2. Tool auto-detects the game name and sets your save folder to `Downloads/FitGirl/<Game Name>`
3. Pick batch size (how many files download at once)
4. Click **▶ START DOWNLOAD** and walk away

---

## Setup

1. Install [Python 3.8+](https://www.python.org/downloads/) — tick **"Add to PATH"** during install
2. Double-click **`START.bat`** — installs dependencies and opens the app

That's it. No other setup needed.

---

## Features

- Auto-fetches all fuckingfast download links from any FitGirl game page
- Auto-names save folder after the game (e.g. `Downloads/FitGirl/Ghost Of Tsushima Directors Cut`)
- Skips language packs automatically
- Per-file progress bars with speed and percentage
- Overall download progress bar
- Skips already downloaded files — safe to stop and resume anytime
- Auto-retries failed downloads (3 attempts)
- Scrollable file list showing status of every part
- Works overnight unattended

---

## Batch Size Guide

| Batch | Best For | Speed Per File |
|-------|----------|---------------|
| 1 | Slow connections (recommended) | Full bandwidth |
| 2 | Medium connections | Half bandwidth |
| 3 | Fast connections | Third bandwidth |
| 4-5 | Very fast connections | Shared bandwidth |
| 6 | Max — risk of rate limiting | Shared bandwidth |

> Each file is ~500 MB. Do not exceed 5 — fuckingfast.co will rate limit you.

---

## Tips

- If you stop the script mid-download, just rerun — already completed files are skipped automatically
- Best strategy for slow connections: **batch size 1, leave overnight**
- If a file fails all 3 retries it gets cleaned up and you can rerun to retry it

---

## Project Structure

```
fitgirl-repack-downloader/
├── main.py            # GUI app
├── START.bat          # double-click to launch
├── requirements.txt
├── screenshots/
│   └── gui.png        # add your GUI screenshot here
└── README.md
```

---

## License

MIT
