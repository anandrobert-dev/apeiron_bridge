
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QListWidget, QListWidgetItem, QComboBox, QMessageBox,
    QProgressBar, QFrame, QGridLayout
)
import PySide6.QtCore
from PySide6.QtCore import Qt, Signal
import os

class SOAFileSelectScreen(QWidget):
    """
    Screen for adding/removing files and selecting the Base file for SOA Reconciliation.
    """
    # Signal to proceed to Mapping Screen with loaded data
    # Signal to proceed to Mapping Screen with loaded data
    # Signal to proceed to Mapping Screen with loaded data
    # args: (base_file_path, list_of_ref_file_paths, config_json, match_keys, date_col, amount_col)
    proceed_to_mapping = Signal(str, list, dict, dict, str, str)
    # Signal to run reconciliation immediately (Skipping Mapping Screen)
    run_reconciliation_now = Signal(dict)
    go_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = [] # List of file paths
        self.file_column_config = {} # {file_path: [selected_columns]}
        self.setAcceptDrops(True) # Enable Drag & Drop
        self.init_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid_extensions = ['.xlsx', '.xls', '.csv'] # Only allowed types
        
        added_count = 0
        for f in files:
            if any(f.lower().endswith(ext) for ext in valid_extensions):
                if f not in self.files:
                    self.files.append(f)
                    self.add_file_to_ui(f)
                    added_count += 1
        
        if added_count > 0:
            self.update_base_combo()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Header
        self.lbl_header = QLabel("Select Files for SOA Reconciliation")
        self.lbl_header.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(self.lbl_header)

        # Controls (Add File)
        controls_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Excel/CSV Files")
        self.btn_add.setObjectName("PrimaryButton")
        self.btn_add.clicked.connect(self.browse_files)
        
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_remove.setObjectName("SecondaryButton") # Or a default style
        self.btn_remove.clicked.connect(self.remove_file)
        
        controls_layout.addWidget(self.btn_add)
        controls_layout.addWidget(self.btn_remove)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # File List
        self.file_list = QListWidget()
        self.file_list.setObjectName("Card") # Style like a card
        layout.addWidget(self.file_list, 1) # Expand to fill vertical space

        # Base File Selection
        base_selection_layout = QHBoxLayout()
        self.lbl_base_select = QLabel("Select Base File (SOA):")
        self.combo_base = QComboBox()
        self.combo_base.setFixedWidth(400)
        
        base_selection_layout.addWidget(self.lbl_base_select)
        base_selection_layout.addWidget(self.combo_base)
        base_selection_layout.addStretch()
        layout.addLayout(base_selection_layout)

        # Date/Amount Selection (Moved from Mapping Screen)
        input_layout = QHBoxLayout()
        
        # Date
        input_layout.addWidget(QLabel("Date Column:"))
        self.combo_date = QComboBox()
        self.combo_date.setMinimumWidth(150)
        input_layout.addWidget(self.combo_date)
        
        input_layout.addSpacing(20)
        
        # Amount
        input_layout.addWidget(QLabel("Amount Column:"))
        self.combo_amount = QComboBox()
        self.combo_amount.setMinimumWidth(150)
        input_layout.addWidget(self.combo_amount)
        
        input_layout.addStretch()
        layout.addLayout(input_layout)
        
        # Connect base selection change to column loading
        self.combo_base.currentIndexChanged.connect(self.on_base_file_changed)

        # layout.addStretch() # Removed to allow file list to expand

        # Navigation Footer
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_next = QPushButton("Next: Map Columns")
        self.btn_next.setObjectName("PrimaryButton")
        self.btn_next.clicked.connect(self.on_next)
        
        nav_layout.addWidget(self.btn_back)
        nav_layout.addStretch()
        
        # Run Button (New)
        self.btn_run = QPushButton("▶ Run Reconciliation")
        self.btn_run.setObjectName("SuccessButton") # Green style usually
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; 
                color: white; 
                font-weight: bold;
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #388e3c; }
        """)
        self.btn_run.clicked.connect(self.on_run_click)
        nav_layout.addWidget(self.btn_run)
        
        nav_layout.addSpacing(10)
        
        self.btn_next = QPushButton("Advanced Settings >")
        self.btn_next.setToolTip("Configure templates, fuzzy matching, or specific column mapping.")
        # specific style for next to differentiate
        self.btn_next.setStyleSheet("""
             QPushButton {
                background-color: #555; 
                color: #EEE; 
                border: 1px solid #777; 
                padding: 8px 16px; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #666; }
        """)
        self.btn_next.clicked.connect(self.on_next)
        
        nav_layout.addWidget(self.btn_next)
        layout.addLayout(nav_layout)

    def browse_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "", "Excel/CSV Files (*.xlsx *.xls *.csv)"
        )
        if file_paths:
            for path in file_paths:
                if path not in self.files:
                    self.files.append(path)
                    self.add_file_to_ui(path)
            self.update_base_combo()

    def _save_match_key_selections(self):
        """Save current match key combo selections for all files."""
        selections = {}
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo = item.data(Qt.UserRole + 1)
            if path and combo:
                selections[path] = combo.currentText()
        return selections

    def _restore_match_key_selections(self, selections):
        """Restore match key combo selections after rebuilding the list."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo = item.data(Qt.UserRole + 1)
            if path and combo and path in selections:
                idx = combo.findText(selections[path])
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def move_file_up(self, path):
        """Move a file one position up in the list."""
        idx = self.files.index(path)
        if idx > 0:
            saved = self._save_match_key_selections()
            self.files[idx], self.files[idx - 1] = self.files[idx - 1], self.files[idx]
            self.rebuild_file_list()
            self._restore_match_key_selections(saved)
            self.update_base_combo()

    def move_file_down(self, path):
        """Move a file one position down in the list."""
        idx = self.files.index(path)
        if idx < len(self.files) - 1:
            saved = self._save_match_key_selections()
            self.files[idx], self.files[idx + 1] = self.files[idx + 1], self.files[idx]
            self.rebuild_file_list()
            self._restore_match_key_selections(saved)
            self.update_base_combo()

    def rebuild_file_list(self):
        """Clear and rebuild the file list widget from self.files, preserving column configs."""
        self.file_list.clear()
        for path in self.files:
            self.add_file_to_ui(path)

    def add_file_to_ui(self, path):
        # Create Item
        item = QListWidgetItem()
        self.file_list.addItem(item)
        
        # Create Widget for Item (Arrows + Role Badge + Label + Match Key + Config Button)
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 8, 10, 8)
        
        # ▲/▼ Reorder Buttons
        arrow_style = """
            QPushButton {
                background-color: #3a3a3a;
                color: #CCC;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
                padding: 2px;
                min-width: 24px;
                max-width: 24px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover { background-color: #4a4a4a; color: #FFF; }
            QPushButton:pressed { background-color: #555; }
        """
        
        btn_up = QPushButton("▲")
        btn_up.setStyleSheet(arrow_style)
        btn_up.setToolTip("Move up")
        btn_up.setCursor(Qt.PointingHandCursor)
        btn_up.clicked.connect(lambda checked=False, p=path: self.move_file_up(p))
        
        btn_down = QPushButton("▼")
        btn_down.setStyleSheet(arrow_style)
        btn_down.setToolTip("Move down")
        btn_down.setCursor(Qt.PointingHandCursor)
        btn_down.clicked.connect(lambda checked=False, p=path: self.move_file_down(p))
        
        arrow_container = QWidget()
        arrow_container.setFixedWidth(30)
        arrow_layout = QVBoxLayout(arrow_container)
        arrow_layout.setContentsMargins(0, 0, 0, 0)
        arrow_layout.setSpacing(2)
        arrow_layout.addWidget(btn_up)
        arrow_layout.addWidget(btn_down)
        
        # Role Badge (Main / Ref1 / Ref2 / Ref3)
        lbl_role = QLabel("")
        lbl_role.setFixedWidth(60)
        lbl_role.setAlignment(Qt.AlignCenter)
        lbl_role.setStyleSheet("""
            QLabel {
                background-color: #555;
                color: #FFF;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        
        # File Info Layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        # Filename
        lbl_name = QLabel(os.path.basename(path))
        lbl_name.setStyleSheet("font-size: 15px; font-weight: bold; color: #FFFFFF;")
        info_layout.addWidget(lbl_name)
        
        # File Details (Size, Ext)
        try:
            size_bytes = os.path.getsize(path)
            size_str = self.human_readable_size(size_bytes)
        except:
            size_str = "Unknown size"
            
        ext = os.path.splitext(path)[1].upper().replace(".", "")
        lbl_details = QLabel(f"{ext} File • {size_str}")
        lbl_details.setStyleSheet("font-size: 12px; color: #AAAAAA;")
        info_layout.addWidget(lbl_details)

        # Match Key Selection
        lbl_key = QLabel("Match Key / Join Column:")
        lbl_key.setStyleSheet("color: #AAAAAA; font-size: 10px;")

        combo_key = QComboBox()
        combo_key.setMinimumWidth(150)
        combo_key.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px;
            }
        """)
        
        # Load Columns for Combobox
        try:
            from app.core.data_loader import DataLoader
            cols = DataLoader.load_file_headers(path)
            combo_key.addItems(cols)
        except Exception as e:
            print(f"Error loading columns for {path}: {e}")

        # Store combo reference and role label in item for retrieval
        item.setData(Qt.UserRole + 1, combo_key)
        item.setData(Qt.UserRole + 2, lbl_role)
        
        # Configure Button
        btn_config = QPushButton("⚙ Configure Columns")
        btn_config.setToolTip("Select specific columns to use (Pivot Style)")
        btn_config.setCursor(Qt.PointingHandCursor)
        
        # Check if this path already has column config (restore green state)
        if path in self.file_column_config:
            count = len(self.file_column_config[path])
            btn_config.setText(f"✔ Configured ({count} cols)")
            btn_config.setStyleSheet("""
                QPushButton {
                    background-color: #2e7d32; 
                    color: white; 
                    border: none; 
                    padding: 6px 12px; 
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #388e3c; }
            """)
        else:
            btn_config.setStyleSheet("""
                QPushButton {
                    background-color: #3f51b5; 
                    color: white; 
                    border: none; 
                    padding: 6px 12px; 
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #5c6bc0; }
            """)
        
        btn_config.clicked.connect(lambda checked=False, p=path, b=btn_config: self.open_column_config(p, b))
        
        # Match Key Container
        match_key_container = QWidget()
        match_key_container.setFixedWidth(250)
        match_key_layout = QVBoxLayout(match_key_container)
        match_key_layout.setContentsMargins(0, 0, 0, 0)
        match_key_layout.setSpacing(4)
        match_key_layout.addWidget(lbl_key)
        match_key_layout.addWidget(combo_key)
        
        # Layout: [ ▲▼ ] [ Role Badge ] [ File Info (Stretch) ] [ Match Key ] [ Config Button ]
        layout.addWidget(arrow_container)
        layout.addSpacing(6)
        layout.addWidget(lbl_role)
        layout.addSpacing(10)
        layout.addLayout(info_layout, 1)
        layout.addSpacing(20)
        layout.addWidget(match_key_container)
        layout.addSpacing(20)
        layout.addWidget(btn_config)
        
        # Row Height
        widget.setLayout(layout)
        item.setSizeHint(widget.sizeHint() +  PySide6.QtCore.QSize(0, 10))
        if item.sizeHint().height() < 70:
            item.setSizeHint(PySide6.QtCore.QSize(item.sizeHint().width(), 70))
        
        # Set Widget
        self.file_list.setItemWidget(item, widget)
        item.setData(Qt.UserRole, path)
        
        # Update all role labels after adding
        self.update_role_labels()

    def human_readable_size(self, size, decimal_places=1):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                break
            size /= 1024.0
        return f"{size:.{decimal_places}f} {unit}"

    def open_column_config(self, path, btn_widget):
        """Open drag-and-drop column selector."""
        try:
            from app.core.data_loader import DataLoader
            from app.ui.column_config import ColumnConfigDialog
            
            # Load headers only (efficiently?)
            # DataLoader loads full df, might be slow for huge files but necessary
            # TODO: Add optimization later if needed
            df = DataLoader.load_file(path)
            all_columns = df.columns.tolist()
            
            initial_selection = self.file_column_config.get(path, [])
            
            dialog = ColumnConfigDialog(path, all_columns, initial_selection, self)
            if dialog.exec():
                selected = dialog.selected_columns
                if selected:
                     self.file_column_config[path] = selected
                     # visual feedback: Update Button to Green
                     count = len(selected)
                     btn_widget.setText(f"✔ Configured ({count} cols)")
                     btn_widget.setStyleSheet("""
                        QPushButton {
                            background-color: #2e7d32; 
                            color: white; 
                            border: none; 
                            padding: 6px 12px; 
                            border-radius: 4px;
                        }
                        QPushButton:hover { background-color: #388e3c; }
                     """)
                     print(f"Configured {count} columns for {os.path.basename(path)}")
                else:
                     # If user clears selection, remove from config (revert to all)
                     if path in self.file_column_config:
                         del self.file_column_config[path]
                     
                     # Revert Button to Default
                     btn_widget.setText("⚙ Configure Columns")
                     btn_widget.setStyleSheet("""
                        QPushButton {
                            background-color: #3f51b5; 
                            color: white; 
                            border: none; 
                            padding: 6px 12px; 
                            border-radius: 4px;
                        }
                        QPushButton:hover { background-color: #5c6bc0; }
                     """)
        except Exception as e:
            QMessageBox.critical(self, "Error Loading File Data", f"Could not read file headers:\n{str(e)}")

    def remove_file(self):
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            item = self.file_list.takeItem(current_row)
            path = item.data(Qt.UserRole)
            if path in self.files:
                self.files.remove(path)
            self.update_base_combo()

    def update_role_labels(self):
        """Update the role badges (Main ★, Ref1, Ref2...) based on current base file."""
        base_path = self.combo_base.currentData()
        ref_counter = 1
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            lbl_role = item.data(Qt.UserRole + 2)
            path = item.data(Qt.UserRole)
            
            if not lbl_role:
                continue
            
            if path == base_path:
                lbl_role.setText("★ Main")
                lbl_role.setStyleSheet("""
                    QLabel {
                        background-color: #1565C0;
                        color: #FFFFFF;
                        border-radius: 4px;
                        padding: 4px 6px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                """)
            else:
                lbl_role.setText(f"Ref{ref_counter}")
                lbl_role.setStyleSheet("""
                    QLabel {
                        background-color: #E65100;
                        color: #FFFFFF;
                        border-radius: 4px;
                        padding: 4px 6px;
                        font-size: 11px;
                        font-weight: bold;
                    }
                """)
                ref_counter += 1

    def update_base_combo(self):
        current_base = self.combo_base.currentText()
        self.combo_base.blockSignals(True)
        self.combo_base.clear()
        for path in self.files:
            self.combo_base.addItem(os.path.basename(path), path)
        
        # Restore selection if possible
        index = self.combo_base.findText(current_base)
        if index >= 0:
            self.combo_base.setCurrentIndex(index)
        elif self.combo_base.count() > 0:
             self.combo_base.setCurrentIndex(0)
             
        self.combo_base.blockSignals(False)
        self.on_base_file_changed()

    def on_base_file_changed(self):
        """Load columns for the selected base file into Date/Amount dropdowns."""
        # Update role badges whenever base changes
        self.update_role_labels()
        
        base_path = self.combo_base.currentData()
        if not base_path:
            self.combo_date.clear()
            self.combo_amount.clear()
            return
            
        try:
            from app.core.data_loader import DataLoader
            cols = DataLoader.load_file_headers(base_path)
            
            # Populate Date
            self.combo_date.clear()
            self.combo_date.addItems(cols)
            
            # Populate Amount
            self.combo_amount.clear()
            self.combo_amount.addItems(cols)
            
            # Auto-Detect
            self._auto_select_columns(cols)
            
        except Exception as e:
            print(f"Error loading base columns: {e}")

    def _auto_select_columns(self, columns):
        """Helper to fuzzy match date and amount columns."""
        # Date Keywords
        date_keywords = ['date', 'dt', 'dated', 'invoice date', 'inv date', 'receive date']
        best_date_idx = -1
        # Simple containment check
        for i, col in enumerate(columns):
            if any(k in col.lower() for k in date_keywords):
                best_date_idx = i
                break # Take first match
        
        if best_date_idx >= 0:
            self.combo_date.setCurrentIndex(best_date_idx)
            
        # Amount Keywords
        amount_keywords = ['amount', 'amt', 'open amount', 'invoice amount', 'total', 'value', 'balance']
        best_amt_idx = -1
        for i, col in enumerate(columns):
            if any(k in col.lower() for k in amount_keywords):
                best_amt_idx = i
                break
                
        if best_amt_idx >= 0:
            self.combo_amount.setCurrentIndex(best_amt_idx)

    # set_mode removed as this class is now strictly SOA

    def on_run_click(self):
        """Gather configuration and run immediately."""
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add at least one file.")
            return
        
        base_path = self.combo_base.currentData()
        if not base_path:
             QMessageBox.warning(self, "No Base File", "Please select a Base file.")
             return

        ref_files = [f for f in self.files if f != base_path]
        if not ref_files:
            QMessageBox.warning(self, "No Reference Files", "Please add at least one reference file.")
            return

        # Gather Match Keys
        match_keys = {}
        base_match_key = None
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            
            # We do NOT skip base path anymore, because we need its match key for 'master_match_col'
            # if path == base_path: continue 

            combo_key = item.data(Qt.UserRole + 1)
            
            if path and combo_key:
                selected_key = combo_key.currentText()
                if not selected_key:
                        QMessageBox.warning(self, "Missing Key", f"Please select a Match Key for {os.path.basename(path)}")
                        return
                match_keys[path] = selected_key
                
                if path == base_path:
                    base_match_key = selected_key
        
        if not base_match_key:
             # Fallback: If base file not in list (shouldn't happen) or key empty
             QMessageBox.warning(self, "Missing Base Key", "Could not identify match key for Base File.")
             return
        
        # Get Date/Amount
        date_col = self.combo_date.currentText()
        amount_col = self.combo_amount.currentText()
        
        if not date_col or not amount_col:
             QMessageBox.warning(self, "Missing Columns", "Please select valid Date and Amount columns.")
             return

        # Build Rules
        rules = {}
        try:
            from app.core.data_loader import DataLoader
            
            for ref_path in ref_files:
                match_col = match_keys.get(ref_path)
                if not match_col:
                    QMessageBox.warning(self, "Missing Key", f"Match key missing for {os.path.basename(ref_path)}")
                    return
                
                # Determine Return Columns
                if ref_path in self.file_column_config:
                    # User configured specific columns
                    all_cols = self.file_column_config[ref_path]
                else:
                    # Default: All columns
                    all_cols = DataLoader.load_file_headers(ref_path)
                
                # Include ALL columns (match key is mandatory in output)
                return_cols = list(all_cols)
                
                rules[ref_path] = {
                    "match_col": match_col,
                    "return_cols": return_cols,
                    "match_type": "exact" # Default for quick run
                }
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to prepare configuration: {e}")
            return

        # Construct Config
        config = {
            "rules": rules,
            "date_col": date_col,
            "amount_col": amount_col,
            "master_match_col": base_match_key,
            "schema_config": [],
            "match_keys": match_keys,
            "base_file": base_path,
            "column_config": self.file_column_config
        }
        
        # Emit Signal
        self.run_reconciliation_now.emit(config)

    def on_next(self):
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add at least one file.")
            return
        
        base_path = self.combo_base.currentData()
        if not base_path:
             QMessageBox.warning(self, "No Base File", "Please select a Base file.")
             return

        # Ref files are all except base
        ref_files = [f for f in self.files if f != base_path]
        
        # Collect Match Keys (For SOA now)
        match_keys = {} # {file_path: selected_column}
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            
            if path and combo_key:
                selected_key = combo_key.currentText()
                if not selected_key:
                        QMessageBox.warning(self, "Missing Key", f"Please select a Match Key for {os.path.basename(path)}")
                        return
                match_keys[path] = selected_key
        
        # Get Date/Amount
        date_col = self.combo_date.currentText()
        amount_col = self.combo_amount.currentText()

        self.proceed_to_mapping.emit(base_path, ref_files, self.file_column_config, match_keys, date_col, amount_col)
