
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QListWidget, QListWidgetItem, QFrame, QSplitter, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal

class MappingScreen(QWidget):
    """
    Screen for mapping columns between Base and Reference files.
    """
    go_back = Signal()
    run_reco = Signal(dict) # mapping configuration

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_file = None
        self.ref_files = []
        # Store DataFrames or at least columns metadata here
        self.base_columns = [] 
        self.ref_columns = {} # {ref_path: [cols]}

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Map Columns & Configure Rules")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        # Main Content: Splitter for Refs vs Configuration
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel: Base File Info
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Base File Columns (SOA)"))
        self.list_base_cols = QListWidget()
        left_layout.addWidget(self.list_base_cols)
        
        # --- New inputs for Oi360 Logic ---
        left_layout.addWidget(QLabel("Select Date Column (for Age Bucket):"))
        self.combo_date_col = QComboBox()
        left_layout.addWidget(self.combo_date_col)
        
        left_layout.addWidget(QLabel("Select Amount Column (for Mismatch):"))
        self.combo_amount_col = QComboBox()
        left_layout.addWidget(self.combo_amount_col)
        
        splitter.addWidget(left_panel)

        # Center Panel: Mapping Area
        center_panel = QFrame()
        center_layout = QVBoxLayout(center_panel)
        
        # Select Reference File to Map
        center_layout.addWidget(QLabel("Select Reference File to Map:"))
        self.combo_current_ref = QComboBox()
        self.combo_current_ref.currentIndexChanged.connect(self.on_ref_change)
        center_layout.addWidget(self.combo_current_ref)

        center_layout.addWidget(QLabel("Reference File Columns"))
        self.list_ref_cols = QListWidget()
        center_layout.addWidget(self.list_ref_cols)
        
        splitter.addWidget(center_panel)

        # Right Panel: Rules & Actions
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(QLabel("Match Configuration"))
        
        self.chk_fuzzy = QCheckBox("Enable Partial/Fuzzy Match")
        right_layout.addWidget(self.chk_fuzzy)
        
        right_layout.addStretch()
        
        self.btn_add_rule = QPushButton("Add Mapping Rule")
        self.btn_add_rule.setObjectName("SecondaryButton")
        self.btn_add_rule.clicked.connect(self.add_rule)
        right_layout.addWidget(self.btn_add_rule)

        self.list_rules = QListWidget() # Display added rules
        right_layout.addWidget(self.list_rules)

        splitter.addWidget(right_panel)
        layout.addWidget(splitter)

        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_run = QPushButton("Run Reconciliation")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_run.clicked.connect(self.on_run)
        
        footer.addWidget(self.btn_back)
        footer.addStretch()
        footer.addWidget(self.btn_run)
        layout.addLayout(footer)
        
        # Internal storage for rules
        self.mapping_rules = {} # {ref_name: {base_col, ref_col, match_type}}

    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        
        # Populate UI
        self.list_base_cols.clear()
        self.list_base_cols.addItems(self.base_columns)
        
        self.combo_date_col.clear()
        self.combo_date_col.addItems(self.base_columns)
        
        self.combo_amount_col.clear()
        self.combo_amount_col.addItems(self.base_columns)
        
        self.combo_current_ref.clear()
        for ref in self.ref_files:
            self.combo_current_ref.addItem(ref) # Use basename ideally

        self.on_ref_change()
        self.list_rules.clear()
        self.mapping_rules = {}

    def on_ref_change(self):
        current_ref = self.combo_current_ref.currentText()
        if current_ref in self.ref_columns:
            cols = self.ref_columns[current_ref]
            self.list_ref_cols.clear()
            self.list_ref_cols.addItems(cols)

    def add_rule(self):
        # Get selections
        base_item = self.list_base_cols.currentItem()
        ref_item = self.list_ref_cols.currentItem()
        current_ref = self.combo_current_ref.currentText()
        
        if not base_item or not ref_item or not current_ref:
            return # Show error?

        base_col = base_item.text()
        ref_col = ref_item.text()
        match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
        
        # Store rule
        self.mapping_rules[current_ref] = {
            "base_col": base_col,
            "ref_col": ref_col,
            "match_type": match_type
        }
        
        # Add to list
        display_text = f"{current_ref}: Map '{base_col}' -> '{ref_col}' ({match_type})"
        # Remove existing if any for this ref (MVP restriction)
        for i in range(self.list_rules.count()):
            if self.list_rules.item(i).text().startswith(f"{current_ref}:"):
                self.list_rules.takeItem(i)
                break
                
        self.list_rules.addItem(display_text)

    def on_run(self):
        if not self.mapping_rules:
            # warn user
            return
            
        # Gather extra configs
        config = {
            "rules": self.mapping_rules,
            "date_col": self.combo_date_col.currentText(),
            "amount_col": self.combo_amount_col.currentText()
        }
        self.run_reco.emit(config)
