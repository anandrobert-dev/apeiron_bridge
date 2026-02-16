
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import pandas as pd

class ResultsScreen(QWidget):
    """
    Displays the reconciliation results and allows export.
    """
    go_home = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_df = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Reconciliation Results")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)
        
        self.lbl_stats = QLabel("Total Rows: 0 | Matches: 0")
        layout.addWidget(self.lbl_stats)

        # Table View
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        # Footer
        footer = QHBoxLayout()
        self.btn_home = QPushButton("New Reconciliation")
        self.btn_home.clicked.connect(self.go_home.emit)
        
        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setObjectName("PrimaryButton")
        self.btn_export.clicked.connect(self.export_data)
        
        footer.addWidget(self.btn_home)
        footer.addStretch()
        footer.addWidget(self.btn_export)
        layout.addLayout(footer)

    def display_results(self, df: pd.DataFrame):
        self.result_df = df
        
        # Update Stats
        total = len(df)
        self.lbl_stats.setText(f"Total Rows: {total}")
        
        # Populate Table (Preview first 100 rows)
        preview_limit = 100
        preview_df = df.head(preview_limit)
        
        self.table.setColumnCount(len(preview_df.columns))
        self.table.setRowCount(len(preview_df))
        self.table.setHorizontalHeaderLabels(preview_df.columns.astype(str))
        
        for i in range(len(preview_df)):
            for j, val in enumerate(preview_df.iloc[i]):
                self.table.setItem(i, j, QTableWidgetItem(str(val)))
                
        self.table.resizeColumnsToContents()

    def export_data(self):
        if self.result_df is None:
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "reconciliation_results.xlsx", "Excel Files (*.xlsx)"
        )
        
        if path:
            try:
                self.result_df.to_excel(path, index=False)
                QMessageBox.information(self, "Success", f"Data exported to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
