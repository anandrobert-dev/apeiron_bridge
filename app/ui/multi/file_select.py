
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QListWidget, QListWidgetItem, QComboBox, QMessageBox,
    QProgressBar, QFrame, QGridLayout
)
import PySide6.QtCore
from PySide6.QtCore import Qt, Signal
import os

class ReorderableListWidget(QListWidget):
    """A QListWidget that supports drag-and-drop reordering and Alt+Up/Down for keyboard reordering."""
    
    itemMoved = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        if (modifiers == Qt.AltModifier or modifiers == Qt.ControlModifier):
            if event.key() == Qt.Key_Up:
                self.move_current_item(-1)
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                self.move_current_item(1)
                event.accept()
                return
        super().keyPressEvent(event)

    def move_current_item(self, offset):
        row = self.currentRow()
        if row < 0:
            return
        new_row = row + offset
        if 0 <= new_row < self.count():
            # In QListWidget, takeItem removes the custom widget set by setItemWidget
            # Therefore we just signal to the parent to rebuild the list
            paths = []
            for i in range(self.count()):
                paths.append(self.item(i).data(Qt.UserRole))
            
            # Swap
            paths[row], paths[new_row] = paths[new_row], paths[row]
            
            # Emit signal
            self.itemMoved.emit(paths, new_row)
            
    def dropEvent(self, event):
        super().dropEvent(event)
        # Drop event also loses widgets unfortunately for InternalMove if setWidget is used
        # Rebuild whole list
        paths = []
        for i in range(self.count()):
            paths.append(self.item(i).data(Qt.UserRole))
            
        self.itemMoved.emit(paths, self.currentRow())

class MultiFileSelectScreen(QWidget):
    """
    Screen for adding/removing files and selecting the Anchor file for Multi-File Comparison.
    """
    # Signal to proceed to Mapping Screen with loaded data
    # args: (base_file_path, list_of_ref_file_paths, config_json, match_keys)
    proceed_to_mapping = Signal(str, list, dict, dict)
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
        self.lbl_header = QLabel("Select Files for Multi-File Comparison")
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
        self.file_list = ReorderableListWidget()
        self.file_list.setObjectName("Card") # Style like a card
        # Hint for keyboard reordering
        self.file_list.setToolTip("Drag and drop to reorder, or use Alt+Up/Down on keyboard")
        self.file_list.itemMoved.connect(self.on_file_reordered)
        layout.addWidget(self.file_list, 1) # Expand to fill vertical space

        # Base File Selection
        base_selection_layout = QHBoxLayout()
        self.lbl_base_select = QLabel("Primary Reference (Anchor):")
        self.combo_base = QComboBox()
        self.combo_base.setFixedWidth(400)
        
        base_selection_layout.addWidget(self.lbl_base_select)
        base_selection_layout.addWidget(self.combo_base)
        base_selection_layout.addStretch()
        layout.addLayout(base_selection_layout)

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

    def on_file_reordered(self, ordered_paths, select_row):
        """Rebuilds the list to restore custom widgets that QListWidget drops on move."""
        # 1. Capture current Match Keys before clearing
        current_keys = {}
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            if path and combo_key:
                current_keys[path] = combo_key.currentText()
                
        # 2. Clear and reset order
        self.file_list.clear()
        self.files = ordered_paths
        
        # 3. Rebuild
        for path in self.files:
            self.add_file_to_ui(path)
            
        # 4. Restore selections
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            if path in current_keys and combo_key:
                idx = combo_key.findText(current_keys[path])
                if idx >= 0:
                    combo_key.setCurrentIndex(idx)
                    
        # 5. Set focus
        if 0 <= select_row < self.file_list.count():
            self.file_list.setCurrentRow(select_row)

    def add_file_to_ui(self, path):
        # Create Item
        item = QListWidgetItem()
        self.file_list.addItem(item)
        
        # Create Widget for Item (Label + Match Key + Config Button)
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        
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
        
        # layout.addLayout(info_layout) # Do not add directly, wrap below
        # layout.addStretch()

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

        # Store combo reference in item for retrieval
        item.setData(Qt.UserRole + 1, combo_key) 
        
        # Configure Button
        btn_config = QPushButton("⚙ Configure Columns")
        btn_config.setToolTip("Select specific columns to use (Pivot Style)")
        btn_config.setCursor(Qt.PointingHandCursor)
        # Default Style (Blue)
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
        
        # Add to Layout with spacing
        # Structure: [ File Info (Stretch) ] [ Match Key (Fixed 250px) ] [ Config Button (Fixed) ]
        
        match_key_container = QWidget()
        match_key_container.setFixedWidth(250)
        match_key_layout = QVBoxLayout(match_key_container)
        match_key_layout.setContentsMargins(0, 0, 0, 0)
        match_key_layout.setSpacing(4)
        match_key_layout.addWidget(lbl_key)
        match_key_layout.addWidget(combo_key)
        
        layout.addLayout(info_layout, 1) # Stretch to fill space
        layout.addSpacing(20)
        layout.addWidget(match_key_container)
        layout.addSpacing(20)
        layout.addWidget(btn_config)
        
        # Determine Row Height based on content (approx 70px is good for this density)
        widget.setLayout(layout)
        item.setSizeHint(widget.sizeHint() +  PySide6.QtCore.QSize(0, 10)) # Add some breathing room vertically
        if item.sizeHint().height() < 70:
            item.setSizeHint(PySide6.QtCore.QSize(item.sizeHint().width(), 70))
        
        # Set Widget
        self.file_list.setItemWidget(item, widget)
        # Store full path in item user role still useful for removal
        item.setData(Qt.UserRole, path)

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

    def update_base_combo(self):
        current_base = self.combo_base.currentText()
        self.combo_base.clear()
        for path in self.files:
            self.combo_base.addItem(os.path.basename(path), path)
        
        # Restore selection if possible
        index = self.combo_base.findText(current_base)
        if index >= 0:
            self.combo_base.setCurrentIndex(index)

    # set_mode removed as this class is now strictly MULTI

    def on_next(self):
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add at least one file.")
            return
        
        base_path = self.combo_base.currentData()
        if not base_path:
             QMessageBox.warning(self, "No Base File", "Please select a Base file.")
             return

        # Collect Match Keys and Ref Files in UI order
        ref_files = []
        match_keys = {} # {file_path: selected_column}
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            path = item.data(Qt.UserRole)
            combo_key = item.data(Qt.UserRole + 1)
            
            if path and path != base_path and path not in ref_files:
                ref_files.append(path)
            
            if path and combo_key:
                selected_key = combo_key.currentText()
                if not selected_key:
                        QMessageBox.warning(self, "Missing Key", f"Please select a Match Key for {os.path.basename(path)}")
                        return
                match_keys[path] = selected_key

        self.proceed_to_mapping.emit(base_path, ref_files, self.file_column_config, match_keys)
