# Pharmacy Debt System — Quick guide (Windows, Git, Ollama, tests)

Short reference for syncing code safely, running tests, and using Ollama with this project.

---

## 1. Safe pull on Windows (keep existing data)

Git **does not** replace these local files when you pull (they are in `.gitignore`):

- `pharmacy.db` — all customer and ledger data  
- `.env` — your secrets and Ollama settings  
- `static/uploads/` — uploaded images  
- `.venv/` — Python virtual environment  

**Recommended before pulling:** copy backups somewhere outside the repo (e.g. Desktop):

```powershell
cd C:\path\to\pharmacy-debt-system
copy pharmacy.db $HOME\Desktop\pharmacy.db.backup
copy .env $HOME\Desktop\.env.backup
```

**Safe update:**

```powershell
git status
git fetch origin
git pull --ff-only origin main
```

Use `master` instead of `main` if that is your default branch.

**Never run** `git clean -fdx` on this project — it can delete the database, `.env`, uploads, and the venv.

If `--ff-only` fails, your branch has diverged; resolve merges carefully. Do not use `git reset --hard` unless you only mean to drop **code** edits, not data files.

**After pulling:**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Default URL: `http://127.0.0.1:5055`

---

## 2. Tests (before push or after pull)

From the project folder:

```powershell
python run_tests.py
```

This runs all tests and, on some Python builds, avoids noisy `hashlib` / blake2 log spam.  
You can also use `python run_tests.py --unit`, `--integ`, or `--e2e`.

Direct `python -m pytest` may print harmless blake2-related errors on some installs; prefer `run_tests.py`.  
Tests use a **temporary** database — your real `pharmacy.db` is not touched.

---

## 3. Environment variables

1. Copy the template if you do not have `.env` yet:

   ```powershell
   copy .env.example .env
   ```

2. Edit `.env` as needed. Variables already set in the shell are **not** overridden by the app loader.

3. Important keys for the AI assistant (see `.env.example` for full list):

   - `OLLAMA_BASE_URL` — default `http://127.0.0.1:11434`  
   - `OLLAMA_MODEL` — default `qwen3.5:4b`  
   - `SECRET_KEY` — optional but recommended for production  

---

## 4. Ollama on Windows

### Install

1. Download **Ollama for Windows** from [https://ollama.com/download](https://ollama.com/download).  
2. Run the installer. Restart the terminal (or the PC) if `ollama` is not recognized.

### Model (matches this repo’s defaults)

```powershell
ollama pull qwen3.5:4b
ollama list
```

### Check the API

```powershell
curl http://127.0.0.1:11434/api/tags
```

### Match the pharmacy app

Ensure `.env` contains:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:4b
```

Restart `python app.py` after editing `.env`.

### Auto-run

Usually the Ollama Windows app **starts with Windows** and keeps serving on `127.0.0.1:11434`. Check the **system tray** for the Ollama icon. If it does not start after boot:

- Open **Ollama** from the Start menu once.  
- Enable it under **Settings → Apps → Startup** (or **Task Manager → Startup apps**).

You typically do **not** need to run `ollama serve` manually when the desktop app is running.

If Ollama is off, the app still runs; the chatbot falls back to **rule-based** mode (no local LLM).

---

## 5. Fresh clone on a new machine

```powershell
git clone https://github.com/GhandourGh/PharmacyDebt.git pharmacy-debt-system
cd pharmacy-debt-system
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Restore your **backups** of `pharmacy.db`, `.env`, and `static\uploads` if you are migrating data from another PC.

---

## 6. Checklist

| Task | Command / note |
|------|----------------|
| Backup data | Copy `pharmacy.db`, `.env`, `uploads` |
| Pull code | `git pull --ff-only origin main` |
| Dependencies | `pip install -r requirements.txt` |
| Tests | `python run_tests.py` |
| Run app | `python app.py` |
| Ollama | Install app, `ollama pull qwen3.5:4b`, `.env` URLs/model |

---

*Last updated for this repository’s layout (`pharmacy.db` in project root, Flask `app.py`, chat under `/chat` and the floating widget in `base.html`).*
