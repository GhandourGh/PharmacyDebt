# Windows Setup Guide - Pharmacy Debt System
## Complete Transfer Instructions for New Windows Laptop

This guide will walk you through every step needed to transfer and set up the Pharmacy Debt Management System on a brand new Windows laptop.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Transferring Files from Old Computer](#transferring-files-from-old-computer)
3. [Installing Python](#installing-python)
4. [Installing Node.js (Optional - for frontend dependencies)](#installing-nodejs-optional)
5. [Setting Up the Project](#setting-up-the-project)
6. [Installing Python Dependencies](#installing-python-dependencies)
7. [Installing Node.js Dependencies (Optional)](#installing-nodejs-dependencies-optional)
8. [Transferring the Database](#transferring-the-database)
9. [Transferring Uploaded Files](#transferring-uploaded-files)
10. [Running the Application](#running-the-application)
11. [Verifying Everything Works](#verifying-everything-works)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, make sure you have:
- Your old computer with the pharmacy-debt-system folder
- A USB drive or external hard drive (at least 1GB free space)
- Internet connection on the new Windows laptop
- Administrator access on the new Windows laptop

---

## Transferring Files from Old Computer

### Step 1: Prepare Files for Transfer

On your **OLD computer**:

1. **Locate the project folder**: Navigate to where your `pharmacy-debt-system` folder is located
   - Common locations: `Desktop`, `Documents`, or `C:\Users\YourName\`

2. **Copy the entire folder**: Right-click on the `pharmacy-debt-system` folder and select **Copy**

3. **Paste to USB drive**: 
   - Insert your USB drive
   - Open it in File Explorer
   - Right-click in an empty area and select **Paste**
   - Wait for the copy to complete (this may take a few minutes if you have many uploaded images)

4. **Verify the copy**: Make sure these folders/files are on the USB drive:
   - `pharmacy-debt-system/`
     - `app.py`
     - `database.py`
     - `pharmacy.db` (THIS IS CRITICAL - contains all your data!)
     - `requirements.txt`
     - `package.json`
     - `templates/` folder
     - `static/` folder (including `static/uploads/` with all customer images)
     - All other `.py` files

5. **Safely eject the USB drive**: Right-click the USB drive in File Explorer and select **Eject**

### Step 2: Transfer to New Computer

On your **NEW Windows laptop**:

1. **Insert the USB drive**

2. **Open File Explorer** (press `Windows Key + E`)

3. **Navigate to your USB drive** (usually shows as `D:`, `E:`, or `F:`)

4. **Copy the folder**: Right-click on `pharmacy-debt-system` and select **Copy**

5. **Choose a location on new laptop**:
   - Recommended: `C:\Users\YourName\Desktop\pharmacy-debt-system`
   - Or: `C:\Users\YourName\Documents\pharmacy-debt-system`
   - Or: `C:\pharmacy-debt-system` (if you prefer a system-wide location)

6. **Paste the folder**: Navigate to your chosen location, right-click in an empty area, and select **Paste**

7. **Wait for transfer to complete**

8. **Verify the folder structure**: Open the `pharmacy-debt-system` folder and confirm all files are there

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

1. **Open Command Prompt**:
   - Press `Windows Key + R`
   - Type `cmd` and press Enter
   - OR press `Windows Key`, type "Command Prompt", and click it

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

## Setting Up the Project

### Step 1: Navigate to Project Folder

1. **Open Command Prompt** (as described above)

2. **Navigate to your project folder**:
   ```
   cd C:\Users\YourName\Desktop\pharmacy-debt-system
   ```
   (Replace with your actual path if different)

3. **Verify you're in the right place**:
   ```
   dir
   ```
   You should see `app.py`, `database.py`, `requirements.txt`, etc.

---

## Installing Python Dependencies

### Step 1: Install Required Packages

1. **Make sure you're in the project folder** (see above)

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

## Transferring the Database

### Critical Step: Database File

The `pharmacy.db` file contains ALL your data:
- Customer information
- Debt records
- Payment history
- Products
- Donations
- User accounts
- Everything!

### Step 1: Verify Database File is Present

1. **In File Explorer**, navigate to your `pharmacy-debt-system` folder

2. **Look for `pharmacy.db`** - it should be there if you copied the entire folder

3. **Check the file size**: Right-click `pharmacy.db` → Properties
   - If it's 0 bytes or very small (less than 10KB), the database might be empty or corrupted
   - Normal size: Usually at least 50KB+ if you have data

### Step 2: If Database is Missing

If `pharmacy.db` is NOT in the folder:

1. **Go back to your old computer**

2. **Find `pharmacy.db`** in the `pharmacy-debt-system` folder

3. **Copy it separately** to your USB drive

4. **Transfer it** to the new computer's `pharmacy-debt-system` folder

### Step 3: Verify Database Integrity (Optional but Recommended)

1. **Open Command Prompt** in the project folder

2. **Test the database**:
   ```
   python -c "import sqlite3; conn = sqlite3.connect('pharmacy.db'); print('Database is valid'); conn.close()"
   ```

If you see "Database is valid", you're good!

---

## Transferring Uploaded Files

### Step 1: Verify Uploaded Images

The `static/uploads/` folder contains customer profile images and other uploaded files.

1. **Navigate to**: `pharmacy-debt-system\static\uploads\`

2. **Check that image files are present** (you should see `.jpg`, `.png`, etc. files)

3. **If the folder is empty or missing files**:
   - Go back to old computer
   - Copy the entire `static/uploads/` folder
   - Replace it on the new computer

### Step 2: Verify Folder Structure

Make sure your folder structure looks like this:
```
pharmacy-debt-system/
├── app.py
├── database.py
├── pharmacy.db          ← CRITICAL: Your data!
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
│   └── uploads/        ← Customer images
│       ├── 20260125...jpg
│       └── ... (all image files)
└── ... (other .py files)
```

---

## Running the Application

### Step 1: Start the Application

1. **Open Command Prompt**

2. **Navigate to project folder**:
   ```
   cd C:\Users\YourName\Desktop\pharmacy-debt-system
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

### Step 2: Access the Application

1. **Open your web browser** (Edge, Chrome, Firefox, etc.)

2. **Go to**: `http://localhost:5001`
   - OR: `http://127.0.0.1:5001`

3. **You should see the login page** or dashboard

### Step 3: Test Login

1. **Try logging in** with your existing username and password
   - If you don't remember credentials, see Troubleshooting section

2. **Check that you can see**:
   - Dashboard with debt totals
   - Customer list
   - Recent activity

### Step 4: Keep Application Running

- **Keep the Command Prompt window open** while using the application
- **To stop the application**: Press `Ctrl + C` in the Command Prompt window
- **To start again**: Run `python app.py` again

---

## Verifying Everything Works

### Checklist:

- [ ] Python is installed and working (`python --version`)
- [ ] Dependencies are installed (`pip list` shows flask and reportlab)
- [ ] Database file (`pharmacy.db`) is present and has data
- [ ] Uploaded images are in `static/uploads/` folder
- [ ] Application starts without errors (`python app.py`)
- [ ] Can access application in browser (`http://localhost:5001`)
- [ ] Can log in with existing credentials
- [ ] Dashboard shows correct debt totals
- [ ] Customer list displays correctly
- [ ] Customer images load properly
- [ ] Can view customer details
- [ ] Can generate PDF reports

### Quick Test Commands

Run these in Command Prompt (in project folder) to verify:

```bash
# Check Python
python --version

# Check dependencies
pip list | findstr flask
pip list | findstr reportlab

# Check database exists
dir pharmacy.db

# Check uploads folder
dir static\uploads
```

---

## Troubleshooting

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

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution**:
1. Make sure you're in the project folder
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

### Problem: Database is empty or missing data

**Solution**:
1. The `pharmacy.db` file wasn't transferred correctly
2. Go back to old computer and copy `pharmacy.db` again
3. Make sure to copy it to the exact same location: `pharmacy-debt-system/pharmacy.db`
4. Replace the existing file on new computer

### Problem: Images not loading (broken image icons)

**Solution**:
1. Check that `static/uploads/` folder exists and has files
2. Verify file paths in File Explorer
3. Make sure images were copied from old computer
4. Check file permissions (right-click folder → Properties → Security)

### Problem: Can't log in / Forgot password

**Solution**:
1. If you have admin access on old computer, check the database there
2. OR create a new admin user (see below)
3. OR reset password in database (advanced - requires SQL knowledge)

**Create new admin user** (if you have access to old computer):
- Use the old computer to create a new user
- Transfer the updated database

### Problem: Application starts but shows errors

**Solution**:
1. Check the Command Prompt window for error messages
2. Common issues:
   - Missing database file → Copy `pharmacy.db` again
   - Missing uploads folder → Create `static/uploads/` folder
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

### Method 1: Create Batch File

1. **Open Notepad**

2. **Paste this** (adjust the path to your actual location):
   ```batch
   @echo off
   cd /d C:\Users\YourName\Desktop\pharmacy-debt-system
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

### Backing Up Your Data

**IMPORTANT**: Regularly backup `pharmacy.db`!

1. **Copy `pharmacy.db`** to:
   - USB drive
   - Cloud storage (OneDrive, Google Drive, Dropbox)
   - External hard drive

2. **Recommended**: Backup weekly or daily if you have many transactions

---

## Additional Notes

### Firewall Settings

Windows Firewall may ask for permission the first time you run the application. Click "Allow access" when prompted.

### Antivirus Software

Some antivirus software may flag Python scripts. If you get warnings:
1. Add the `pharmacy-debt-system` folder to antivirus exclusions
2. The application is safe - it only runs locally on your computer

### Updates

To update Python packages in the future:
```
pip install --upgrade -r requirements.txt
```

### Port Configuration

The application runs on port 5001 by default. To use a different port:
```
python app.py 8080
```
Then access at: `http://localhost:8080`

---

## Support

If you encounter issues not covered here:

1. **Check the error message** in Command Prompt
2. **Verify all files are present** (especially `pharmacy.db`)
3. **Check that Python and dependencies are installed correctly**
4. **Review the Troubleshooting section** above

---

## Summary Checklist

Before considering setup complete, verify:

- [ ] All files transferred from old computer
- [ ] Python installed and working
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Database file (`pharmacy.db`) present and valid
- [ ] Uploaded images in `static/uploads/` folder
- [ ] Application starts successfully
- [ ] Can access in browser at `http://localhost:5001`
- [ ] Can log in with existing credentials
- [ ] Data appears correctly (customers, debts, etc.)
- [ ] Images load properly
- [ ] PDF reports can be generated

**Once all items are checked, your setup is complete!**

---

*Last updated: January 2025*
*For Pharmacy Debt Management System v1.0*

