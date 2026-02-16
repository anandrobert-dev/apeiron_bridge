
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFileDialog, QListWidget, QListWidgetItem, QComboBox, QMessageBox, QFrame
)
from PySide6.QtCore import Qt, Signal
import os

class FileSelectScreen(QWidget):
    """
    Screen for adding/removing files and selecting the Base file.
    """
    # Signal to proceed to Mapping Screen with loaded data
    # args: (base_file_path, list_of_ref_file_paths)
    proceed_to_mapping = Signal(str, list)
    go_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = [] # List of file paths
        self.setAcceptDrops(True) # Enable Drag & Drop
        self.init_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid_extensions = ['.xlsx', '.xls', '.csv']
        
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
        header = QLabel("Select Files for Reconciliation")
        header.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(header)

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
        layout.addWidget(self.file_list)

        # Base File Selection
        base_selection_layout = QHBoxLayout()
        lbl_base = QLabel("Select Base File (SOA):")
        self.combo_base = QComboBox()
        self.combo_base.setFixedWidth(400)
        
        base_selection_layout.addWidget(lbl_base)
        base_selection_layout.addWidget(self.combo_base)
        base_selection_layout.addStretch()
        layout.addLayout(base_selection_layout)

        layout.addStretch()

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

    def add_file_to_ui(self, path):
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path) # Store full path
        self.file_list.addItem(item)

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
        
        self.proceed_to_mapping.emit(base_path, ref_files)
