
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QListWidget, QListWidgetItem, QFrame, QSplitter, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import os

class MappingScreen(QWidget):
    """
    Screen for mapping columns between Base (SOA) and Reference files.
    Matches the original Oi360 workflow:
      - SOA: select match column, date column, amount column
      - Each Ref: select match column (dropdown) + return columns (multi-select)
    """
    go_back = Signal()
    run_reco = Signal(dict) # mapping configuration

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_file = None
        self.ref_files = []
        self.base_columns = [] 
        self.ref_columns = {} # {ref_path: [cols]}

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Header
        header = QLabel("Map Columns & Configure Rules")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px 0;")
        layout.addWidget(header)

        # Main Content: Splitter for 3-panel layout
        splitter = QSplitter(Qt.Horizontal)
        
        # ============== Left Panel: Base File (SOA) Info ==============
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(4)
        
        left_layout.addWidget(QLabel("Base File Columns (SOA)"))
        self.list_base_cols = QListWidget()
        left_layout.addWidget(self.list_base_cols)
        
        # SOA-specific column selectors
        left_layout.addWidget(QLabel("Select Date Column (for Age Bucket):"))
        self.combo_date_col = QComboBox()
        left_layout.addWidget(self.combo_date_col)
        
        left_layout.addWidget(QLabel("Select Amount Column (for Mismatch):"))
        self.combo_amount_col = QComboBox()
        left_layout.addWidget(self.combo_amount_col)
        
        splitter.addWidget(left_panel)

        # ============== Center Panel: Reference File Mapping ==============
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(5, 5, 5, 5)
        center_layout.setSpacing(4)
        
        # Select which ref file to configure
        center_layout.addWidget(QLabel("Select Reference File to Map:"))
        self.combo_current_ref = QComboBox()
        self.combo_current_ref.currentIndexChanged.connect(self.on_ref_change)
        center_layout.addWidget(self.combo_current_ref)

        # Match column dropdown (single select - which col to match on)
        center_layout.addWidget(QLabel("Match Column (match against SOA):"))
        self.combo_ref_match = QComboBox()
        center_layout.addWidget(self.combo_ref_match)

        # Return columns list (multi-select - which cols to include in output)
        center_layout.addWidget(QLabel("Return Columns (select columns to include):"))
        self.list_ref_cols = QListWidget()
        self.list_ref_cols.setSelectionMode(QListWidget.MultiSelection)
        center_layout.addWidget(self.list_ref_cols)
        
        splitter.addWidget(center_panel)

        # ============== Right Panel: Rules & Actions ==============
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(4)
        
        right_layout.addWidget(QLabel("Match Configuration"))
        
        self.chk_fuzzy = QCheckBox("Enable Partial/Fuzzy Match")
        right_layout.addWidget(self.chk_fuzzy)
        
        self.btn_add_rule = QPushButton("💾 Save Ref Mapping")
        self.btn_add_rule.setObjectName("SecondaryButton")
        self.btn_add_rule.setMinimumHeight(40)
        self.btn_add_rule.clicked.connect(self.add_rule)
        right_layout.addWidget(self.btn_add_rule)

        right_layout.addWidget(QLabel("Saved Mapping Rules:"))
        self.list_rules = QListWidget()
        self.list_rules.setStyleSheet("""
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #555;
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
        """)
        right_layout.addWidget(self.list_rules)
        
        # Status label for feedback
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        self.lbl_status.setWordWrap(True)
        right_layout.addWidget(self.lbl_status)

        splitter.addWidget(right_panel)
        
        # Set reasonable splitter proportions
        splitter.setSizes([250, 350, 300])
        layout.addWidget(splitter, 1)  # stretch=1 so it takes available space

        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_run = QPushButton("Run Reconciliation")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self.on_run)
        
        footer.addWidget(self.btn_back)
        footer.addStretch()
        footer.addWidget(self.btn_run)
        layout.addLayout(footer)
        
        # Internal storage for rules: {ref_path: {match_col, return_cols, match_type}}
        self.mapping_rules = {}

    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        
        # Populate Base columns list (display only)
        self.list_base_cols.clear()
        self.list_base_cols.addItems(self.base_columns)
        
        # Populate Date and Amount dropdowns
        self.combo_date_col.clear()
        self.combo_date_col.addItems(self.base_columns)
        
        self.combo_amount_col.clear()
        self.combo_amount_col.addItems(self.base_columns)
        
        # --- Auto-detect Date column ---
        date_keywords = ['date', 'dt', 'dated', 'invoice date', 'inv date', 'receive date']
        best_date_idx = self._find_best_column_match(self.base_columns, date_keywords)
        if best_date_idx >= 0:
            self.combo_date_col.setCurrentIndex(best_date_idx)
        
        # --- Auto-detect Amount column ---
        amount_keywords = ['amount', 'amt', 'open amount', 'invoice amount', 'total', 'value', 'balance']
        best_amt_idx = self._find_best_column_match(self.base_columns, amount_keywords)
        if best_amt_idx >= 0:
            self.combo_amount_col.setCurrentIndex(best_amt_idx)
        
        # Populate ref file selector
        self.combo_current_ref.clear()
        for ref in self.ref_files:
            self.combo_current_ref.addItem(os.path.basename(ref), ref)

        self.on_ref_change()
        self.list_rules.clear()
        self.mapping_rules = {}
        self.lbl_status.setText("")

    def _find_best_column_match(self, columns, keywords):
        """Find the column index that best matches the keywords.
        Tries exact substring match first, then partial match."""
        columns_lower = [c.lower().strip() for c in columns]
        
        # Priority 1: Exact match (column name IS the keyword)
        for kw in keywords:
            for i, col_l in enumerate(columns_lower):
                if col_l == kw.lower():
                    return i
        
        # Priority 2: Keyword is a substring of column name
        for kw in keywords:
            for i, col_l in enumerate(columns_lower):
                if kw.lower() in col_l:
                    return i
        
        return -1

    def on_ref_change(self):
        """When user switches the ref file dropdown, update the match column and return column lists."""
        current_ref = self.combo_current_ref.currentData()
        if current_ref and current_ref in self.ref_columns:
            cols = self.ref_columns[current_ref]
            
            # Populate match column dropdown
            self.combo_ref_match.clear()
            self.combo_ref_match.addItems(cols)
            
            # Populate return columns list (multi-select)
            self.list_ref_cols.clear()
            self.list_ref_cols.addItems(cols)
            
            # Restore previous selections if rule exists for this ref
            if current_ref in self.mapping_rules:
                rule = self.mapping_rules[current_ref]
                # Restore match column
                idx = self.combo_ref_match.findText(rule["match_col"])
                if idx >= 0:
                    self.combo_ref_match.setCurrentIndex(idx)
                # Restore return column selections
                for i in range(self.list_ref_cols.count()):
                    item = self.list_ref_cols.item(i)
                    if item.text() in rule.get("return_cols", []):
                        item.setSelected(True)
                self.lbl_status.setText(f"✔ Mapping exists for this file")
            else:
                self.lbl_status.setText("")

    def add_rule(self):
        """Save the mapping rule for the currently selected reference file."""
        current_ref = self.combo_current_ref.currentData()
        ref_display = self.combo_current_ref.currentText()
        
        if not current_ref:
            QMessageBox.warning(self, "No Reference File", "Please select a reference file.")
            return

        match_col = self.combo_ref_match.currentText()
        if not match_col:
            QMessageBox.warning(self, "No Match Column", "Please select a match column for this reference file.")
            return
        
        # Get selected return columns
        selected_returns = [item.text() for item in self.list_ref_cols.selectedItems()]
        if not selected_returns:
            QMessageBox.warning(self, "No Return Columns", 
                "Please select at least one return column.\n\n"
                "These are the columns from the reference file that will be included in the output.")
            return

        match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
        
        # Store rule keyed by full ref path
        self.mapping_rules[current_ref] = {
            "match_col": match_col,
            "return_cols": selected_returns,
            "match_type": match_type
        }
        
        # Update display list
        returns_preview = ', '.join(selected_returns[:3])
        if len(selected_returns) > 3:
            returns_preview += f" +{len(selected_returns)-3} more"
        display_text = f"✔ {ref_display}: Match '{match_col}' → [{returns_preview}] ({match_type})"
        
        # Remove existing entry for this ref if any
        for i in range(self.list_rules.count()):
            if self.list_rules.item(i).data(Qt.UserRole) == current_ref:
                self.list_rules.takeItem(i)
                break
        
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, current_ref)
        self.list_rules.addItem(item)
        
        # Show feedback
        self.lbl_status.setText(f"✔ Mapping saved for {ref_display}")
        print(f"[MappingScreen] Rule saved: {display_text}")

    def on_run(self):
        """Gather all mapping rules and emit run signal."""
        # Auto-save current ref mapping if not yet saved
        current_ref = self.combo_current_ref.currentData()
        if current_ref and current_ref not in self.mapping_rules:
            # Try to auto-capture
            match_col = self.combo_ref_match.currentText()
            selected_returns = [item.text() for item in self.list_ref_cols.selectedItems()]
            if match_col and selected_returns:
                match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
                self.mapping_rules[current_ref] = {
                    "match_col": match_col,
                    "return_cols": selected_returns,
                    "match_type": match_type
                }
                print(f"[MappingScreen] Auto-captured rule for {self.combo_current_ref.currentText()}")

        if not self.mapping_rules:
            QMessageBox.warning(self, "No Mapping Rules", 
                "Please configure at least one reference file mapping.\n\n"
                "Select a match column and return columns for each reference file, "
                "then click 'Save Ref Mapping'.")
            return
            
        config = {
            "rules": self.mapping_rules,
            "date_col": self.combo_date_col.currentText(),
            "amount_col": self.combo_amount_col.currentText()
        }
        
        print(f"[MappingScreen] Running with config: date_col={config['date_col']}, amount_col={config['amount_col']}")
        print(f"[MappingScreen] Rules: {self.mapping_rules}")
        self.run_reco.emit(config)
