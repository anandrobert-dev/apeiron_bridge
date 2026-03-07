# 🚀 Deployment Guide: Building on Ubuntu 22.04

To ensure your app works on all field machines, you must build it on your **Ubuntu 22.04** machine to avoid `glibc` backward-compatibility issues.

## 📦 Step 1: Copy Files to Flash Drive

Create a new folder on your flash drive (e.g., `Apeiron_Bridge_Source`) and copy **ONLY** these files and folders into it.

### ✅ Folders to Copy

* `app/`
* `resources/`

### ✅ Files to Copy

* `main.py`
* `requirements.txt`
* `APIERON.png` (The main logo in root folder)
* `install.sh` (We will need this later)
* `uninstall.sh`

### ❌ DO NOT Copy (Skip these)

* `venv/`
* `build/`
* `dist/`
* `.git/`
* `__pycache__/` folders
* `tests/`
* `output/`

---

## 🛠️ Step 2: Set Up on Ubuntu 22.04

1. **Paste the Folder**: Copy the `Apeiron_Bridge_Source` folder from your flash drive to the destination computer (e.g., to the Desktop).
2. **Open Terminal**: Right-click inside that folder and select **"Open in Terminal"**.

### 1. Install System Requirements

**IMPORTANT:** These commands use `sudo` because they install system-level Python and UI dependency packages. You will be prompted for your password.

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev build-essential libxcb-cursor0
```

**What this installs:**
- `python3-pip`, `python3-venv`: Python package management and virtual environments
- `build-essential`, `python3-dev`: Compiler tools for building Python packages
- `libxcb-cursor0`: Qt6/PySide6 dependency for the GUI that is often missing on fresh Ubuntu 22.04 installs.

### 2. Setup Python Environment

**NOTE:** These commands use `pip` (within a virtual environment), NOT `sudo`. Never use `sudo pip` as it can break your system's Python installation.

```bash
# Create a fresh virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies (pip, NOT sudo)
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

---

## 🏗️ Step 3: Build the App

Run the following command to bundle your PySide6 application. This creates a standalone folder with your binary and required assets.

```bash
pyinstaller --noconfirm --onedir --windowed --name "Apeiron_Bridge" \
  --add-data "resources:resources" \
  --hidden-import "PySide6" \
  --hidden-import "pandas" \
  --hidden-import "openpyxl" \
  --hidden-import "rapidfuzz" \
  --icon "resources/icon.png" \
  main.py
```

*Note: we are using `--onedir` instead of `--onefile` for PySide6 apps specifically to avoid painfully slow startup times caused by PyInstaller unzipping Qt libraries on every run.*

---

## 🚀 Step 4: Verify & Deploy

1. **Check the Output**: You will now see a new `dist/Apeiron_Bridge` folder.
2. **Test It**: Run `./dist/Apeiron_Bridge/Apeiron_Bridge` to make sure it opens.
3. **Prepare for Fleet**:
   
   Copy these files to a folder for distribution:
   * `dist/Apeiron_Bridge/` - The entire bundled directory
   * `resources/icon.png` - The application icon
   * `install.sh` - Installation script
   * `uninstall.sh` - Uninstallation script

4. **Deploy to Target Machines**:
   
   On each target machine, copy the distribution folder, open a terminal inside it, and run:
   ```bash
   chmod +x install.sh uninstall.sh
   ./install.sh
   ```

---

## 📝 Troubleshooting

### App doesn't start or `libxcb-cursor` error
- PySide6 requires Qt6 cursor libraries: `sudo apt install libxcb-cursor0`

### Missing modules (`ModuleNotFoundError: No module named '...'`)
- Make sure you ran `pip install -r requirements.txt` before compiling with `pyinstaller`. PyInstaller only picks up modules installed in the currently active environment.
- Try explicitly adding the module to your build command: `--hidden-import "<module_name>"`

### `glibc` errors on other machines
- Make sure you followed these instructions entirely on an **Ubuntu 22.04** machine. Code built on Ubuntu 24.04 cannot be run on Ubuntu 22.04 due to newer C-libraries.
