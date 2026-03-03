
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QAbstractItemView, QLineEdit, QFrame
)
from PySide6.QtCore import Qt, Signal
import os

class ColumnConfigDialog(QDialog):
    """
    Dialog for selecting which columns to use from a file.
    Features: Drag & Drop between "Available" and "Selected" lists.
    """
    def __init__(self, filename, all_columns, initial_selection=None, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.all_columns = all_columns
        # If no initial selection, start with empty selection (user must pick)
        # OR start with all? User requested "Bucket option", implying start empty usually.
        # Let's start empty for "Pivot" feel, or maybe all in "Available".
        self.selected_columns = initial_selection if initial_selection is not None else []
        
        self.setWindowTitle(f"Configure Columns: {os.path.basename(filename)}")
        self.resize(700, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"Drag and drop columns to 'Selected' for: {os.path.basename(self.filename)}")
        header.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header)
        
        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search columns...")
        self.txt_search.textChanged.connect(self.filter_columns)
        layout.addWidget(self.txt_search)

        # Content Area (Two Lists)
        content_layout = QHBoxLayout()
        
        # --- Left: Available Columns ---
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Available Columns"))
        
        self.list_available = QListWidget()
        self.list_available.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_available.setDragEnabled(True)
        self.list_available.setAcceptDrops(True)
        self.list_available.setDropIndicatorShown(True)
        self.list_available.setDefaultDropAction(Qt.MoveAction)
        
        left_layout.addWidget(self.list_available)
        content_layout.addLayout(left_layout)
        
        # --- Center: Buttons (Optional, for non-drag users) ---
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        self.btn_add = QPushButton("→")
        self.btn_add.setToolTip("Add Selected")
        self.btn_add.clicked.connect(self.move_to_selected)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_remove = QPushButton("←")
        self.btn_remove.setToolTip("Remove Selected")
        self.btn_remove.clicked.connect(self.move_to_available)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        content_layout.addLayout(btn_layout)

        # --- Right: Selected Columns ---
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Selected Columns (Mapped)"))
        
        self.list_selected = QListWidget()
        self.list_selected.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_selected.setDragEnabled(True)
        self.list_selected.setAcceptDrops(True)
        self.list_selected.setDropIndicatorShown(True)
        self.list_selected.setDefaultDropAction(Qt.MoveAction)
        
        right_layout.addWidget(self.list_selected)
        content_layout.addLayout(right_layout)
        
        layout.addLayout(content_layout)

        # Footer
        footer = QHBoxLayout()
        
        self.lbl_count = QLabel("")
        footer.addWidget(self.lbl_count)
        
        footer.addStretch()
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        footer.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self.save_and_close)
        footer.addWidget(self.btn_save)
        
        layout.addLayout(footer)
        
        # Populate Lists
        self.populate_lists()
        
    def populate_lists(self):
        self.list_available.clear()
        self.list_selected.clear()
        
        # Selected
        for col in self.selected_columns:
            if col in self.all_columns:
                self.list_selected.addItem(col)
        
        # Available (All minus Selected)
        for col in self.all_columns:
            if col not in self.selected_columns:
                self.list_available.addItem(col)
                
        self.update_counts()

    def filter_columns(self):
        query = self.txt_search.text().lower()
        # Only filtering Available list for now
        for i in range(self.list_available.count()):
            item = self.list_available.item(i)
            item.setHidden(query not in item.text().lower())

    def move_to_selected(self):
        items = self.list_available.selectedItems()
        for item in items:
            self.list_available.takeItem(self.list_available.row(item))
            self.list_selected.addItem(item.text())
        self.update_counts()

    def move_to_available(self):
        items = self.list_selected.selectedItems()
        for item in items:
            self.list_selected.takeItem(self.list_selected.row(item))
            self.list_available.addItem(item.text())
        self.update_counts()

    def update_counts(self):
        sel = self.list_selected.count()
        avail = self.list_available.count()
        self.lbl_count.setText(f"Selected: {sel} | Available: {avail}")

    def save_and_close(self):
        # Gather selected columns
        self.selected_columns = [self.list_selected.item(i).text() for i in range(self.list_selected.count())]
        self.accept()
