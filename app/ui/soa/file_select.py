
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QListWidget, QListWidgetItem, QComboBox, QMessageBox,
    QProgressBar, QFrame, QGridLayout, QLineEdit, QRadioButton
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
    # Signal for advanced schema-based mapping (base_file, ref_files, col_config, match_keys, date_col, amount_col, custom_names)
    proceed_to_advanced_mapping = Signal(str, list, dict, dict, str, str, dict)
    # Signal to run reconciliation immediately (Skipping Mapping Screen)
    run_reconciliation_now = Signal(dict)
    go_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = [] # List of file paths
        self.file_column_config = {} # {file_path: [selected_columns]}
        self.ref_custom_names = {} # {file_path: custom_display_name}
        self.current_soa_path = None # Tracking the active SOA file
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
            if not self.current_soa_path:
                self.toggle_soa_file(self.files[0])
            self.update_role_labels()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Header
        self.lbl_header = QLabel("Select Files for SOA Reconciliation")
        self.lbl_header.setObjectName("HeaderTitle") # Use QSS for color/font
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
        self.file_list.setDragDropMode(QListWidget.InternalMove)
        self.file_list.setDefaultDropAction(PySide6.QtCore.Qt.MoveAction)
        self.file_list.model().rowsMoved.connect(self.on_rows_moved)
        layout.addWidget(self.file_list, 1) # Expand to fill vertical space

        # Connect base selection change to column loading
        # (Legacy combo_base removed, logic will move to row toggles)
        pass 

        # layout.addStretch() # Removed to allow file list to expand

        # layout.addStretch() # Removed to allow file list to expand

        # Navigation Footer
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton("Back")
        self.btn_back.clicked.connect(self.go_back.emit)
        nav_layout.addWidget(self.btn_back)
        nav_layout.addStretch()

        # Right-side button row (Advanced Mapping and Run Reconciliation side-by-side)
        right_buttons_widget = QWidget()
        right_row = QHBoxLayout(right_buttons_widget)
        right_row.setContentsMargins(0, 0, 0, 0)
        right_row.setSpacing(12)
        
        self.btn_advanced = QPushButton("ADVANCE MAPPING")
        self.btn_advanced.setCursor(Qt.PointingHandCursor)
        self.btn_advanced.setFixedHeight(42)
        self.btn_advanced.setStyleSheet("""
            QPushButton { 
                background-color: transparent; 
                border: 2px solid #9C27B0; 
                color: #BA68C8; 
                padding: 0 25px; 
                border-radius: 6px; 
                font-size: 13px;
                font-weight: bold; 
            } 
            QPushButton:hover { background-color: rgba(156, 39, 176, 0.1); border-color: #BA68C8; }
        """)
        self.btn_advanced.clicked.connect(self.on_advanced_mapping)
        right_row.addWidget(self.btn_advanced)
        
        self.btn_run_quick = QPushButton("RUN RECONCILIATION")
        self.btn_run_quick.setCursor(Qt.PointingHandCursor)
        self.btn_run_quick.setFixedHeight(42)
        self.btn_run_quick.setStyleSheet("""
            QPushButton { 
                background-color: #7B1FA2; 
                color: white; 
                border: none; 
                padding: 0 30px; 
                border-radius: 6px; 
                font-size: 14px;
                font-weight: bold; 
            } 
            QPushButton:hover { background-color: #8E24AA; }
        """)
        self.btn_run_quick.clicked.connect(self.on_run_click)
        right_row.addWidget(self.btn_run_quick)
        
        nav_layout.addWidget(right_buttons_widget)
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
            if not self.current_soa_path and self.files:
                self.toggle_soa_file(self.files[0])
            self.update_role_labels()

    def on_rows_moved(self, parent, start, end, destination, row):
        """Sync self.files when rows are moved via drag-and-drop and refresh widgets."""
        # 1. Update self.files list to match new order
        new_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            if path:
                new_files.append(path)
        self.files = new_files

        # 2. Re-link widgets (InternalMove loses setItemWidget mapping)
        # However, InternalMove in QListWidget usually just moves the item.
        # But setItemWidget often breaks. Let's force a rebuild for safety
        # or just ensure current state is correct.
        # Actually, a better way is to not use setItemWidget or to re-set it.
        # For QListWidget InternalMove, the widget is often destroyed.
        # So we MUST rebuild the list.
        self.rebuild_file_list()

    def rebuild_file_list(self):
        """Clear and rebuild the file list widget from self.files, preserving column configs."""
        self.file_list.clear()
        for path in self.files:
            self.add_file_to_ui(path)
        self.update_role_labels() # Ensure roles and placeholders are correct after rebuild

    def add_file_to_ui(self, path):
        # Create Item
        item = QListWidgetItem()
        self.file_list.addItem(item)
        
        # Create Widget for Item
        widget = QWidget()
        

        # ▲/▼ Reorder Buttons
        arrow_style = """
            QPushButton {
                background-color: transparent;
                color: #888;
                border: 1px solid #888;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
                padding: 2px;
                min-width: 24px;
                max-width: 24px;
                min-height: 22px;
                max-height: 22px;
            }
            QPushButton:hover { background-color: rgba(128,128,128,0.1); color: #BA68C8; border-color: #BA68C8; }
        """
        
        if not self.current_soa_path and path == self.files[0]:
            self.current_soa_path = path

        # Custom Radio-style logic (Role Selection)
        radio_soa = QRadioButton()
        radio_soa.setFixedSize(24, 24)
        radio_soa.setCursor(Qt.PointingHandCursor)
        radio_soa.setChecked(path == self.current_soa_path)
        radio_soa.toggled.connect(lambda checked, p=path: self.toggle_soa_file(p) if checked else None)
        radio_soa.setStyleSheet("""
            QRadioButton::indicator { width: 18px; height: 18px; border-radius: 9px; }
            QRadioButton::indicator:unchecked { border: 2px solid #9E9E9E; background: transparent; }
            QRadioButton::indicator:checked { border: 2px solid #4CAF50; background: #4CAF50; }
        """)
        
        # Date Selection (for SOA only)
        lbl_date = QLabel("Date:")
        lbl_date.setObjectName("SubTitle")
        lbl_date.setStyleSheet("font-size: 10px; margin-bottom: 0px;")
        combo_date = QComboBox()
        combo_date.setMinimumWidth(120)

        # Amount Selection (for SOA only)
        lbl_amount = QLabel("Amount:")
        lbl_amount.setObjectName("SubTitle")
        lbl_amount.setStyleSheet("font-size: 10px; margin-bottom: 0px;")
        combo_amount = QComboBox()
        combo_amount.setMinimumWidth(120)

        # Load Columns for Date/Amount
        try:
            from app.core.data_loader import DataLoader
            cols = DataLoader.load_file_headers(path)
            combo_date.addItems(cols)
            combo_amount.addItems(cols)
        except Exception as e:
            print(f"Error loading columns for {path}: {e}")

        # SOA Config Container
        soa_config_container = QWidget()
        soa_config_container.setFixedWidth(270)
        sp = soa_config_container.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        soa_config_container.setSizePolicy(sp)
        soa_config_container.setVisible(path == self.current_soa_path)
        soa_config_layout = QHBoxLayout(soa_config_container)
        soa_config_layout.setContentsMargins(0, 0, 0, 0)
        soa_config_layout.setSpacing(6)
        
        date_v_layout = QVBoxLayout()
        date_v_layout.setSpacing(2)
        date_v_layout.addWidget(lbl_date)
        date_v_layout.addWidget(combo_date)
        
        amount_v_layout = QVBoxLayout()
        amount_v_layout.setSpacing(2)
        amount_v_layout.addWidget(lbl_amount)
        amount_v_layout.addWidget(combo_amount)
        
        soa_config_layout.addLayout(date_v_layout)
        soa_config_layout.addLayout(amount_v_layout)

        # Custom Display Name (editable)
        edit_name = QLineEdit()
        edit_name.setPlaceholderText("Name")
        edit_name.setFixedWidth(120)
        # Style handles font and padding, colors come from QSS
        edit_name.setStyleSheet("QLineEdit { font-size: 12px; font-weight: bold; padding: 6px 8px; }")
        if path in self.ref_custom_names:
            edit_name.setText(self.ref_custom_names[path])
        edit_name.textChanged.connect(lambda text, p=path: self._on_custom_name_changed(p, text))
        
        # File Info Layout
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        lbl_name = QLabel(os.path.basename(path))
        # Remove hardcoded white color
        lbl_name.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(lbl_name)
        
        try:
            size_bytes = os.path.getsize(path)
            size_str = self.human_readable_size(size_bytes)
        except:
            size_str = "Unknown size"
        ext = os.path.splitext(path)[1].upper().replace(".", "")
        lbl_details = QLabel(f"{ext} File • {size_str}")
        lbl_details.setObjectName("SubTitle")
        lbl_details.setStyleSheet("font-size: 11px;")
        info_layout.addWidget(lbl_details)

        # Match Key / ID Selection
        title_text = "Master ID Column:" if path == self.current_soa_path else "Match Key to Master:"
        lbl_key = QLabel(title_text)
        lbl_key.setObjectName("SubTitle")
        lbl_key.setStyleSheet("font-size: 10px; font-weight: bold; color: #BBB;")
        combo_key = QComboBox()
        combo_key.setMinimumWidth(140)
        # No hardcoded colors — inherit from QSS theme
        try:
            from app.core.data_loader import DataLoader
            cols = DataLoader.load_file_headers(path)
            combo_key.addItems(cols)
        except Exception as e:
            print(f"Error loading columns for {path}: {e}")

        # Store widget references in item for retrieval
        item.setData(Qt.UserRole + 1, combo_key)
        item.setData(Qt.UserRole + 3, edit_name)
        item.setData(Qt.UserRole + 4, radio_soa)
        item.setData(Qt.UserRole + 5, soa_config_container)
        item.setData(Qt.UserRole + 6, combo_date)
        item.setData(Qt.UserRole + 7, combo_amount)
        
        # Configure Button
        btn_config = QPushButton("⚙ Configure Columns")
        btn_config.setToolTip("Select specific columns to use (Pivot Style)")
        btn_config.setCursor(Qt.PointingHandCursor)
        btn_config.setFixedWidth(170)
        if path in self.file_column_config:
            count = len(self.file_column_config[path])
            btn_config.setText(f"✔ Configured ({count} cols)")
            btn_config.setStyleSheet("QPushButton { background-color: #2e7d32; color: white; border: none; padding: 6px 12px; border-radius: 4px; } QPushButton:hover { background-color: #388e3c; }")
        else:
            btn_config.setStyleSheet("QPushButton { background-color: #3f51b5; color: white; border: none; padding: 6px 12px; border-radius: 4px; } QPushButton:hover { background-color: #5c6bc0; }")
        btn_config.clicked.connect(lambda checked=False, p=path, b=btn_config: self.open_column_config(p, b))

        # Match Key container widget (fixed col width)
        match_key_container = QWidget()
        match_key_container.setFixedWidth(155)
        match_key_layout_v = QVBoxLayout(match_key_container)
        match_key_layout_v.setContentsMargins(0, 0, 0, 0)
        match_key_layout_v.setSpacing(2)
        match_key_layout_v.addWidget(lbl_key)
        match_key_layout_v.addWidget(combo_key)
        
        # ── Layout Assembly – strict fixed-column grid ──────────────────
        # Use a QGridLayout so every row has the SAME column widths.
        # Col 0: radio (32)  Col 1: name edit (110)  Col 2: file info (stretch)
        # Col 3: soa date/amount panel (270, retained hidden)
        # Col 4: match key (155)  Col 5: configure btn (170)
        from PySide6.QtWidgets import QGridLayout, QSizePolicy as QSP
        grid = QGridLayout(widget)
        grid.setContentsMargins(10, 6, 10, 6)
        grid.setSpacing(10)

        # Fix column widths so they never flex
        grid.setColumnMinimumWidth(0, 32)
        grid.setColumnMinimumWidth(1, 110)
        grid.setColumnStretch(2, 1)        # file name stretches
        grid.setColumnMinimumWidth(3, 270) # date/amount panel — always same width
        grid.setColumnMinimumWidth(4, 155)
        grid.setColumnMinimumWidth(5, 170)

        # ── Wrap the file info layout in a plain QWidget ──
        info_container = QWidget()
        info_container.setLayout(info_layout)

        grid.addWidget(radio_soa,            0, 0, 2, 1, Qt.AlignVCenter)
        grid.addWidget(edit_name,            0, 1, 2, 1, Qt.AlignVCenter)
        grid.addWidget(info_container,       0, 2, 2, 1, Qt.AlignVCenter)
        grid.addWidget(soa_config_container, 0, 3, 2, 1, Qt.AlignVCenter)
        grid.addWidget(match_key_container,  0, 4, 2, 1, Qt.AlignVCenter)
        grid.addWidget(btn_config,           0, 5, 2, 1, Qt.AlignVCenter)

        item.setSizeHint(widget.sizeHint() +  PySide6.QtCore.QSize(0, 10))
        if item.sizeHint().height() < 80:
            item.setSizeHint(PySide6.QtCore.QSize(item.sizeHint().width(), 80))
        
        self.file_list.setItemWidget(item, widget)
        item.setData(Qt.UserRole, path)
        
        # Special logic for auto-detecting SOA columns
        if path == self.current_soa_path:
            self._auto_select_columns_for_path(path, combo_date, combo_amount)
        
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
            if path == self.current_soa_path:
                self.current_soa_path = self.files[0] if self.files else None
            self.rebuild_file_list()

    def _on_custom_name_changed(self, path, text):
        """Store custom name when user edits it."""
        text = text.strip()
        if text:
            self.ref_custom_names[path] = text
        elif path in self.ref_custom_names:
            del self.ref_custom_names[path]

    def toggle_soa_file(self, path):
        """Designate a file as the SOA (Base) file and update UI."""
        self.current_soa_path = path
        
        # Update all row widgets
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            p = item.data(Qt.UserRole)
            btn_role = item.data(Qt.UserRole + 4)
            soa_container = item.data(Qt.UserRole + 5)
            
            if btn_role:
                # Standard QRadioButton handles its own check state via mutually exclusive signals
                # but we need to ensure consistency if we set it programmatically
                btn_role.blockSignals(True)
                btn_role.setChecked(p == path)
                btn_role.blockSignals(False)
            
            if p == path:
                if soa_container: soa_container.setVisible(True)
                # Ensure columns are auto-detected for the new SOA
                combo_date = item.data(Qt.UserRole + 6)
                combo_amount = item.data(Qt.UserRole + 7)
                if combo_date and combo_amount:
                    self._auto_select_columns_for_path(p, combo_date, combo_amount)
            else:
                if soa_container: soa_container.setVisible(False)
        
        self.update_role_labels()

    def update_role_labels(self):
        """Update the custom name defaults based on current SOA file."""
        ref_counter = 1
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            edit_name = item.data(Qt.UserRole + 3)
            path = item.data(Qt.UserRole)
            if not edit_name: continue
            
            if path == self.current_soa_path:
                if not edit_name.text().strip():
                    edit_name.setPlaceholderText("SOA")
            else:
                default_name = f"Ref{ref_counter}"
                if not edit_name.text().strip():
                    edit_name.setPlaceholderText(default_name)
                ref_counter += 1

    def _auto_select_columns_for_path(self, path, combo_date, combo_amount):
        """Fuzzy match date and amount columns for a specific file."""
        try:
            from app.core.data_loader import DataLoader
            cols = DataLoader.load_file_headers(path)
            
            date_keywords = ['date', 'dt', 'dated', 'invoice date', 'inv date', 'receive date']
            for i, col in enumerate(cols):
                if any(k in col.lower() for k in date_keywords):
                    combo_date.setCurrentIndex(i)
                    break
            
            amount_keywords = ['amount', 'amt', 'open amount', 'invoice amount', 'total', 'value', 'balance']
            for i, col in enumerate(cols):
                if any(k in col.lower() for k in amount_keywords):
                    combo_amount.setCurrentIndex(i)
                    break
        except:
            pass

    def on_run_click(self):
        """Gather current UI configuration and emit run signal directly."""
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add at least one file.")
            return
        
        base_path = self.current_soa_path
        if not base_path:
             QMessageBox.warning(self, "No SOA File", "Please designate one file as 'SOA'.")
             return

        ref_files = [f for f in self.files if f != base_path]
        if not ref_files:
            QMessageBox.warning(self, "No Reference Files", "Please add at least one reference file.")
            return

        # Gather Match Keys/Date/Amount from Rows
        match_keys = {}
        base_match_key = None
        date_col = None
        amount_col = None
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            
            if path and combo_key:
                val = combo_key.currentText()
                if not val:
                    QMessageBox.warning(self, "Missing Key", f"Match key missing for {os.path.basename(path)}")
                    return
                match_keys[path] = val
                if path == base_path:
                    base_match_key = val
                    combo_date = item.data(Qt.UserRole + 6)
                    combo_amount = item.data(Qt.UserRole + 7)
                    if combo_date and combo_amount:
                        date_col = combo_date.currentText()
                        amount_col = combo_amount.currentText()

        if not base_match_key or not date_col or not amount_col:
             QMessageBox.warning(self, "Incomplete Config", "Please check SOA match, date, and amount columns.")
             return

        # Build Rules
        rules = {}
        try:
            from app.core.data_loader import DataLoader
            for ref_path in ref_files:
                match_col = match_keys.get(ref_path)
                return_cols = list(self.file_column_config.get(ref_path, DataLoader.load_file_headers(ref_path)))
                rules[ref_path] = {"match_col": match_col, "return_cols": return_cols, "match_type": "exact"}
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to prepare configuration: {e}")
            return

        # Ref Custom Names
        ref_custom_names = {}
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            edit_name = item.data(Qt.UserRole + 3)
            if path and edit_name:
                name = edit_name.text().strip() or edit_name.placeholderText()
                ref_custom_names[path] = name

        config = {
            "rules": rules, "date_col": date_col, "amount_col": amount_col,
            "master_match_col": base_match_key, "schema_config": [], "match_keys": match_keys,
            "base_file": base_path, "column_config": self.file_column_config, "ref_custom_names": ref_custom_names
        }
        self.run_reconciliation_now.emit(config)

    def on_advanced_mapping(self):
        """Prepare data and switch to the advanced schema mapper."""
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add at least one file.")
            return
        base_path = self.current_soa_path
        if not base_path:
             QMessageBox.warning(self, "No SOA File", "Please designate one file as 'SOA'.")
             return
        
        ref_files = [f for f in self.files if f != base_path]
        match_keys = {}
        date_col = None
        amount_col = None

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            if path and combo_key:
                val = combo_key.currentText()
                if not val:
                    QMessageBox.warning(self, "Missing Key", f"Match key missing for {os.path.basename(path)}")
                    return
                match_keys[path] = val
                if path == base_path:
                    combo_date = item.data(Qt.UserRole + 6)
                    combo_amount = item.data(Qt.UserRole + 7)
                    if combo_date and combo_amount:
                        date_col = combo_date.currentText()
                        amount_col = combo_amount.currentText()

        # Ref Custom Names
        ref_custom_names = {}
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            edit_name = item.data(Qt.UserRole + 3) # Custom name edit field
            if path and edit_name:
                name = edit_name.text().strip() or edit_name.placeholderText()
                ref_custom_names[path] = name

        self.proceed_to_advanced_mapping.emit(base_path, ref_files, self.file_column_config, match_keys, date_col, amount_col, ref_custom_names)
