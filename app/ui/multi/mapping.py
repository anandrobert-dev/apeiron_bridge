
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
TEMPLATES_FILE = os.path.join(TEMPLATES_DIR, "mapping_templates.json")

# Import the new SchemaConfigWidget
from app.ui.schema_config import SchemaConfigWidget


class MultiMappingScreen(QWidget):
    """
    Screen for mapping columns for Multi-File Comparison.
    Uses a Schema-based approach where users define output fields and map them to file columns.
    Supports saving/loading mapping templates for reuse.
    """
    go_back = Signal()
    run_reco = Signal(dict) # mapping configuration

    def __init__(self, parent=None):
        super().__init__(parent)
        self.base_file = None
        self.ref_files = []
        self.base_columns = [] 
        self.ref_columns = {} # {ref_path: [columns]}
        self.schema_config = [] # For Multi-File Comparison
        self.mapping_rules = {} # Still needed for compatibility with engine, but derived from schema
        
        # Load Template Logic
        self.templates = self._get_templates()
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Header
        self.lbl_header = QLabel("Map Columns: Multi-File Comparison")
        self.lbl_header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px 0;")
        layout.addWidget(self.lbl_header)

        # Main Content: Splitter for 3-panel layout
        self.splitter = QSplitter(Qt.Horizontal)
        splitter = self.splitter # Keep local var for existing code compatibility
        
        # ============== Main Panel: Schema Configuration ==============
        # In Multi-File mode, this takes the place of Left/Center panels
        self.schema_widget = SchemaConfigWidget(self.ref_files, self.ref_columns)
        splitter.addWidget(self.schema_widget)
        
        # ============== Right Panel: Rules & Templates ==============
        right_panel = QFrame()
        right_panel.setObjectName("PanelRules")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 10, 8, 10)
        right_layout.setSpacing(6)
        
        lbl_rules = QLabel("Rules & Templates")
        lbl_rules.setObjectName("HeaderRules")
        right_layout.addWidget(lbl_rules)
        
        # --- Match Type ---
        match_group = QGroupBox("Match Configuration")
        match_group_layout = QVBoxLayout(match_group)
        
        self.chk_fuzzy = QCheckBox("Enable Partial/Fuzzy Match")
        self.chk_fuzzy.setToolTip(
            "When ENABLED: Matches partial text (e.g., 'INV-123' matches 'INV-12345').\\n"
            "Useful when invoice numbers have extra characters or prefixes.\\n\\n"
            "When DISABLED (default): Only exact matches are used.\\n"
            "Recommended for most reconciliations."
        )
        match_group_layout.addWidget(self.chk_fuzzy)
        
        # Fuzzy match hint
        fuzzy_hint = QLabel("ℹ️ Use exact match unless invoice formats differ between files.")
        fuzzy_hint.setStyleSheet("color: #888; font-size: 11px;")
        fuzzy_hint.setWordWrap(True)
        match_group_layout.addWidget(fuzzy_hint)
        
        right_layout.addWidget(match_group)
        
        # --- Save Template Button (Prominent) ---
        self.btn_save_template_main = QPushButton("Save Configuration as Template")
        self.btn_save_template_main.setMinimumHeight(40)
        self.btn_save_template_main.setStyleSheet("""
            QPushButton {
                background-color: #00897B;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00796B; }
        """)

        self.btn_save_template_main.clicked.connect(self.save_template)
        right_layout.addWidget(self.btn_save_template_main)

        # --- Current Session Rules (Removed as schema widget handles mapping) ---
        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        self.lbl_status.setWordWrap(True)
        right_layout.addWidget(self.lbl_status)

        # --- Templates Section (Adjustable) ---
        right_layout.addWidget(QLabel("Saved Templates:"))
        self.list_templates = QListWidget()
        self.list_templates.setObjectName("CompactList")
        self.list_templates.setMinimumHeight(60)
        right_layout.addWidget(self.list_templates, 1) # Stretch factor 1
        
        # Template buttons
        tmpl_btn_layout = QHBoxLayout()
        
        self.btn_save_template = QPushButton("Save Tmplt")
        self.btn_save_template.setMinimumHeight(25)
        self.btn_save_template.clicked.connect(self.save_template)
        tmpl_btn_layout.addWidget(self.btn_save_template)
        
        self.btn_load_template = QPushButton("Load Tmplt")
        self.btn_load_template.setMinimumHeight(25)
        self.btn_load_template.clicked.connect(self.load_template)
        tmpl_btn_layout.addWidget(self.btn_load_template)
        
        self.btn_delete_template = QPushButton("🗑")
        self.btn_delete_template.setMaximumWidth(30)
        self.btn_delete_template.setMinimumHeight(25)
        self.btn_delete_template.clicked.connect(self.delete_template)
        tmpl_btn_layout.addWidget(self.btn_delete_template)
        
        right_layout.addLayout(tmpl_btn_layout)

        splitter.addWidget(right_panel)
        
        # Set reasonable splitter proportions
        splitter.setSizes([700, 300]) # Schema takes most space, Rules take some
        layout.addWidget(splitter, 1)

        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_run = QPushButton("Run Comparison")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_run.setMinimumHeight(40)
        self.btn_run.clicked.connect(self.on_run)
        
        footer.addWidget(self.btn_back)
        footer.addStretch()
        footer.addWidget(self.btn_run)
        layout.addLayout(footer)
        
    # set_mode removed as this class is now strictly MULTI

    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict, match_keys=None):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        self.match_keys = match_keys or {}

        # Update Schema Widget with new data
        if hasattr(self, 'schema_widget'):
            self.schema_widget.ref_files = self.ref_files
            self.schema_widget.ref_columns = self.ref_columns
            self.schema_widget.match_keys = self.match_keys
            self.schema_widget.init_ui() # Re-init UI to reflect new columns

        self.lbl_status.setText("")
        
        # Refresh templates list
        self._load_templates_list()

        # Re-apply mode visibility logic to ensure splitter sizes are correct
        self.splitter.setSizes([700, 300])


    def _find_best_column_match(self, columns, keywords):
        """Find the column index that best matches the keywords."""
        columns_lower = [c.lower().strip() for c in columns]
        
        # Priority 1: Exact match
        for kw in keywords:
            for i, col_l in enumerate(columns_lower):
                if col_l == kw.lower():
                    return i
        
        # Priority 2: Substring match
        for kw in keywords:
            for i, col_l in enumerate(columns_lower):
                if kw.lower() in col_l:
                    return i
        
        return -1

    # auto_configure_all_refs, on_ref_change, load_ref_ui removed as they are legacy SOA components
    # (SchemaWidget handles its own column mapping)
    
    # save_current_mapping, update_rules_list, add_rule, on_schema_config removed as they are legacy SOA components

    def on_run(self):
        """Gather schema and emit run signal."""
        
        # Strict Multi-File Config
        config = {
            "rules": {}, # Legacy rules logic bypassed
            "date_col": None,
            "amount_col": None,
            "master_match_col": None, # Will be taken from match_keys in engine
            "schema_config": self.schema_widget.get_schema(),
            "match_keys": getattr(self, 'match_keys', {})
        }
        
        # Validation: check if schema has fields and match keys are present
        if not config["schema_config"]:
             QMessageBox.warning(self, "No Schema", "Please add at least one output field in the Schema.")
             return

        print(f"[MultiMappingScreen] Running in MULTI mode")
        print(f"[MultiMappingScreen] Config: {config}")
        self.run_reco.emit(config)

    # ======================== Template Persistence ========================

    def _get_templates(self):
        """Load all templates from disk."""
        try:
            if os.path.exists(TEMPLATES_FILE):
                with open(TEMPLATES_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[MappingScreen] Error loading templates: {e}")
        return {}

    def _save_templates(self, templates):
        """Save all templates to disk."""
        try:
            os.makedirs(TEMPLATES_DIR, exist_ok=True)
            with open(TEMPLATES_FILE, 'w') as f:
                json.dump(templates, f, indent=2)
        except Exception as e:
            print(f"[MappingScreen] Error saving templates: {e}")

    def _load_templates_list(self):
        """Refresh the templates list widget from disk."""
        self.list_templates.clear()
        templates = self._get_templates()
        for name, tmpl in templates.items():
            # Show template name + brief info
            schema = tmpl.get("schema_config", [])
            if schema:
                field_count = len(schema)
                display = f"{name}  ({field_count} field{'s' if field_count != 1 else ''})"
            else:
                ref_count = len(tmpl.get("rules", {}))
                display = f"{name}  ({ref_count} ref{'s' if ref_count != 1 else ''})"
            
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, name)
            self.list_templates.addItem(item)

    def save_template(self):
        """Save current mapping rules as a named template."""
        schema = self.schema_widget.get_schema() if hasattr(self, 'schema_widget') else []

        if not schema:
            QMessageBox.warning(self, "No Rules to Save", 
                "Please configure at least one output field in the Schema before saving a template.")
            return

        name, ok = QInputDialog.getText(self, "Save Template", 
            "Enter a name for this template:\n(e.g., 'Monthly Multi-File Config')")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        template = {
            "schema_config": schema,
            "match_type": "fuzzy" if getattr(self, 'chk_fuzzy', None) and self.chk_fuzzy.isChecked() else "exact"
        }
        
        templates = self._get_templates()
        templates[name] = template
        self._save_templates(templates)
        self._load_templates_list()
        
        self.lbl_status.setText(f"✔ Template '{name}' saved!")
        print(f"[MultiMappingScreen] Template saved: {name}")

    def load_template(self):
        """Load a saved template and apply it to the schema configuration."""
        selected = self.list_templates.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Template Selected", "Please select a template from the list.")
            return
        
        tmpl_name = selected.data(Qt.UserRole)
        templates = self._get_templates()
        tmpl = templates.get(tmpl_name)
        
        if not tmpl:
            QMessageBox.warning(self, "Template Not Found", f"Template '{tmpl_name}' was not found.")
            return

        # Apply match type switch
        if "match_type" in tmpl and hasattr(self, 'chk_fuzzy'):
            self.chk_fuzzy.setChecked(tmpl["match_type"] == "fuzzy")
        
        schema_data = tmpl.get("schema_config", [])
        if schema_data and hasattr(self, 'schema_widget'):
            if hasattr(self.schema_widget, 'load_schema'):
                self.schema_widget.load_schema(schema_data)
            self.lbl_status.setText(f"✔ Template '{tmpl_name}' loaded! ({len(schema_data)} fields)")
            print(f"[MultiMappingScreen] Template loaded: {tmpl_name}, applied {len(schema_data)} fields")
        elif tmpl.get("rules"):
            self.lbl_status.setText(f"⚠ Template '{tmpl_name}' is from an older version and cannot be fully loaded in Multi-File mode.")
            self.lbl_status.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12px;")

    def delete_template(self):
        """Delete the selected template."""
        selected = self.list_templates.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Template Selected", "Please select a template to delete.")
            return
        
        tmpl_name = selected.data(Qt.UserRole)
        
        reply = QMessageBox.question(self, "Delete Template", 
            f"Are you sure you want to delete template '{tmpl_name}'?",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            templates = self._get_templates()
            if tmpl_name in templates:
                del templates[tmpl_name]
                self._save_templates(templates)
                self._load_templates_list()
                self.lbl_status.setText(f"Template '{tmpl_name}' deleted.")
