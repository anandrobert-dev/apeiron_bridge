from .welcome import WelcomeScreen
from .file_select import FileSelectScreen
from .mapping import MappingScreen
from .results import ResultsScreen
from ..core.engine import MatchingEngine
from ..core.soa_engine import SOAEngine
from app.core.data_loader import DataLoader
from PySide6.QtWidgets import QMessageBox, QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QApplication
from PySide6.QtGui import QIcon
from PySide6.QtCore import QFile, QTextStream
import sys
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Apeiron Bridge")
        self.resize(1000, 700)
        
        # Absolute path for resources
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icon_path = os.path.join(base_dir, "resources", "icon.png")
        self.setWindowIcon(QIcon(icon_path))

        # Central Widget & Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.layout = QVBoxLayout(central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Stacked Widget for Page Navigation
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # Initialize Screens
        self.init_ui()

    def init_ui(self):
        # 0. Welcome Screen
        self.welcome_screen = WelcomeScreen(self)
        self.stack.addWidget(self.welcome_screen)
        
        # 1. File Selection
        self.file_select_screen = FileSelectScreen(self)
        self.stack.addWidget(self.file_select_screen)

        # 2. Mapping Screen
        self.mapping_screen = MappingScreen(self)
        self.stack.addWidget(self.mapping_screen)
        
        # 3. Results Screen
        self.results_screen = ResultsScreen(self)
        self.stack.addWidget(self.results_screen)

        # Set default page
        self.stack.setCurrentWidget(self.welcome_screen)

        # Navigation Signals
        self.welcome_screen.btn_soa.clicked.connect(lambda: self.navigate_to(1))
        self.welcome_screen.btn_multi.clicked.connect(lambda: self.navigate_to(1))
        
        self.file_select_screen.go_back.connect(lambda: self.navigate_to(0))
        self.file_select_screen.proceed_to_mapping.connect(self.goto_mapping)
        
        self.mapping_screen.go_back.connect(lambda: self.navigate_to(1))
        self.mapping_screen.run_reco.connect(self.run_reconciliation)
        
        self.results_screen.go_home.connect(lambda: self.navigate_to(0))

    def navigate_to(self, index):
        self.stack.setCurrentIndex(index)

    def goto_mapping(self, base_file, ref_files):
        """Loads data columns and switches to Mapping Screen."""
        try:
            # Load Base File Columns - Optimize by not reloading if mostly same
            # For now, simplistic reload
            self.current_base_file = base_file
            self.current_ref_files = ref_files
            
            df_base = DataLoader.load_file(base_file)
            base_cols = list(df_base.columns.astype(str))
            
            ref_cols_dict = {}
            for ref in ref_files:
                df_ref = DataLoader.load_file(ref)
                ref_cols_dict[ref] = list(df_ref.columns.astype(str))
            
            self.mapping_screen.set_data(base_file, ref_files, base_cols, ref_cols_dict)
            self.navigate_to(2)
            
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Files", f"Could not load file data:\n{str(e)}")

    def run_reconciliation(self, config):
        """
        Executes the reconciliation process using SOAEngine.
        config: dict with 'rules', 'date_col', 'amount_col'
        """
        try:
            print(f"DEBUG: Running Reconciliation with config: {config}")
            
            mapping_rules = config.get("rules", {})
            date_col = config.get("date_col")
            amount_col = config.get("amount_col")

            if not mapping_rules:
                QMessageBox.warning(self, "Reconciliation Error", "No mapping rules provided.")
                return

            # Prepare data for SOAEngine
            first_rule = list(mapping_rules.values())[0]
            soa_match_col = first_rule["base_col"] 
            
            ref_configs = []
            import pandas as pd
            
            for ref_name, rule in mapping_rules.items():
                ref_path = None
                for path in self.current_ref_files:
                     if os.path.basename(path) == ref_name:
                         ref_path = path
                         break
                
                if ref_path:
                    try:
                        if ref_path.endswith('.csv'):
                            df = pd.read_csv(ref_path)
                        else:
                            df = pd.read_excel(ref_path)
                        
                        return_cols = list(df.columns)
                        if rule["ref_col"] in return_cols:
                            return_cols.remove(rule["ref_col"]) 
                            
                        ref_configs.append((df, rule["ref_col"], return_cols, ref_name))
                    except Exception as e:
                        print(f"Error loading {ref_path}: {e}")
                        QMessageBox.critical(self, "File Load Error", f"Error loading reference file {ref_name}:\n{str(e)}")
                        return

            # Load Base DF
            soa_path = self.current_base_file
            try:
                 if soa_path.endswith('.csv'):
                     soa_df = pd.read_csv(soa_path)
                 else:
                     soa_df = pd.read_excel(soa_path)
            except Exception as e:
                 print(f"Error loading SOA {soa_path}: {e}")
                 QMessageBox.critical(self, "File Load Error", f"Error loading base file {os.path.basename(soa_path)}:\n{str(e)}")
                 return

            # Initialize Engine
            engine = SOAEngine(soa_df, soa_match_col, date_col, amount_col, ref_configs)
            result_df, saved_path = engine.run()
            
            print(f"DEBUG: Reconciliation Complete. Saved to {saved_path}")
            
            # Show Results
            self.results_screen.display_results(result_df)
            self.stack.setCurrentWidget(self.results_screen)
            
            if saved_path:
                 QMessageBox.information(self, "Reconciliation Complete", f"Results saved to:\n{saved_path}")

        except Exception as e:
            QMessageBox.critical(self, "Reconciliation Failed", f"An error occurred:\n{str(e)}")

def load_stylesheet():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    style_path = os.path.join(base_dir, "resources", "styles.qss")
    
    file = QFile(style_path)
    if file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(file)
        return stream.readAll()
    return ""

if __name__ == "__main__":
    try:
        print("DEBUG: Starting application...")
        app = QApplication(sys.argv)
        app.setStyleSheet(load_stylesheet())
        
        print("DEBUG: Creating MainWindow...")
        window = MainWindow()
        window.show()
        print("DEBUG: Window shown. Entering event loop.")
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
