# Windows Setup Guide - Pharmacy Debt System
## Complete Setup Instructions for New Windows Laptop (GitHub Clone)

This guide will walk you through every step needed to clone and set up the Pharmacy Debt Management System from GitHub on a brand new Windows laptop. The system will start with a fresh, empty database.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installing Git](#installing-git)
3. [Installing Python](#installing-python)
4. [Installing Node.js (Optional - for frontend dependencies)](#installing-nodejs-optional)
5. [Cloning from GitHub](#cloning-from-github)
6. [Installing Python Dependencies](#installing-python-dependencies)
7. [Installing Node.js Dependencies (Optional)](#installing-nodejs-dependencies-optional)
8. [Setting Up the Database](#setting-up-the-database)
9. [Creating Your First Admin User](#creating-your-first-admin-user)
10. [Running the Application](#running-the-application)
11. [Verifying Everything Works](#verifying-everything-works)
12. [Updating the Application (Git Pull/Push)](#updating-the-application)
13. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, make sure you have:
- Internet connection on the new Windows laptop
- Administrator access on the new Windows laptop
- A GitHub account (if you want to push changes)
- GitHub repository access (the repository should be accessible)

---

## Installing Git

Git is needed to clone the repository from GitHub and manage updates.

### Step 1: Download Git

1. **Open your web browser** (Edge, Chrome, or Firefox)

2. **Go to**: https://git-scm.com/download/win

3. **Click the download button** (it will automatically detect your Windows version)

4. **Wait for the download to complete** (file will be named something like `Git-2.43.x-64-bit.exe`)

### Step 2: Install Git

1. **Open File Explorer** and go to your **Downloads** folder

2. **Double-click** the Git installer file (the `.exe` file you just downloaded)

3. **Click "Next"** through the installation wizard

4. **Important settings**:
   - **Editor**: Choose your preferred text editor (Notepad++ or VS Code recommended, or keep default)
   - **Default branch name**: Keep as "main" (or "master" if that's what your repo uses)
   - **PATH environment**: Select "Git from the command line and also from 3rd-party software" (recommended)
   - **Line ending conversions**: Select "Checkout Windows-style, commit Unix-style line endings" (default)

5. **Click "Install"** and wait for installation (takes 2-5 minutes)

6. **Click "Finish"** when done

### Step 3: Verify Git Installation

1. **Open Command Prompt**:
   - Press `Windows Key + R`
   - Type `cmd` and press Enter
   - OR press `Windows Key`, type "Command Prompt", and click it

2. **Test Git**:
   - Type: `git --version`
   - Press Enter
   - You should see something like: `git version 2.43.x`

3. **Configure Git** (first time setup):
   ```
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```
   Replace with your actual name and email (this is used for commit messages)

If Git works, you're ready to clone the repository!

---

## Installing Python

### Step 1: Download Python

1. **Open your web browser** (Edge, Chrome, or Firefox)

2. **Go to**: https://www.python.org/downloads/

3. **Click the big yellow button** that says "Download Python 3.x.x" (latest version)

4. **Wait for the download to complete** (file will be named something like `python-3.12.x-amd64.exe`)

### Step 2: Install Python

1. **Open File Explorer** and go to your **Downloads** folder

2. **Double-click** the Python installer file (the `.exe` file you just downloaded)

3. **IMPORTANT**: Check the box that says **"Add Python to PATH"** at the bottom of the installer window
   - This is crucial! If you don't check this, you'll have problems later

4. **Click "Install Now"**

5. **Wait for installation** (this takes 2-5 minutes)

6. **When you see "Setup was successful"**, click **"Close"**

### Step 3: Verify Python Installation

1. **Open a NEW Command Prompt** (close and reopen if you had one open)

2. **Test Python**:
   - Type: `python --version`
   - Press Enter
   - You should see something like: `Python 3.12.x`

3. **Test pip** (Python package installer):
   - Type: `pip --version`
   - Press Enter
   - You should see something like: `pip 24.x from ...`

If both commands work, Python is installed correctly! If not, see the Troubleshooting section.

---

## Installing Node.js (Optional)

**Note**: Node.js is only needed if you plan to modify the frontend JavaScript/CSS. If you're just running the application, you can skip this section.

### Step 1: Download Node.js

1. **Go to**: https://nodejs.org/

2. **Download the LTS version** (recommended) - click the green button

3. **Wait for download** (file will be named something like `node-v20.x.x-x64.msi`)

### Step 2: Install Node.js

1. **Double-click** the downloaded `.msi` file

2. **Click "Next"** through the installation wizard (accept defaults)

3. **Click "Install"** (you may need to allow administrator access)

4. **Wait for installation**

5. **Click "Finish"**

### Step 3: Verify Node.js Installation

1. **Open a NEW Command Prompt** (close and reopen if you had one open)

2. **Type**: `node --version`
   - Should show something like: `v20.x.x`

3. **Type**: `npm --version`
   - Should show something like: `10.x.x`

---

## Cloning from GitHub

### Step 1: Choose Installation Location

Decide where you want to install the project on your new laptop:
- Recommended: `C:\Users\YourName\Desktop\`
- Or: `C:\Users\YourName\Documents\`
- Or: `C:\Projects\` (create this folder if it doesn't exist)

### Step 2: Clone the Repository

1. **Open Command Prompt**

2. **Navigate to where you want the project**:
   ```
   cd C:\Users\YourName\Desktop
   ```
   (Replace with your chosen location)

3. **Clone the repository**:
   ```
   git clone https://github.com/GhandourGh/PharmacyDebt.git
   ```

4. **Wait for cloning to complete** (this downloads all the files from GitHub)

5. **Navigate into the project folder**:
   ```
   cd PharmacyDebt\pharmacy-debt-system
   ```

   **Note**: The repository structure is `PharmacyDebt/pharmacy-debt-system/`, so you need to go into the `pharmacy-debt-system` subfolder.

6. **Verify the files are there**:
   ```
   dir
   ```
   You should see `app.py`, `database.py`, `requirements.txt`, `templates/`, `static/`, etc.

### Step 3: Verify Folder Structure

Make sure your folder structure looks like this:
```
PharmacyDebt/
└── pharmacy-debt-system/
    ├── app.py
    ├── database.py
    ├── requirements.txt
    ├── package.json
    ├── templates/
    │   ├── base.html
    │   ├── dashboard.html
    │   ├── customers.html
    │   └── ... (all other .html files)
    ├── static/
    │   ├── style.css
    │   ├── script.js
    │   ├── logo.svg
    │   └── uploads/        ← Will be empty initially
    └── ... (other .py files)
```

**Important Notes**:
- There will be NO `pharmacy.db` file initially (it will be created automatically)
- The `static/uploads/` folder will be empty (no customer images yet)
- This is normal - you're starting fresh!

---

## Installing Python Dependencies

### Step 1: Install Required Packages

1. **Make sure you're in the project folder**:
   ```
   cd C:\Users\YourName\Desktop\PharmacyDebt\pharmacy-debt-system
   ```

2. **Install Flask and other dependencies**:
   ```
   pip install -r requirements.txt
   ```
   
   This will install:
   - Flask (web framework)
   - ReportLab (PDF generation)

3. **Wait for installation** (takes 1-3 minutes)

4. **You should see**: "Successfully installed flask-x.x.x reportlab-x.x.x"

### Step 2: Verify Installation

1. **Test Flask installation**:
   ```
   python -c "import flask; print('Flask installed successfully')"
   ```

2. **Test ReportLab installation**:
   ```
   python -c "import reportlab; print('ReportLab installed successfully')"
   ```

If both show success messages, you're good to go!

---

## Installing Node.js Dependencies (Optional)

**Only do this if you installed Node.js and want to modify frontend code.**

1. **Make sure you're in the project folder**

2. **Install Node packages**:
   ```
   npm install
   ```

3. **Wait for installation** (this may take 5-10 minutes as it downloads many packages)

---

## Setting Up the Database

### Important: Fresh Database

When you first run the application, it will automatically create a new, empty `pharmacy.db` file. This means:
- **No existing customers**
- **No existing debts**
- **No existing products**
- **No existing users**

You'll need to create everything from scratch.

### Step 1: Verify Database Will Be Created

The database is created automatically when you first run `app.py`. The `database.py` file contains code that creates all necessary tables.

### Step 2: Ensure Uploads Folder Exists

The `static/uploads/` folder should already exist (it's in the repository), but verify:

1. **Check if folder exists**:
   ```
   dir static\uploads
   ```

2. **If it doesn't exist**, create it:
   ```
   mkdir static\uploads
   ```

The folder will be empty initially - customer images will be uploaded as you add customers.

---

## Creating Your First Admin User

Since you're starting with a fresh database, you'll need to create your first admin user. The application should handle this automatically, but here's what to expect:

### Option 1: Automatic User Creation

Some applications create a default admin user on first run. Check the `database.py` file or run the application and try logging in.

### Option 2: Manual User Creation (If Needed)

If the application doesn't create a default user, you may need to:

1. **Check if there's a setup script** in the repository
2. **Or create a user directly in the database** (advanced - requires SQL knowledge)
3. **Or use the application's user management interface** (if accessible without login)

**Note**: Check the application's documentation or contact the repository owner for the default login credentials if a default admin user is created.

---

## Running the Application

### Step 1: Start the Application

1. **Open Command Prompt**

2. **Navigate to project folder**:
   ```
   cd C:\Users\YourName\Desktop\PharmacyDebt\pharmacy-debt-system
   ```

3. **Run the application**:
   ```
   python app.py
   ```

4. **You should see output like**:
   ```
   * Running on http://127.0.0.1:5001
   * Debug mode: on
   ```

5. **The database will be created automatically** on first run - you may see messages about table creation.

### Step 2: Access the Application

1. **Open your web browser** (Edge, Chrome, Firefox, etc.)

2. **Go to**: `http://localhost:5001`
   - OR: `http://127.0.0.1:5001`

3. **You should see the login page** or dashboard

### Step 3: Initial Setup

1. **Log in** (or create your first admin user if needed)

2. **Start adding data**:
   - Add products first (Products → Add Product)
   - Add customers (Customers → Add Customer)
   - Start recording debts and payments

### Step 4: Keep Application Running

- **Keep the Command Prompt window open** while using the application
- **To stop the application**: Press `Ctrl + C` in the Command Prompt window
- **To start again**: Run `python app.py` again

---

## Verifying Everything Works

### Checklist:

- [ ] Git is installed and working (`git --version`)
- [ ] Python is installed and working (`python --version`)
- [ ] Repository cloned successfully from GitHub
- [ ] Dependencies are installed (`pip list` shows flask and reportlab)
- [ ] Application starts without errors (`python app.py`)
- [ ] Database file (`pharmacy.db`) is created automatically
- [ ] Can access application in browser (`http://localhost:5001`)
- [ ] Can log in (or create first admin user)
- [ ] Dashboard loads correctly
- [ ] Can add a product
- [ ] Can add a customer
- [ ] Can record a debt transaction
- [ ] Can generate PDF reports

### Quick Test Commands

Run these in Command Prompt (in project folder) to verify:

```bash
# Check Git
git --version

# Check Python
python --version

# Check dependencies
pip list | findstr flask
pip list | findstr reportlab

# Check project files
dir app.py
dir database.py

# Check database was created (after first run)
dir pharmacy.db
```

---

## Updating the Application (Git Pull/Push)

### Pulling Latest Changes from GitHub

When you want to get the latest updates from GitHub:

1. **Open Command Prompt**

2. **Navigate to project folder**:
   ```
   cd C:\Users\YourName\Desktop\PharmacyDebt\pharmacy-debt-system
   ```

3. **Make sure you're not running the application** (stop it with `Ctrl + C` if it's running)

4. **Pull latest changes**:
   ```
   git pull
   ```

5. **Wait for update to complete**

6. **If there are new Python dependencies**, install them:
   ```
   pip install -r requirements.txt
   ```

7. **Restart the application**:
   ```
   python app.py
   ```

**Important**: Your local database (`pharmacy.db`) and uploaded files (`static/uploads/`) are NOT affected by `git pull`. Only code files are updated.

### Pushing Your Changes to GitHub

If you make code changes and want to save them to GitHub:

1. **Make your code changes** (edit files as needed)

2. **Check what files changed**:
   ```
   git status
   ```

3. **Stage your changes**:
   ```
   git add .
   ```
   (This adds all changed files - be careful not to add `pharmacy.db` or `static/uploads/` - these should be in `.gitignore`)

4. **Commit your changes**:
   ```
   git commit -m "Description of your changes"
   ```
   Example: `git commit -m "Fixed customer search bug"`

5. **Push to GitHub**:
   ```
   git push
   ```
   (You may need to enter your GitHub username and password/token)

**Important Notes**:
- **Never commit `pharmacy.db`** - it contains your local data and should be in `.gitignore`
- **Never commit `static/uploads/`** - these are user-uploaded files and should be in `.gitignore`
- Only commit code changes (`.py`, `.html`, `.css`, `.js` files, etc.)

### Checking Git Status

To see what files have changed:
```
git status
```

To see what changes you made:
```
git diff
```

---

## Troubleshooting

### Problem: "git is not recognized"

**Solution**:
1. Git wasn't added to PATH during installation
2. **Reinstall Git** and make sure to select "Git from the command line" option
3. **Close and reopen Command Prompt** after installation

### Problem: "python is not recognized"

**Solution**:
1. Python wasn't added to PATH during installation
2. **Reinstall Python** and make sure to check "Add Python to PATH"
3. OR manually add Python to PATH (advanced - see below)

**Manual PATH fix**:
1. Search for "Environment Variables" in Windows
2. Click "Edit the system environment variables"
3. Click "Environment Variables"
4. Under "System variables", find "Path" and click "Edit"
5. Click "New" and add: `C:\Users\YourName\AppData\Local\Programs\Python\Python3xx`
6. Click OK on all windows
7. **Close and reopen Command Prompt**

### Problem: "pip is not recognized"

**Solution**: Same as above - Python wasn't added to PATH

### Problem: "fatal: repository not found" when cloning

**Solution**:
1. Check the repository URL is correct: `https://github.com/GhandourGh/PharmacyDebt.git`
2. Make sure you have internet connection
3. The repository might be private - you may need to authenticate with GitHub
4. Try accessing the repository in your browser first to verify it exists

### Problem: "Permission denied" when cloning

**Solution**:
1. Check that you have write permissions to the destination folder
2. Try running Command Prompt as Administrator
3. Try cloning to a different location (like Desktop or Documents)

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution**:
1. Make sure you're in the project folder (`pharmacy-debt-system`)
2. Run: `pip install -r requirements.txt`
3. If that doesn't work, try: `python -m pip install -r requirements.txt`

### Problem: "Address already in use" or "Port 5001 already in use"

**Solution**:
1. Another program is using port 5001
2. **Option 1**: Close the other program
3. **Option 2**: Run on a different port:
   ```
   python app.py 5002
   ```
   Then access at: `http://localhost:5002`

### Problem: Database is empty (no customers, no data)

**Solution**: This is **NORMAL**! You cloned a fresh copy from GitHub, so the database starts empty. You need to:
1. Add products first
2. Add customers
3. Start recording transactions
4. The database will grow as you use the system

### Problem: Can't log in / No users exist

**Solution**:
1. This is normal for a fresh installation
2. Check if the application creates a default admin user on first run
3. Check the repository documentation for default credentials
4. You may need to create the first user manually (see "Creating Your First Admin User" section)

### Problem: "git pull" shows merge conflicts

**Solution**:
1. This happens when you've made local changes that conflict with GitHub changes
2. **Option 1**: Stash your changes, pull, then reapply:
   ```
   git stash
   git pull
   git stash pop
   ```
3. **Option 2**: Commit your changes first, then pull and resolve conflicts manually
4. If unsure, ask for help or backup your `pharmacy.db` file before attempting

### Problem: "git push" asks for authentication

**Solution**:
1. GitHub no longer accepts passwords for git operations
2. You need to use a **Personal Access Token** instead:
   - Go to GitHub.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate a new token with "repo" permissions
   - Use this token as your password when pushing
3. OR use GitHub Desktop (easier GUI option)

### Problem: Application starts but shows errors

**Solution**:
1. Check the Command Prompt window for error messages
2. Common issues:
   - Missing dependencies → Run `pip install -r requirements.txt`
   - Database errors → Delete `pharmacy.db` and let it recreate (WARNING: This deletes all data!)
   - Permission errors → Run Command Prompt as Administrator
   - Port conflict → Use different port (see above)

### Problem: "Permission denied" errors

**Solution**:
1. **Run Command Prompt as Administrator**:
   - Press `Windows Key`
   - Type "Command Prompt"
   - Right-click it
   - Select "Run as administrator"
2. Navigate to project folder and try again

### Problem: Slow performance

**Solution**:
1. This is normal on first run (database initialization)
2. If consistently slow:
   - Check available disk space
   - Close other programs
   - Check if antivirus is scanning the folder (add exception)

---

## Creating a Desktop Shortcut (Optional but Recommended)

To make it easier to start the application:

### Method 1: Use the Provided Batch File

A batch file (`start_pharmacy_system.bat`) is already included in the repository. You can use it directly:

1. **Navigate to** your `pharmacy-debt-system` folder in File Explorer

2. **Find** `start_pharmacy_system.bat`

3. **Right-click** the file → **Create shortcut**

4. **Drag the shortcut** to your Desktop

5. **Rename it** to "Pharmacy Debt System" (optional)

6. **Double-click the shortcut** to start the application

### Method 2: Create Your Own Batch File

If you prefer to create your own:

1. **Open Notepad**

2. **Paste this** (adjust the path to your actual location):
   ```batch
   @echo off
   cd /d C:\Users\YourName\Desktop\PharmacyDebt\pharmacy-debt-system
   python app.py
   pause
   ```

3. **Save as**: `Start Pharmacy System.bat`
   - Save it in your `pharmacy-debt-system` folder
   - Make sure "Save as type" is set to "All Files (*.*)"

4. **Create shortcut**:
   - Right-click the `.bat` file
   - Select "Create shortcut"
   - Drag shortcut to Desktop
   - Rename it to "Pharmacy Debt System"

5. **Double-click the shortcut** to start the application

### Method 2: Pin to Taskbar

1. **Create the batch file** (see Method 1)

2. **Right-click the batch file**

3. **Select "Pin to taskbar"**

---

## Auto-Start on Windows Boot (Start Application Automatically)

To make the application start automatically when you turn on your laptop:

### Step 1: Use the Provided Batch File

A batch file (`start_pharmacy_system.bat`) is already included in the repository. If you don't see it, you can create it (see below).

### Step 2: Add to Windows Startup Folder

**Method 1: Using Startup Folder (Easiest)**

1. **Press `Windows Key + R`** to open the Run dialog

2. **Type**: `shell:startup`
   - This opens your personal Startup folder

3. **Press Enter**

4. **Create a shortcut to the batch file**:
   - Navigate to your `pharmacy-debt-system` folder in File Explorer
   - Find `start_pharmacy_system.bat`
   - **Right-click** the file
   - Select **"Create shortcut"**
   - **Copy** the shortcut (Ctrl+C)
   - Go back to the Startup folder window
   - **Paste** the shortcut (Ctrl+V)

5. **Rename the shortcut** (optional): Right-click → Rename → "Pharmacy Debt System"

**Method 2: Using Task Scheduler (More Control)**

1. **Press `Windows Key`** and type "Task Scheduler"

2. **Open Task Scheduler**

3. **Click "Create Basic Task"** in the right panel

4. **Name it**: "Pharmacy Debt System"
   - Click **Next**

5. **Trigger**: Select "When I log on"
   - Click **Next**

6. **Action**: Select "Start a program"
   - Click **Next**

7. **Program/script**: Click **Browse** and navigate to:
   ```
   C:\Users\YourName\Desktop\PharmacyDebt\pharmacy-debt-system\start_pharmacy_system.bat
   ```
   (Adjust path to your actual location)

8. **Click Next** → **Finish**

### Step 3: Test Auto-Start

1. **Restart your computer** (or log out and log back in)

2. **Wait a few seconds** after Windows loads

3. **Open your browser** and go to: `http://localhost:5001`

4. **The application should be running!**

### Step 4: Verify It's Running

- You should see a Command Prompt window open automatically (this is the application running)
- The browser should show the login page or dashboard
- You can minimize the Command Prompt window, but **don't close it** (that stops the application)

### Creating the Batch File (If It Doesn't Exist)

If `start_pharmacy_system.bat` is not in your repository:

1. **Open Notepad**

2. **Paste this**:
   ```batch
   @echo off
   REM Pharmacy Debt System - Auto Start Script
   cd /d "%~dp0"
   python app.py
   if errorlevel 1 (
       echo ERROR: Failed to start the application!
       pause
   )
   ```

3. **Save as**: `start_pharmacy_system.bat`
   - Save it in your `pharmacy-debt-system` folder
   - Make sure "Save as type" is set to "All Files (*.*)"

### Disabling Auto-Start (If Needed)

**To stop auto-starting**:

1. **Press `Windows Key + R`**

2. **Type**: `shell:startup`

3. **Press Enter**

4. **Delete the shortcut** to `start_pharmacy_system.bat`

**OR** if using Task Scheduler:

1. Open **Task Scheduler**

2. Find **"Pharmacy Debt System"** in the task list

3. **Right-click** → **Disable** (or **Delete**)

### Notes About Auto-Start

- **The Command Prompt window will appear** when the application starts - this is normal
- **You can minimize it** but don't close it (closing stops the application)
- **The application starts when you log in** to Windows
- **If Python isn't in PATH**, auto-start might fail - make sure Python installation added it to PATH
- **Internet connection** is not required for the application to start (it runs locally)

---

## Daily Usage

### Starting the Application

1. **Double-click your desktop shortcut** (if you created one)
   - OR open Command Prompt, navigate to folder, run `python app.py`

2. **Wait for**: `* Running on http://127.0.0.1:5001`

3. **Open browser** and go to: `http://localhost:5001`

### Stopping the Application

1. **Go to the Command Prompt window** where it's running

2. **Press**: `Ctrl + C`

3. **Confirm** if asked

### Updating from GitHub

**Regularly pull updates** to get the latest features and bug fixes:

1. **Stop the application** (`Ctrl + C`)

2. **Pull updates**:
   ```
   git pull
   ```

3. **Install any new dependencies**:
   ```
   pip install -r requirements.txt
   ```

4. **Restart the application**:
   ```
   python app.py
   ```

### Backing Up Your Data

**IMPORTANT**: Regularly backup `pharmacy.db`!

1. **Copy `pharmacy.db`** to:
   - USB drive
   - Cloud storage (OneDrive, Google Drive, Dropbox)
   - External hard drive

2. **Recommended**: Backup weekly or daily if you have many transactions

3. **Note**: `pharmacy.db` is NOT in git, so you must backup it manually

---

## Additional Notes

### Firewall Settings

Windows Firewall may ask for permission the first time you run the application. Click "Allow access" when prompted.

### Antivirus Software

Some antivirus software may flag Python scripts. If you get warnings:
1. Add the `pharmacy-debt-system` folder to antivirus exclusions
2. The application is safe - it only runs locally on your computer

### Git Configuration

If you want to use a different text editor for Git commits:
```
git config --global core.editor "notepad"
```
(Replace "notepad" with your preferred editor)

### Port Configuration

The application runs on port 5001 by default. To use a different port:
```
python app.py 8080
```
Then access at: `http://localhost:8080`

### What Gets Synced with GitHub

**Synced (in git)**:
- All code files (`.py`, `.html`, `.css`, `.js`)
- Configuration files (`requirements.txt`, `package.json`)
- Templates and static assets (except uploads)

**NOT Synced (local only)**:
- `pharmacy.db` - Your database with all data
- `static/uploads/` - Customer uploaded images
- `__pycache__/` - Python cache files

This means:
- Code updates come from GitHub (`git pull`)
- Your data stays local and safe
- Each computer has its own database

---

## Support

If you encounter issues not covered here:

1. **Check the error message** in Command Prompt
2. **Verify Git, Python, and dependencies are installed correctly**
3. **Check the GitHub repository** for issues or documentation
4. **Review the Troubleshooting section** above

---

## Summary Checklist

Before considering setup complete, verify:

- [ ] Git installed and configured (`git --version`)
- [ ] Python installed and working (`python --version`)
- [ ] Repository cloned from GitHub successfully
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Application starts successfully (`python app.py`)
- [ ] Database file (`pharmacy.db`) created automatically
- [ ] Can access in browser at `http://localhost:5001`
- [ ] Can log in (or create first admin user)
- [ ] Dashboard loads correctly
- [ ] Can add products and customers
- [ ] Can record transactions
- [ ] PDF reports can be generated
- [ ] `git pull` works for updates
- [ ] Understand how to backup `pharmacy.db`

**Once all items are checked, your setup is complete!**

---

*Last updated: January 2025*
*For Pharmacy Debt Management System v1.0*
*GitHub Repository: https://github.com/GhandourGh/PharmacyDebt*
