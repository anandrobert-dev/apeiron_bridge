# Apeiron Bridge: Standalone App Build Guide (Ubuntu 22.04)

This guide explains how to bundle the Apeiron Bridge application into a standalone executable package specifically for **Ubuntu 22.04**.

> [!WARNING]
> **Important Note on `glibc` Compatibility**
> If you develop the app on Ubuntu 24.04, building the executable on that machine will link it against a newer `glibc` version (v2.39+). This binary **will fail to run** on Ubuntu 22.04 (which uses `glibc` v2.35).
> 
> **To create a standalone app for Ubuntu 22.04, you MUST run the build process on an actual Ubuntu 22.04 system (e.g., a physical machine, a Virtual Machine, or a Docker container).**

---

## Step 1: Prepare the Ubuntu 22.04 Environment

On your Ubuntu 22.04 machine, clone the repository containing the fully updated source code.

```bash
# Clone the repository
git clone https://github.com/anandrobert-dev/apeiron_bridge.git
cd apeiron_bridge

# Install necessary system packages for Python compilation
sudo apt update
sudo apt install python3-venv python3-dev build-essential libxcb-cursor0
```

> *Note: `libxcb-cursor0` is a common Qt6 dependency missing on some fresh Ubuntu installs.*

## Step 2: Set up the Python Virtual Environment

Create a clean virtual environment and install all dependencies from `requirements.txt`. PyInstaller requires all modules to be installed in the active environment to bundle them correctly.

```bash
# Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the required Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 3: Build the Standalone Package with PyInstaller

We will use `pyinstaller` to bundle the app. We need to tell it to run in "windowed" mode (no terminal console) and to include our static assets (the `resources` folder).

```bash
# Run PyInstaller
pyinstaller --name Apeiron_Bridge \
            --windowed \
            --icon=resources/icon.png \
            --add-data "resources:resources" \
            main.py
```

### Explanation of flags:
* `--name Apeiron_Bridge`: Names the final executable file.
* `--windowed`: Prevents a black terminal window from staying open behind the GUI application.
* `--icon`: Applies the application icon (if supported by your desktop environment).
* `--add-data "resources:resources"`: Copies the `resources/` folder into the compiled bundle so styles, images, and HTML guides load correctly. Look out for the `:` separator which is standard on Linux.

## Step 4: Locate & Run Your Bundle

Once the process finishes, PyInstaller will generate two new folders: `build/` and `dist/`.

1. **Locate the App**: Navigate to the `dist/Apeiron_Bridge/` directory.
   ```bash
   cd dist/Apeiron_Bridge
   ```
2. **Run it**: You can double-click the `Apeiron_Bridge` executable file from your file manager, or run it via terminal:
   ```bash
   ./Apeiron_Bridge
   ```

### Distributing the App
To share the standalone app with other Ubuntu 22.04 users, simply zip the entire `dist/Apeiron_Bridge` folder folder and send it to them. They can extract it and run the executable directly without needing to install Python or any dependencies!
