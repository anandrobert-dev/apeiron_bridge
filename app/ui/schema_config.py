
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QMessageBox, QLineEdit, QFrame, QAbstractScrollArea
)
from PySide6.QtCore import Qt, QEvent
import os

class SmartTableWidget(QTableWidget):
    """Table widget that adds a new row when Tabbing from the last cell."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.owner = parent # The widget containing the add_row method

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            # Check if we are at the last cell
            row = self.currentRow()
            col = self.currentColumn()
            
            if row == self.rowCount() - 1 and col == self.columnCount() - 1:
                # We are at the last cell, add a new row
                if self.owner and hasattr(self.owner, 'add_row'):
                    self.owner.add_row()
                    pass 
        
        super().keyPressEvent(event)

class SchemaConfigWidget(QWidget):
    """
    Reusable widget for defining a comparison schema.
    """
    def __init__(self, ref_files, ref_columns, initial_schema=None, parent=None):
        super().__init__(parent)
        self.ref_files = ref_files
        self.ref_columns = ref_columns
        self.schema = initial_schema if initial_schema else []
        self.init_ui()

    def init_ui(self):
        # Ensure we don't stack layouts if called multiple times
        if self.layout():
             # Already initialized, just refresh structure
             self.refresh_structure()
             return

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Instructions
        lbl_inst = QLabel(
            "Map 'Output Fields' to columns in each file. These fields will be compared across all files."
        )
        lbl_inst.setStyleSheet("color: #AAAAAA; margin-bottom: 5px;")
        layout.addWidget(lbl_inst)
        
        # Table
        self.table = SmartTableWidget(self)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Styles
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.setStyleSheet("""
            QTableWidget { gridline-color: #444; }
            QComboBox, QLineEdit {
                min-height: 25px; padding: 2px 5px; margin: 2px;
                border: 1px solid #555; border-radius: 3px;
                background-color: #2b2b2b; color: #e0e0e0;
            }
            QComboBox::drop-down { border: none; }
            QHeaderView::section {
                background-color: #333; padding: 5px; border: 1px solid #444;
            }
        """)
        
        # Actions
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("+ Add Field")
        self.btn_add.clicked.connect(self.add_row)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_remove = QPushButton("− Remove Selected")
        self.btn_remove.clicked.connect(self.remove_row)
        btn_layout.addWidget(self.btn_remove)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.refresh_structure()

    def refresh_structure(self):
        """Re-builds table headers based on current ref_files."""
        self.table.clear() 
        self.table.setRowCount(0)
        
        self.file_headers = [os.path.basename(f) for f in self.ref_files]
        headers = self.file_headers + ["Data Type", "Output Field Name"]
        
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Restore schema logic
        if self.schema:
            for field in self.schema:
                self.load_row(field)
        else:
            self.add_row()

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 1. File Columns (0 to N-1)
        for i, ref_path in enumerate(self.ref_files):
            combo_col = QComboBox()
            combo_col.addItem("") 
            cols = self.ref_columns.get(ref_path, [])
            combo_col.addItems(cols)
            # Auto-fill name on first col change
            if i == 0:
                combo_col.currentTextChanged.connect(lambda text, r=row: self.auto_fill_name(r, text))
            self.table.setCellWidget(row, i, combo_col)
            
        # 2. Data Type (N)
        col_type_idx = len(self.ref_files)
        combo_type = QComboBox()
        combo_type.addItems(["Text", "Number", "Currency", "Date"])
        self.table.setCellWidget(row, col_type_idx, combo_type)
        
        # 3. Output Name (N+1)
        col_name_idx = col_type_idx + 1
        txt_name = QLineEdit()
        txt_name.setPlaceholderText("Result Column Name")
        self.table.setCellWidget(row, col_name_idx, txt_name)

    def load_row(self, data):
        self.add_row()
        row = self.table.rowCount() - 1
        
        mappings = data.get("mappings", {})
        for i, ref_path in enumerate(self.ref_files):
            target_col = mappings.get(ref_path, "")
            combo = self.table.cellWidget(row, i)
            if combo:
                idx = combo.findText(target_col)
                if idx >= 0: combo.setCurrentIndex(idx)
        
        col_type_idx = len(self.ref_files)
        dtype = data.get("type", "Text")
        combo_type = self.table.cellWidget(row, col_type_idx)
        if combo_type:
             idx = combo_type.findText(dtype)
             if idx >= 0: combo_type.setCurrentIndex(idx)
             
        col_name_idx = col_type_idx + 1
        name = data.get("name", "")
        txt_name = self.table.cellWidget(row, col_name_idx)
        if txt_name:
            txt_name.setText(name)

    def auto_fill_name(self, row, text):
        if not text: return
        col_name_idx = len(self.ref_files) + 1
        txt_name = self.table.cellWidget(row, col_name_idx)
        if txt_name and not txt_name.text().strip():
            txt_name.setText(text)

    def remove_row(self):
        current = self.table.currentRow()
        if current >= 0:
            self.table.removeRow(current)

    def load_schema(self, schema_data):
        """Clears current table and loads the provided schema."""
        self.schema = schema_data
        # Clear existing rows
        self.table.setRowCount(0)
        
        if self.schema:
            for field in self.schema:
                self.load_row(field)
        else:
            self.add_row() # Default empty row

    def get_schema(self):
        """Extracts the configured schema from the table."""
        schema = []
        rows = self.table.rowCount()
        col_type_idx = len(self.ref_files)
        col_name_idx = len(self.ref_files) + 1
        
        for r in range(rows):
            name_widget = self.table.cellWidget(r, col_name_idx)
            type_widget = self.table.cellWidget(r, col_type_idx)
            
            name = name_widget.text().strip()
            # Auto-name fallback
            if not name:
                for i in range(len(self.ref_files)):
                    w = self.table.cellWidget(r, i)
                    if w and w.currentText():
                       name = w.currentText()
                       name_widget.setText(name)
                       break
                if not name: continue # Skip empty
            
            dtype = type_widget.currentText()
            mappings = {}
            has_mapping = False
            for i, ref_path in enumerate(self.ref_files):
                col_widget = self.table.cellWidget(r, i)
                val = col_widget.currentText()
                if val:
                    mappings[ref_path] = val
                    has_mapping = True
            
            if has_mapping:
                schema.append({
                    "name": name,
                    "type": dtype,
                    "mappings": mappings
                })
        return schema

class ComparisonSchemaDialog(QDialog):
    """Refactored to use SchemaConfigWidget"""
    def __init__(self, ref_files, ref_columns, initial_schema=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Comparison Schema")
        self.resize(1000, 600)
        
        layout = QVBoxLayout(self)
        
        # Create Widget
        self.widget = SchemaConfigWidget(ref_files, ref_columns, initial_schema)
        layout.addWidget(self.widget)
        
        # Dialog Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton("Save Schema")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self.save)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)

    def save(self):
        self.schema = self.widget.get_schema()
        self.accept()
