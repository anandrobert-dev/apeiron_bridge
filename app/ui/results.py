
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QTabWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
import pandas as pd


class ResultsScreen(QWidget):
    """
    Displays the reconciliation results with two tabs:
      1. Detailed View — full row-by-row match output
      2. Discrepancy Report — summarized delta/status per invoice
    """
    go_home = Signal()
    go_back = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_df = None
        self.discrepancy_df = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Reconciliation Results")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)
        
        self.lbl_stats = QLabel("Total Rows: 0")
        layout.addWidget(self.lbl_stats)

        # Tab Widget for Detailed View + Discrepancy Report
        self.tabs = QTabWidget()
        
        # Tab 1: Detailed View
        self.table_detail = QTableWidget()
        self.tabs.addTab(self.table_detail, "📋 Detailed View")
        
        # Tab 2: Discrepancy Report
        self.table_discrepancy = QTableWidget()
        self.tabs.addTab(self.table_discrepancy, "⚠️ Discrepancy Report")
        
        layout.addWidget(self.tabs)
        
        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back to Mapping")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_home = QPushButton("New Reconciliation")
        self.btn_home.clicked.connect(self.go_home.emit)
        
        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setObjectName("PrimaryButton")
        self.btn_export.clicked.connect(self.export_data)
        
        footer.addWidget(self.btn_back)
        footer.addWidget(self.btn_home)
        footer.addStretch()
        footer.addWidget(self.btn_export)
        layout.addLayout(footer)

    def display_results(self, df: pd.DataFrame, discrepancy_df: pd.DataFrame = None):
        self.result_df = df
        self.discrepancy_df = discrepancy_df
        
        # Update Stats
        total = len(df)
        disc_count = len(discrepancy_df) if discrepancy_df is not None and not discrepancy_df.empty else 0
        match_count = 0
        issue_count = 0
        if discrepancy_df is not None and not discrepancy_df.empty and 'Status' in discrepancy_df.columns:
            match_count = len(discrepancy_df[discrepancy_df['Status'] == 'MATCH'])
            issue_count = disc_count - match_count
        
        self.lbl_stats.setText(
            f"Total Rows: {total}  |  Invoices: {disc_count}  |  "
            f"Matches: {match_count}  |  Issues: {issue_count}"
        )
        
        # --- Tab 1: Detailed View ---
        self._populate_table(self.table_detail, df)
        
        # --- Tab 2: Discrepancy Report ---
        if discrepancy_df is not None and not discrepancy_df.empty:
            self._populate_table(self.table_discrepancy, discrepancy_df)
            self._colorize_discrepancy(self.table_discrepancy, discrepancy_df)
            # Auto-switch to Discrepancy tab to show the important data first
            self.tabs.setCurrentIndex(1)
        else:
            self.table_discrepancy.setRowCount(0)
            self.table_discrepancy.setColumnCount(1)
            self.table_discrepancy.setHorizontalHeaderLabels(["Info"])
            self.table_discrepancy.setItem(0, 0, QTableWidgetItem("No discrepancy data available."))

    def _populate_table(self, table: QTableWidget, df: pd.DataFrame):
        """Populate a QTableWidget from a DataFrame."""
        preview_limit = 200
        preview_df = df.head(preview_limit)
        
        table.setColumnCount(len(preview_df.columns))
        table.setRowCount(len(preview_df))
        table.setHorizontalHeaderLabels(preview_df.columns.astype(str))
        
        for i in range(len(preview_df)):
            for j, val in enumerate(preview_df.iloc[i]):
                cell = QTableWidgetItem(str(val) if pd.notna(val) else "")
                table.setItem(i, j, cell)
                
        table.resizeColumnsToContents()

    def _colorize_discrepancy(self, table: QTableWidget, df: pd.DataFrame):
        """Apply color-coding to the discrepancy report table."""
        cols = list(df.columns)
        
        idx_delta = cols.index('Delta') if 'Delta' in cols else -1
        idx_status = cols.index('Status') if 'Status' in cols else -1
        
        # Colors
        clr_red_bg = QColor("#3D1F1F")       # Dark red background
        clr_red_text = QColor("#FF6B6B")      # Red text
        clr_green_bg = QColor("#1F3D1F")      # Dark green background
        clr_green_text = QColor("#6BCB77")    # Green text
        clr_match_bg = QColor("#1F2D3D")      # Dark blue background
        clr_match_text = QColor("#64B5F6")    # Blue text
        clr_amber_bg = QColor("#3D3D1F")      # Dark amber background
        clr_amber_text = QColor("#FFD54F")    # Amber text
        
        for row_idx in range(min(len(df), 200)):
            row = df.iloc[row_idx]
            
            # Color Delta column
            if idx_delta >= 0:
                delta = row['Delta']
                item = table.item(row_idx, idx_delta)
                if item:
                    if delta < -0.01:
                        item.setBackground(QBrush(clr_red_bg))
                        item.setForeground(QBrush(clr_red_text))
                    elif delta > 0.01:
                        item.setBackground(QBrush(clr_amber_bg))
                        item.setForeground(QBrush(clr_amber_text))
                    else:
                        item.setBackground(QBrush(clr_green_bg))
                        item.setForeground(QBrush(clr_green_text))
            
            # Color Status column
            if idx_status >= 0:
                status = str(row['Status'])
                item = table.item(row_idx, idx_status)
                if item:
                    if "MATCH" in status and "MIS" not in status:
                        item.setBackground(QBrush(clr_match_bg))
                        item.setForeground(QBrush(clr_match_text))
                    elif "Overpaid" in status or "MISSING IN SOA" in status:
                        item.setBackground(QBrush(clr_red_bg))
                        item.setForeground(QBrush(clr_red_text))
                    elif "Underpaid" in status or "MISSING IN REF" in status:
                        item.setBackground(QBrush(clr_amber_bg))
                        item.setForeground(QBrush(clr_amber_text))
            
            # Color entire row background lightly based on status
            if idx_status >= 0:
                status = str(row['Status'])
                if "MATCH" in status and "MIS" not in status:
                    row_color = QColor("#1A2A1A")  # Very subtle green
                elif "Overpaid" in status or "MISSING" in status:
                    row_color = QColor("#2A1A1A")  # Very subtle red
                else:
                    row_color = None
                
                if row_color:
                    for col_idx in range(len(cols)):
                        if col_idx != idx_delta and col_idx != idx_status:
                            cell = table.item(row_idx, col_idx)
                            if cell:
                                cell.setBackground(QBrush(row_color))

    def export_data(self):
        if self.result_df is None:
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "reconciliation_results.xlsx", "Excel Files (*.xlsx)"
        )
        
        if path:
            try:
                with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                    self.result_df.to_excel(writer, index=False, sheet_name='Detailed View')
                    if self.discrepancy_df is not None and not self.discrepancy_df.empty:
                        self.discrepancy_df.to_excel(writer, index=False, sheet_name='Discrepancy Report')
                QMessageBox.information(self, "Success", f"Data exported to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
