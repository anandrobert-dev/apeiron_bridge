# Apeiron Bridge

Welcome to **Apeiron Bridge**, a high-performance reconciliation engine designed to bridge data discrepancies across disjointed datasets.

## Features

- **🧠 AI Insights Engine**: Automatically analyzes reconciliation results to calculate Risk Scores, detect statistical anomalies, grade source reliability, and identify systematic payment patterns—all using local statistical processing (no cloud APIs).
- **⚡ High-Performance Architecture**: Process 200MB+ files smoothly via off-main-thread QThread workers, fully vectorized data parsing, and real-time chunked progress reporting.
- **SOA Reconciliation**: Quickly analyze large Statements of Account against internal records.
- **Multi-File Comparison**: Combine multiple datasets into a single cohesive report with custom schemas.
- **Visual Mapping**: Map target output columns to localized file headers easily using a clean PySide6 UI.
- **Custom Reference Naming**: Ensure export column headers perfectly match your internal nomenclature instead of generic "Ref1" labels.
- **File Sequencing & Reordering**: Pick, drag, drop, or use keyboard shortcuts (`Alt/Ctrl + Up/Down`) to instantly sequence how source files are processed in Multi-File mode.
- **Template Persistency**: Save and reload your localized matching configurations into templates.
