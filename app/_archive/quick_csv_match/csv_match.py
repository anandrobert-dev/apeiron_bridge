from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Signal, Qt

class QuickMatchScreen(QWidget):
    """
    Placeholder screen for Quick CSV Match.
    This demonstrates the separation of concerns - this code is completely isolated.
    """
    go_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        
        lbl_title = QLabel("Quick CSV Match")
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF9800;")
        layout.addWidget(lbl_title)
        
        lbl_desc = QLabel("This feature is currently under development.\nIt is located in app/ui/quick_match/csv_match.py")
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setStyleSheet("font-size: 16px; color: #DDD; margin-top: 10px;")
        layout.addWidget(lbl_desc)
        
        btn_back = QPushButton("Go Back")
        btn_back.setFixedWidth(200)
        btn_back.clicked.connect(self.go_back.emit)
        layout.addWidget(btn_back)
