import sys
import os
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

def main():
    try:
        app = QApplication(sys.argv)
        
        # Initialize and show main window
        window = MainWindow()
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
