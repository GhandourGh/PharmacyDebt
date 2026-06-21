# Pharmacy Debt System — Quick guide (Windows, Git, tests)

Short reference for syncing code safely and running tests with this project.

---

## 1. Safe pull on Windows (keep existing data)

Git **does not** replace these local files when you pull (they are in `.gitignore`):

- `pharmacy.db` — all customer and ledger data  
- `.env` — your secrets and local settings  
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

Default URL: `http://127.0.0.1:5001`

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

3. Optional keys:

   - `SECRET_KEY` — recommended for production  

---

## 4. Fresh clone on a new machine

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

## 5. Checklist

| Task | Command / note |
|------|----------------|
| Backup data | Copy `pharmacy.db`, `.env`, `uploads` |
| Pull code | `git pull --ff-only origin main` |
| Dependencies | `pip install -r requirements.txt` |
| Tests | `python run_tests.py` |
| Run app | `python app.py` |

---

*Last updated for this repository’s layout (`pharmacy.db` in project root, Flask `app.py`, default port 5001).*
