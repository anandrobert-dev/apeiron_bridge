# Apeiron Bridge

Welcome to **Apeiron Bridge**, a high-performance data reconciliation and analysis engine designed to bridge differences across disjointed datasets and audit commercial contracts.

## Key Modules

### 1. 📊 Rate Analysis & Comparison (RA&C) [NEW]
A professional carrier-agreement intelligence dashboard divided into three specialized workflows:
- **Rate Comparison (Agreement vs. Agreement)**: Side-by-side comparison of line-haul rates, geographic zip-code nearby-lane substitution using a local Postgres database, missing-lane alerts, zero/on-request rate checks, and percentage/absolute rate deltas between renewed versions.
- **Terms & Conditions (T&C) Comparison**: Unified parser for extracting contractual clauses (payment terms, fuel surcharges, accessorial schedules, liability limits, and demurrage rules) into a structured taxonomy, generating a clause coverage matrix, change tracking (red/green diffs), and favorability scoring using editable grading rubrics.
- **Rate Analysis (Shipment History vs. Agreements)**: Full-loaded audit of historical shipments to compare billed rates against hypothetical multi-carrier quotes (calculating line-haul, fuel, accessorials, and minimums), highlighting potential routing savings and carrier rate-creep patterns.

### 2. 📑 Statement of Account (SOA) Reconciliation
Quickly audit large billing statements (SOA) against multiple system dumps or carrier records:
- **🧠 AI Insights Engine**: Automatically analyzes results to calculate Health/Risk Scores, detect IQR statistical outliers, grade reference reliability (A+ through D), and identify systematic payment patterns (e.g. constant 5% short-payments).
- **⚡ High-Performance Threading**: Process 200MB+ files smoothly via background `QThread` workers with zero UI freezing and live chunked progress updates.

### 3. 📂 Multi-File Comparison
- **Flexible Matching**: Combine and match schemas across 2 to 5 distinct files.
- **Drag-and-Drop Sequencing**: Reorder files visually to establish the primary processing sequence.
- **Templates**: Save and load custom matching schemas to automate recurring runs.

---

## 🔒 Data Security & Privacy
Apeiron Bridge is a **standalone desktop application** designed for Ubuntu 22.04 LTS and above.
* **100% Air-Gapped**: Customer pricing and freight details never leave the machine. No telemetry or external scraping services are used.
* **Graceful Degradation**: Optional AI integrations (narrative phrasing and clause summaries) operate on de-identified text snippets only and require user-provided API keys.

---

## Installation & Launch

### Prerequisites
Install Ubuntu system dependencies:
```bash
sudo ./install.sh
```

### Run
Ensure the virtual environment is active and launch:
```bash
source venv/bin/activate
python main.py
```

*Developed by Koinonia Technologies. All rights reserved.*
