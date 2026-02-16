
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile, QTextStream
from app.ui.main_window import MainWindow

def load_stylesheet():
    """Loads the QSS file from resources."""
    # Ensure we are looking in the context of the running script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "resources/styles.qss")
    
    file = QFile(file_path)
    if file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        return stream.readAll()
    else:
        print(f"Warning: Could not load stylesheet from {file_path}")
        return ""

def main():
    try:
        app = QApplication(sys.argv)
        
        # Apply Stylesheet
        stylesheet = load_stylesheet()
        if stylesheet:
            app.setStyleSheet(stylesheet)
        
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
