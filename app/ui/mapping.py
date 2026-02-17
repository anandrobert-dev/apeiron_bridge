
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


class MappingScreen(QWidget):
    """
    Screen for mapping columns between Base (SOA) and Reference files.
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

        # ============== Right Panel: Rules, Templates & Actions ==============
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(4)
        
        # --- Match Type ---
        match_group = QGroupBox("Match Configuration")
        match_group_layout = QVBoxLayout(match_group)
        
        self.chk_fuzzy = QCheckBox("Enable Partial/Fuzzy Match")
        self.chk_fuzzy.setToolTip(
            "When ENABLED: Matches partial text (e.g., 'INV-123' matches 'INV-12345').\n"
            "Useful when invoice numbers have extra characters or prefixes.\n\n"
            "When DISABLED (default): Only exact matches are used.\n"
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
        self.btn_add_rule.clicked.connect(self.add_rule)
        right_layout.addWidget(self.btn_add_rule)

        # --- Current Session Rules ---
        right_layout.addWidget(QLabel("Current Session Rules:"))
        self.list_rules = QListWidget()
        self.list_rules.setMaximumHeight(100)
        right_layout.addWidget(self.list_rules)
        
        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 12px;")
        self.lbl_status.setWordWrap(True)
        right_layout.addWidget(self.lbl_status)

        # --- Templates Section ---
        templates_group = QGroupBox("Saved Templates")
        templates_layout = QVBoxLayout(templates_group)
        
        templates_hint = QLabel("Save your mapping config as a template to reuse next time.")
        templates_hint.setStyleSheet("color: #888; font-size: 11px;")
        templates_hint.setWordWrap(True)
        templates_layout.addWidget(templates_hint)
        
        self.list_templates = QListWidget()
        self.list_templates.setMaximumHeight(120)
        templates_layout.addWidget(self.list_templates)
        
        # Template buttons
        tmpl_btn_layout = QHBoxLayout()
        
        self.btn_save_template = QPushButton("Save As Template")
        self.btn_save_template.setMinimumHeight(30)
        self.btn_save_template.clicked.connect(self.save_template)
        tmpl_btn_layout.addWidget(self.btn_save_template)
        
        self.btn_load_template = QPushButton("Load Template")
        self.btn_load_template.setMinimumHeight(30)
        self.btn_load_template.clicked.connect(self.load_template)
        tmpl_btn_layout.addWidget(self.btn_load_template)
        
        self.btn_delete_template = QPushButton("🗑")
        self.btn_delete_template.setMaximumWidth(40)
        self.btn_delete_template.setMinimumHeight(30)
        self.btn_delete_template.setToolTip("Delete selected template")
        self.btn_delete_template.clicked.connect(self.delete_template)
        tmpl_btn_layout.addWidget(self.btn_delete_template)
        
        templates_layout.addLayout(tmpl_btn_layout)
        right_layout.addWidget(templates_group)

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
        
        # Internal storage for rules: {ref_path: {match_col, return_cols, match_type}}
        self.mapping_rules = {}
        
        # Load saved templates
        self._load_templates_list()

    # ======================== Data Setup ========================

    def set_data(self, base_file, ref_files, base_cols, ref_cols_dict):
        self.base_file = base_file
        self.ref_files = ref_files
        self.base_columns = base_cols
        self.ref_columns = ref_cols_dict
        
        # Populate Base columns list
        self.list_base_cols.clear()
        self.list_base_cols.addItems(self.base_columns)
        
        # Populate Date and Amount dropdowns
        self.combo_date_col.clear()
        self.combo_date_col.addItems(self.base_columns)
        
        self.combo_amount_col.clear()
        self.combo_amount_col.addItems(self.base_columns)
        
        # Auto-detect Date column
        date_keywords = ['date', 'dt', 'dated', 'invoice date', 'inv date', 'receive date']
        best_date_idx = self._find_best_column_match(self.base_columns, date_keywords)
        if best_date_idx >= 0:
            self.combo_date_col.setCurrentIndex(best_date_idx)
        
        # Auto-detect Amount column
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
        
        # Refresh templates list
        self._load_templates_list()

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

    # ======================== Ref File Switching ========================

    def on_ref_change(self):
        """When user switches the ref file dropdown, update columns."""
        current_ref = self.combo_current_ref.currentData()
        if current_ref and current_ref in self.ref_columns:
            cols = self.ref_columns[current_ref]
            
            self.combo_ref_match.clear()
            self.combo_ref_match.addItems(cols)
            
            self.list_ref_cols.clear()
            self.list_ref_cols.addItems(cols)
            
            # Restore previous selections
            if current_ref in self.mapping_rules:
                rule = self.mapping_rules[current_ref]
                idx = self.combo_ref_match.findText(rule["match_col"])
                if idx >= 0:
                    self.combo_ref_match.setCurrentIndex(idx)
                for i in range(self.list_ref_cols.count()):
                    item = self.list_ref_cols.item(i)
                    if item.text() in rule.get("return_cols", []):
                        item.setSelected(True)
                self.lbl_status.setText(f"✔ Mapping exists for this file")
            else:
                self.lbl_status.setText("")

    # ======================== Add Rule ========================

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
        
        selected_returns = [item.text() for item in self.list_ref_cols.selectedItems()]
        if not selected_returns:
            QMessageBox.warning(self, "No Return Columns", 
                "Please select at least one return column.\n\n"
                "These are the columns from the reference file that will be included in the output.")
            return

        match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
        
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
        
        # Remove existing entry
        for i in range(self.list_rules.count()):
            if self.list_rules.item(i).data(Qt.UserRole) == current_ref:
                self.list_rules.takeItem(i)
                break
        
        item = QListWidgetItem(display_text)
        item.setData(Qt.UserRole, current_ref)
        self.list_rules.addItem(item)
        
        self.lbl_status.setText(f"✔ Mapping saved for {ref_display}")
        print(f"[MappingScreen] Rule saved: {display_text}")

    # ======================== Run ========================

    def on_run(self):
        """Gather all mapping rules and emit run signal."""
        # Auto-save current ref mapping if not yet saved
        current_ref = self.combo_current_ref.currentData()
        if current_ref and current_ref not in self.mapping_rules:
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
        current_ref = self.combo_current_ref.currentData()
        if current_ref and current_ref not in self.mapping_rules:
            match_col = self.combo_ref_match.currentText()
            selected_returns = [item.text() for item in self.list_ref_cols.selectedItems()]
            if match_col and selected_returns:
                match_type = "fuzzy" if self.chk_fuzzy.isChecked() else "exact"
                self.mapping_rules[current_ref] = {
                    "match_col": match_col,
                    "return_cols": selected_returns,
                    "match_type": match_type
                }

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
            "rules": {}
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
