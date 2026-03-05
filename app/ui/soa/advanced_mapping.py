
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QListWidget, QListWidgetItem, QFrame, QSplitter, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QToolTip, QGroupBox
)
from PySide6.QtCore import Qt, Signal
import os
import json

# Template storage path
TEMPLATES_DIR = os.path.join(os.path.expanduser("~"), ".apeiron")
TEMPLATES_FILE = os.path.join(TEMPLATES_DIR, "mapping_templates_soa.json")

# Import the new SchemaConfigWidget
from app.ui.schema_config import SchemaConfigWidget

class SOAAdvancedMappingScreen(QWidget):
    """
    Advanced Mapping Screen for SOA Reconciliation.
    Uses the table-based SchemaConfigWidget for comparing Carrier to Carrier, etc.
    """
    go_back = Signal()
    run_reco = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_file = None
        self.ref_files = []
        self.base_columns = [] 
        self.ref_columns = {} # {ref_path: [columns]}
        self.match_keys = {}
        self.date_col = None
        self.amount_col = None

        # Load Template Logic
        self.templates = self._get_templates()
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Header
        self.lbl_header = QLabel("Advanced Mapping: SOA Reconciliation")
        self.lbl_header.setObjectName("HeaderTitle")
        layout.addWidget(self.lbl_header)

        # Main Content: Splitter
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel: Schema Configuration
        self.schema_widget = SchemaConfigWidget(self.ref_files, self.ref_columns)
        self.splitter.addWidget(self.schema_widget)
        
        # Right Panel: Templates & Settings
        right_panel = QFrame()
        right_panel.setObjectName("PanelRules")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 10, 8, 10)
        right_layout.setSpacing(6)
        
        lbl_rules = QLabel("Rules & Templates")
        lbl_rules.setObjectName("HeaderRules")
        right_layout.addWidget(lbl_rules)
        
        # Match Type
        match_group = QGroupBox("Match Configuration")
        match_group_layout = QVBoxLayout(match_group)
        self.chk_fuzzy = QCheckBox("Enable Partial/Fuzzy Match")
        match_group_layout.addWidget(self.chk_fuzzy)
        right_layout.addWidget(match_group)
        
        # Save Template
        self.btn_save_template_main = QPushButton("Save Configuration as Template")
        self.btn_save_template_main.setMinimumHeight(35)
        self.btn_save_template_main.setObjectName("SecondaryButton") # Use QSS
        self.btn_save_template_main.clicked.connect(self.save_template)
        right_layout.addWidget(self.btn_save_template_main)

        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("SubTitle")
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 12px;")
        right_layout.addWidget(self.lbl_status)

        # Templates List
        right_layout.addWidget(QLabel("Saved Templates:"))
        self.list_templates = QListWidget()
        self.list_templates.setObjectName("CompactList")
        self.list_templates.setMinimumHeight(100)
        right_layout.addWidget(self.list_templates, 1)
        
        tmpl_btn_layout = QHBoxLayout()
        self.btn_load_template = QPushButton("Load Template")
        self.btn_load_template.clicked.connect(self.load_template)
        tmpl_btn_layout.addWidget(self.btn_load_template)
        
        self.btn_delete_template = QPushButton("🗑")
        self.btn_delete_template.setMaximumWidth(30)
        self.btn_delete_template.clicked.connect(self.delete_template)
        tmpl_btn_layout.addWidget(self.btn_delete_template)
        right_layout.addLayout(tmpl_btn_layout)

        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([700, 300])
        layout.addWidget(self.splitter, 1)

        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_run = QPushButton("Run Advanced Reconciliation")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self.on_run)
        
        footer.addWidget(self.btn_back)
        footer.addStretch()
        footer.addWidget(self.btn_run)
        layout.addLayout(footer)

    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict, match_keys, date_col, amount_col, ref_custom_names=None):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        self.match_keys = match_keys
        self.date_col = date_col
        self.amount_col = amount_col
        self.ref_custom_names = ref_custom_names or {}

        # Prepare all columns mapping (Base + Refs)
        all_columns = {self.base_file: self.base_columns}
        all_columns.update(self.ref_columns)

        # Update Schema Widget
        self.schema_widget.ref_files = [self.base_file] + self.ref_files
        self.schema_widget.ref_columns = all_columns
        self.schema_widget.match_keys = self.match_keys
        
        # Pass name map to schema widget
        path_to_name_map = self.ref_custom_names.copy()
        path_to_name_map[self.base_file] = "SOA" # Ensure base is labeled
        self.schema_widget.path_to_name_map = path_to_name_map
        
        self.schema_widget.init_ui()

        self._load_templates_list()

    def on_run(self):
        schema = self.schema_widget.get_schema()
        if not schema:
            QMessageBox.warning(self, "No Schema", "Please add at least one output field.")
            return

        config = {
            "rules": {}, 
            "date_col": self.date_col,
            "amount_col": self.amount_col,
            "master_match_col": self.match_keys.get(self.base_file),
            "schema_config": schema,
            "match_keys": self.match_keys,
            "base_file": self.base_file,
            "ref_custom_names": self.ref_custom_names,
            "match_type": "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
        }
        self.run_reco.emit(config)

    # Template Methods (Simplified for brevity)
    def _get_templates(self):
        try:
            if os.path.exists(TEMPLATES_FILE):
                with open(TEMPLATES_FILE, 'r') as f: return json.load(f)
        except: pass
        return {}

    def _save_templates(self, templates):
        try:
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
            with open(TEMPLATES_FILE, 'w') as f: json.dump(templates, f, indent=2)
        except: pass

    def _load_templates_list(self):
        self.list_templates.clear()
        templates = self._get_templates()
        for name in templates:
            self.list_templates.addItem(name)

    def save_template(self):
        name, ok = QInputDialog.getText(self, "Save Template", "Template Name:")
        if ok and name.strip():
            templates = self._get_templates()
            templates[name.strip()] = {"schema_config": self.schema_widget.get_schema()}
            self._save_templates(templates)
            self._load_templates_list()

    def load_template(self):
        selected = self.list_templates.currentItem()
        if selected:
            templates = self._get_templates()
            tmpl = templates.get(selected.text())
            if tmpl and "schema_config" in tmpl:
                self.schema_widget.load_schema(tmpl["schema_config"])

    def delete_template(self):
        selected = self.list_templates.currentItem()
        if selected:
            templates = self._get_templates()
            if selected.text() in templates:
                del templates[selected.text()]
                self._save_templates(templates)
                self._load_templates_list()
