
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


class SOAMappingScreen(QWidget):
    """
    Screen for mapping columns for SOA Reconciliation matches.
    Matches the original Oi360 workflow:
      - SOA: select match column, date column, amount column
      - Each Ref: select match column (dropdown) + return columns (multi-select)
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
        self.mapping_rules = {} # {ref_path: {match_col, return_cols, match_type}}
        
        # Load Template Logic
        self.templates = self._get_templates()
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(5)
        
        # Header
        self.lbl_header = QLabel("Map Columns & Configure Rules")
        self.lbl_header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px 0;")
        layout.addWidget(self.lbl_header)

        # Main Content: Splitter for 3-panel layout
        self.splitter = QSplitter(Qt.Horizontal)
        splitter = self.splitter # Keep local var for existing code compatibility
        
        # ============== Left Panel: Base File (SOA) Info ==============
        left_panel = QFrame()
        left_panel.setObjectName("PanelBase")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 10, 8, 10)
        left_layout.setSpacing(6)
        
        self.lbl_base_cols = QLabel("Base File Columns (SOA)")
        self.lbl_base_cols.setObjectName("HeaderBase")
        left_layout.addWidget(self.lbl_base_cols)

        self.list_base_cols = QListWidget()
        self.list_base_cols.setObjectName("CompactList")
        left_layout.addWidget(self.list_base_cols)
        
        left_layout.addWidget(self.list_base_cols)
        
        # --- SOA Inputs (Date/Amount) ---
        # These are now passed from File Selection, so we disable them or make them read-only
        self.lbl_date_input = QLabel("Selected Date Column (Read-Only):")
        left_layout.addWidget(self.lbl_date_input)
        self.combo_date_col = QComboBox()
        self.combo_date_col.setEnabled(False) # Read-only
        left_layout.addWidget(self.combo_date_col)
        
        self.lbl_amount_input = QLabel("Selected Amount Column (Read-Only):")
        left_layout.addWidget(self.lbl_amount_input)
        self.combo_amount_col = QComboBox()
        self.combo_amount_col.setEnabled(False) # Read-only
        left_layout.addWidget(self.combo_amount_col)

        # --- MULTI Inputs (Master Match Key) ---
        self.lbl_master_match = QLabel("Select Master Match Key:")
        self.lbl_master_match.setVisible(False)
        left_layout.addWidget(self.lbl_master_match)
        self.combo_base_match = QComboBox()
        self.combo_base_match.setVisible(False)
        left_layout.addWidget(self.combo_base_match)
        
        splitter.addWidget(left_panel)

        # ============== Center Panel: Reference File Mapping ==============
        center_panel = QFrame()
        center_panel.setObjectName("PanelMapping")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(8, 10, 8, 10)
        center_layout.setSpacing(6)
        
        lbl_mapping = QLabel("Reference File Mapping")
        lbl_mapping.setObjectName("HeaderMapping")
        center_layout.addWidget(lbl_mapping)
        
        # Select which ref file to configure
        center_layout.addWidget(QLabel("Select Reference File:"))
        self.combo_current_ref = QComboBox()
        self.combo_current_ref.currentIndexChanged.connect(self.on_ref_change)
        center_layout.addWidget(self.combo_current_ref)

        # Match column dropdown (single select - which col to match on)
        self.lbl_ref_match = QLabel("Match Column (match against SOA):")
        center_layout.addWidget(self.lbl_ref_match)
        self.combo_ref_match = QComboBox()
        center_layout.addWidget(self.combo_ref_match)

        # Select All / Deselect All Buttons
        btn_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.clicked.connect(self.select_all_columns)
        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.clicked.connect(self.deselect_all_columns)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_deselect_all)
        center_layout.addLayout(btn_layout)

        # Return columns list (multi-select - which cols to include in output)
        center_layout.addWidget(QLabel("Return Columns (select to include):"))
        self.list_ref_cols = QListWidget()
        self.list_ref_cols.setObjectName("CompactList")
        self.list_ref_cols.setSelectionMode(QListWidget.MultiSelection)
        center_layout.addWidget(self.list_ref_cols)
        
        splitter.addWidget(center_panel)
        
        # Keep track of panels to toggle them
        self.panel_base = left_panel
        self.panel_mapping = center_panel

        # ============== Right Panel: Rules, Templates & Actions ==============
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
        
        # --- Save Mapping Button ---
        self.btn_add_rule = QPushButton("💾 Save Ref Mapping")
        self.btn_add_rule.setObjectName("SecondaryButton")
        self.btn_add_rule.setMinimumHeight(40)
        self.btn_add_rule.clicked.connect(self.save_current_mapping)
        right_layout.addWidget(self.btn_add_rule)

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

        # Legacy schema button can be removed or hidden, as it's now embedded
        # We will keep it but hide it in all modes for now to avoid confusion

        # --- Schema Configuration (Multi-File Only) ---
        self.btn_schema_config = QPushButton("⚙ Configure Comparison Schema")
        self.btn_schema_config.setObjectName("SecondaryButton")
        self.btn_schema_config.setMinimumHeight(40)
        self.btn_schema_config.setVisible(False)
        self.btn_schema_config.clicked.connect(self.on_schema_config)
        right_layout.addWidget(self.btn_schema_config)

        # --- Current Session Rules ---
        right_layout.addWidget(QLabel("Current Session Rules:"))
        self.list_rules = QListWidget()
        self.list_rules.setObjectName("CompactList")
        self.list_rules.setMinimumHeight(60)
        right_layout.addWidget(self.list_rules, 1) # Stretch factor 1
        
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
        splitter.setSizes([250, 350, 300])
        layout.addWidget(splitter, 1)

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
        
    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict, match_keys=None, date_col=None, amount_col=None, file_column_config=None):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        self.match_keys = match_keys or {}
        self.file_column_config = file_column_config or {}

        self.last_ref_path = None
        
        # Populate Base columns list
        self.list_base_cols.clear()
        self.list_base_cols.addItems(self.base_columns)
        
        # Populate Date and Amount dropdowns (Data passed from File Select)
        self.combo_date_col.clear()
        self.combo_date_col.addItems(self.base_columns)
        if date_col:
            dt_idx = self.combo_date_col.findText(date_col)
            if dt_idx >= 0: self.combo_date_col.setCurrentIndex(dt_idx)
            
        self.combo_amount_col.clear()
        self.combo_amount_col.addItems(self.base_columns)
        if amount_col:
            amt_idx = self.combo_amount_col.findText(amount_col)
            if amt_idx >= 0: self.combo_amount_col.setCurrentIndex(amt_idx)
        
        # Populate Master Match Key dropdown (Not used in SOA but part of UI structure)
        self.combo_base_match.clear()
        self.combo_base_match.addItems(self.base_columns)
        
        # Auto-detect Date/Amount removed here as it's done in FileSelectScreen now.
        # Logic is now just accepting the passed values.
        
        # Populate ref file selector
        self.combo_current_ref.blockSignals(True)
        self.combo_current_ref.clear()
        for ref in self.ref_files:
            self.combo_current_ref.addItem(os.path.basename(ref), ref)
        self.combo_current_ref.blockSignals(False)

        # Handle Match Keys (Pre-selected) - SOA Logic
        if self.match_keys:
            # Base/Anchor Key
            if self.base_file in self.match_keys:
                key = self.match_keys[self.base_file]
                
                # SOA Mode: Auto-select in list widget
                items = self.list_base_cols.findItems(key, Qt.MatchExactly)
                if items:
                    items[0].setSelected(True)
                    self.list_base_cols.setCurrentItem(items[0])
            
            # Disable Reference Match Combo (Visual indication handled in load_ref_ui)
            self.lbl_ref_match.setText("Match Column (Pre-selected):")
            self.combo_ref_match.setEnabled(False)
        else:
             self.combo_ref_match.setEnabled(True)

        # Trigger first load without saving (since nothing previous)
        # Trigger first load without saving (since nothing previous)
        if self.ref_files:
             # Auto-configure all reference files immediately
             self.auto_configure_all_refs()
             
             # Load first file UI
             self.load_ref_ui(self.ref_files[0])
             self.last_ref_path = self.ref_files[0]
        
        self.list_rules.clear()
        self.list_rules.clear()
        self.mapping_rules = {}
        self.schema_config = []
        self.lbl_status.setText("")
        
        # Refresh templates list
        # Refresh templates list
        self._load_templates_list()

        # Re-apply mode visibility logic to ensure splitter sizes are correct
        # after data load (which might have reset some checks)
        # Re-apply mode visibility logic to ensure splitter sizes are correct
        # using the stored current_mode (set by MainWindow)
        # set_mode removed, ensure splitter sizes are default
        self.splitter.setSizes([250, 350, 300])


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

    def auto_configure_all_refs(self):
        """Automatically create mapping rules for all reference files based on filtered columns."""
        count = 0
        
        # Strategy:
        # 1. Check if user configured specific columns in File Select (Pivot Style)
        # 2. If so, use those columns (minus match key) as return columns
        
        for ref_path in self.ref_files:
            # Skip if rule already exists (e.g. from template load, though this runs on init)
            if ref_path in self.mapping_rules:
                continue

            # Determine Match Key
            match_key = None
            if self.match_keys and ref_path in self.match_keys:
                match_key = self.match_keys[ref_path]
            elif ref_path in self.ref_columns and self.ref_columns[ref_path]:
                 # Fallback to first column if no key (shouldn't happen with new workflow)
                 match_key = self.ref_columns[ref_path][0]
            
            if not match_key:
                continue

            # Check for Custom Column Configuration
            custom_cols = self.file_column_config.get(ref_path)
            
            if custom_cols:
                # Use User Selected Columns
                # Ensure match key is not in return cols
                return_cols = [c for c in custom_cols if c != match_key]
                print(f"[MappingScreen] Auto-mapping {os.path.basename(ref_path)} using custom Selection ({len(return_cols)} columns)")
            else:
                 # Default: Do NOT auto-map EVERYTHING. 
                 # User complained "waste time". If they didn't config, they might want to do it here.
                 # BUT, previous logic was "Select ALL". Let's stick to "Select ALL" if no custom config to be safe?
                 # Or maybe do nothing? The request was "we already configured... why waste time".
                 # Implies: If configured -> Map it. If not -> Wait for user?
                 # Let's stick to: If Configured -> Map. If Not -> Select All (Old behavior)
                 # because otherwise they have to select manualy.
                 all_cols = self.ref_columns.get(ref_path, [])
                 return_cols = [c for c in all_cols if c != match_key]
            
            if not return_cols:
                 # If only match key was selected, or empty, fallback to all (safeguard)
                 # or if custom config was just match key, then return cols is empty.
                 # Let's warn or just map empty?
                 pass

            # Create Rule
            self.mapping_rules[ref_path] = {
                "match_col": match_key,
                "return_cols": return_cols,
                "match_type": "exact" # Default
            }
            count += 1
        
        if count > 0:
            self.update_rules_list()
            self.lbl_status.setText(f"✔ Auto-configured {count} files")
            print(f"[MappingScreen] Auto-configured {count} files with default settings")

    # ======================== Ref File Switching ========================

    # ======================== Ref File Switching ========================

    def on_ref_change(self):
        """Called by dropdown change signal. Auto-saves previous ref and loads new one."""
        # 1. Save previous state (Auto-Save)
        if self.last_ref_path:
            self.save_current_mapping(quiet=True, target_ref=self.last_ref_path)
            
        # 2. Load new state
        new_ref = self.combo_current_ref.currentData()
        if new_ref:
            self.load_ref_ui(new_ref)
            self.last_ref_path = new_ref

    def load_ref_ui(self, ref_path):
        """Update UI elements for the selected reference file."""
        if ref_path not in self.ref_columns:
            return
            
        cols = self.ref_columns[ref_path]
        
        self.combo_ref_match.clear()
        self.combo_ref_match.addItems(cols)
        
        self.list_ref_cols.clear()
        self.list_ref_cols.addItems(cols)
        
        # 1. Handle Upstream Match Keys (High Priority)
        match_key_locked = False
        if hasattr(self, 'match_keys') and self.match_keys.get(ref_path):
             pre_selected = self.match_keys[ref_path]
             idx = self.combo_ref_match.findText(pre_selected)
             if idx >= 0:
                 self.combo_ref_match.setCurrentIndex(idx)
             
             # SOA Mode: Pre-select but allow change
             self.combo_ref_match.setEnabled(True)
             self.lbl_ref_match.setText(f"Match Column (Pre-selected):")
                 
             match_key_locked = True # Treat as locked for restoration logic below (don't overwrite with saved rule immediately if upstream is set)
        else:
             self.combo_ref_match.setEnabled(True)
             self.lbl_ref_match.setText("Match Column (match against SOA/Anchor):")

        # 2. Restore Saved Rule (if any)
        if ref_path in self.mapping_rules:
            rule = self.mapping_rules[ref_path]
            
            # Restore Match Column (Only if not locked by upstream)
            if not match_key_locked:
                idx = self.combo_ref_match.findText(rule["match_col"])
                if idx >= 0:
                    self.combo_ref_match.setCurrentIndex(idx)
            
            # Restore Return Columns
            return_cols = rule.get("return_cols", [])
            for i in range(self.list_ref_cols.count()):
                item = self.list_ref_cols.item(i)
                if item.text() in return_cols:
                    item.setSelected(True)
            
            # Restore Match Type
            is_fuzzy = (rule.get("match_type") == "fuzzy")
            self.chk_fuzzy.setChecked(is_fuzzy)
            
            self.lbl_status.setText(f"✔ Settings loaded for {os.path.basename(ref_path)}")
        else:
            # Default State for new file
            self.chk_fuzzy.setChecked(False) 
            self.lbl_status.setText(f"• New file selected")

    def select_all_columns(self):
        for i in range(self.list_ref_cols.count()):
            self.list_ref_cols.item(i).setSelected(True)

    def deselect_all_columns(self):
        for i in range(self.list_ref_cols.count()):
            self.list_ref_cols.item(i).setSelected(False)

    # ======================== Add Rule (Save Logic) ========================

    def save_current_mapping(self, quiet=False, target_ref=None):
        """Save the mapping rule for the currently selected reference file to memory."""
        # Use target_ref if provided (essential for auto-save during switch)
        current_ref = target_ref or self.combo_current_ref.currentData() or self.last_ref_path
        if not current_ref:
            return

        ref_display = os.path.basename(current_ref)
        match_col = self.combo_ref_match.currentText()
        match_col = self.combo_ref_match.currentText()
        
        # Fallback to match_keys if combo is empty (shouldn't happen if logic is correct, but safe)
        if hasattr(self, 'match_keys') and self.match_keys.get(current_ref):
             match_col = self.match_keys[current_ref]

        if not match_col:
            if not quiet: QMessageBox.warning(self, "No Match Column", "Please select a match column.")
            return
        
        selected_returns = [item.text() for item in self.list_ref_cols.selectedItems()]
        if not selected_returns:
            if not quiet: QMessageBox.warning(self, "No Return Columns", "Please select at least one return column.")
            return

        match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
        
        self.mapping_rules[current_ref] = {
            "match_col": match_col,
            "return_cols": selected_returns,
            "match_type": match_type
        }
        
        self.update_rules_list()
        
        if not quiet:
            self.lbl_status.setText(f"✔ Saved mapping for {ref_display}")
            print(f"[MappingScreen] Manually saved rule for {ref_display}")

    def update_rules_list(self):
        """Update the rules list widget based on self.mapping_rules."""
        self.list_rules.clear()
        for ref_path, rule in self.mapping_rules.items():
            ref_display = os.path.basename(ref_path)
            returns_preview = ', '.join(rule["return_cols"][:3])
            if len(rule["return_cols"]) > 3:
                returns_preview += f" +{len(rule['return_cols'])-3} more"
            
            display_text = f"✔ {ref_display}: Match '{rule['match_col']}' → [{returns_preview}]"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, ref_path)
            self.list_rules.addItem(item)

    # Legacy alias, kept for compatibility if needed, but redirects to new logic
    def add_rule(self):
        self.save_current_mapping()
        
    def on_schema_config(self):
        """Open the schema configuration dialog."""
        from app.ui.schema_config import ComparisonSchemaDialog
        
        # Prepare ref columns (only for current ref files)
        current_ref_cols = {r: self.ref_columns.get(r, []) for r in self.ref_files}
        
        dialog = ComparisonSchemaDialog(self.ref_files, current_ref_cols, self.schema_config, self)
        if dialog.exec():
            self.schema_config = dialog.schema
            self.lbl_status.setText(f"✔ Schema updated with {len(self.schema_config)} fields")
            print(f"[MappingScreen] Schema config updated: {len(self.schema_config)} fields")

    # ======================== Run ========================

    def on_run(self):
        """Gather all mapping rules and emit run signal."""
        # Auto-save current ref mapping if not yet saved (final check)
        self.save_current_mapping(quiet=True)

        if not self.mapping_rules:
            QMessageBox.warning(self, "No Mapping Rules", 
                "Please configure at least one reference file mapping.\n\n"
                "Select a match column and return columns for each reference file, "
                "then click 'Save Ref Mapping'.")
            return
            
        # Strict SOA Config
        config = {
            "rules": self.mapping_rules,
            "date_col": self.combo_date_col.currentText(),
            "amount_col": self.combo_amount_col.currentText(),
            "master_match_col": None, # SOA uses first col or internal logic if not set here
            "schema_config": [], # No schema for SOA
            "match_keys": {} # No match keys for SOA logic consumption (handled in set_data UI pre-selection)
        }
        
        print(f"[SOAMappingScreen] Running in SOA mode")
        print(f"[SOAMappingScreen] Config: {config}")
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
            ref_count = len(tmpl.get("rules", {}))
            date_col = tmpl.get("date_col", "?")
            amt_col = tmpl.get("amount_col", "?")
            display = f"{name}  ({ref_count} ref{'s' if ref_count != 1 else ''}, date={date_col}, amt={amt_col})"
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, name)
            self.list_templates.addItem(item)

    def save_template(self):
        """Save current mapping rules as a named template."""
        # Auto-capture current ref if not saved
        self.save_current_mapping(quiet=True)

        if not self.mapping_rules:
            QMessageBox.warning(self, "No Rules to Save", 
                "Please configure at least one mapping rule before saving a template.")
            return

        name, ok = QInputDialog.getText(self, "Save Template", 
            "Enter a name for this template:\n(e.g., 'Monthly SOA - Carrier XYZ')")
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Build template (store column names only, not paths — paths change)
        template = {

            "date_col": self.combo_date_col.currentText(),
            "amount_col": self.combo_amount_col.currentText(),
            "rules": {},
            "schema_config": []
        }
        
        for ref_path, rule in self.mapping_rules.items():
            ref_basename = os.path.basename(ref_path)
            template["rules"][ref_basename] = {
                "match_col": rule["match_col"],
                "return_cols": rule["return_cols"],
                "match_type": rule.get("match_type", "exact")
            }
        
        templates = self._get_templates()
        templates[name] = template
        self._save_templates(templates)
        self._load_templates_list()
        
        self.lbl_status.setText(f"✔ Template '{name}' saved!")
        print(f"[MappingScreen] Template saved: {name}")

    def load_template(self):
        """Load a saved template and apply it to the current mapping."""
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
        
        # Apply date/amount columns
        date_idx = self.combo_date_col.findText(tmpl.get("date_col", ""))
        if date_idx >= 0:
            self.combo_date_col.setCurrentIndex(date_idx)
        
        amt_idx = self.combo_amount_col.findText(tmpl.get("amount_col", ""))
        if amt_idx >= 0:
            self.combo_amount_col.setCurrentIndex(amt_idx)
        
        # Apply rules: match template ref basenames to current ref files
        self.mapping_rules.clear()
        self.list_rules.clear()
        applied_count = 0
        
        for ref_basename, rule in tmpl.get("rules", {}).items():
            # Find matching ref path by basename
            matched_ref_path = None
            for ref_path in self.ref_files:
                if os.path.basename(ref_path) == ref_basename:
                    matched_ref_path = ref_path
                    break
            
            if matched_ref_path:
                # Validate columns exist in current ref file
                ref_cols = self.ref_columns.get(matched_ref_path, [])
                match_col = rule.get("match_col", "")
                return_cols = [c for c in rule.get("return_cols", []) if c in ref_cols]
                
                if match_col in ref_cols and return_cols:
                    self.mapping_rules[matched_ref_path] = {
                        "match_col": match_col,
                        "return_cols": return_cols,
                        "match_type": rule.get("match_type", "exact")
                    }
                    
                    returns_preview = ', '.join(return_cols[:3])
                    if len(return_cols) > 3:
                        returns_preview += f" +{len(return_cols)-3} more"
                    display_text = f"✔ {ref_basename}: Match '{match_col}' → [{returns_preview}]"
                    
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, matched_ref_path)
                    self.list_rules.addItem(item)
                    applied_count += 1
                else:
                    print(f"[MappingScreen] Template rule skipped for {ref_basename}: columns not found")
            else:
                print(f"[MappingScreen] Template ref '{ref_basename}' not found in current files")
        
        # Apply Schema Config (if present)
        schema_data = tmpl.get("schema_config", [])
        if schema_data and hasattr(self, 'schema_widget'):
            # Reload schema widget
            if hasattr(self.schema_widget, 'load_schema'):
                self.schema_widget.load_schema(schema_data)
            else:
                # Fallback: set data and re-init (if method not yet added, but I will add it)
                self.schema_widget.schema = schema_data
                # Clear and re-populate (manual approach until method is guaranteed)
                layout = self.schema_widget.layout()
                # Find the table and clear it?
                # Actually, best to just rely on adding load_schema to SchemaConfigWidget next.
                pass 
                
        # Refresh the current ref view
        self.on_ref_change()
        
        if applied_count > 0:
            self.lbl_status.setText(f"✔ Template '{tmpl_name}' loaded! ({applied_count} rule{'s' if applied_count != 1 else ''} applied)")
        else:
            self.lbl_status.setText(f"⚠ Template '{tmpl_name}' loaded but no matching files found.")
            self.lbl_status.setStyleSheet("color: #FF9800; font-weight: bold; font-size: 12px;")
        
        print(f"[MappingScreen] Template loaded: {tmpl_name}, applied {applied_count} rules")

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
