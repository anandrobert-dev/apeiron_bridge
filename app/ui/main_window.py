from .welcome import WelcomeScreen
from .welcome import WelcomeScreen
from app.ui.soa.file_select import SOAFileSelectScreen
from app.ui.soa.mapping import SOAMappingScreen
from app.ui.multi.file_select import MultiFileSelectScreen
from app.ui.multi.mapping import MultiMappingScreen
from app.ui.quick_match.csv_match import QuickMatchScreen
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
        
        # State Data
        self.current_base_file = None
        self.current_ref_files = []
        self.current_column_config = {}
        self.reco_mode = "SOA"

    def init_ui(self):
        # 0. Welcome Screen
        self.welcome_screen = WelcomeScreen(self)
        self.stack.addWidget(self.welcome_screen)
        
        # 1. SOA Screens
        self.soa_file_select = SOAFileSelectScreen(self)
        self.stack.addWidget(self.soa_file_select)
        
        self.soa_mapping = SOAMappingScreen(self)
        self.stack.addWidget(self.soa_mapping)
        
        # 2. Multi Screens
        self.multi_file_select = MultiFileSelectScreen(self)
        self.stack.addWidget(self.multi_file_select)
        
        self.multi_mapping = MultiMappingScreen(self)
        self.stack.addWidget(self.multi_mapping)

        # 3. Quick Match
        self.quick_match_screen = QuickMatchScreen(self)
        self.stack.addWidget(self.quick_match_screen)
        
        # 4. Results Screen
        self.results_screen = ResultsScreen(self)
        self.stack.addWidget(self.results_screen)

        # Set default page
        self.stack.setCurrentWidget(self.welcome_screen)

        # Navigation Signals
        # Welcome -> Modes
        self.welcome_screen.btn_soa.clicked.connect(self.start_soa)
        self.welcome_screen.btn_multi.clicked.connect(self.start_multi)
        self.welcome_screen.btn_csv.clicked.connect(self.start_quick_match)
        
        # SOA Flow
        self.soa_file_select.go_back.connect(lambda: self.navigate_to_widget(self.welcome_screen))
        self.soa_file_select.proceed_to_mapping.connect(self.goto_soa_mapping)
        self.soa_file_select.run_reconciliation_now.connect(self.run_reconciliation)
        
        self.soa_mapping.go_back.connect(lambda: self.navigate_to_widget(self.soa_file_select))
        self.soa_mapping.run_reco.connect(self.run_reconciliation)
        
        # Multi Flow
        self.multi_file_select.go_back.connect(lambda: self.navigate_to_widget(self.welcome_screen))
        self.multi_file_select.proceed_to_mapping.connect(self.goto_multi_mapping)
        
        self.multi_mapping.go_back.connect(lambda: self.navigate_to_widget(self.multi_file_select))
        self.multi_mapping.run_reco.connect(self.run_reconciliation)
        
        # Quick Match Flow
        self.quick_match_screen.go_back.connect(lambda: self.navigate_to_widget(self.welcome_screen))
        
        # Results Flow
        self.results_screen.go_home.connect(lambda: self.navigate_to_widget(self.welcome_screen))
        # Results Back: Needs to go back to correct mapping screen. 
        # For now, let's just go home or check mode.
        self.results_screen.go_back.connect(self.go_back_from_results)

    def navigate_to_widget(self, widget):
        self.stack.setCurrentWidget(widget)

    def start_soa(self):
        """Starts SOA Reconciliation Workflow."""
        self.reco_mode = "SOA"
        # Reset screens if needed? For now just nav.
        self.navigate_to_widget(self.soa_file_select)
        
    def start_multi(self):
        """Starts Multi-File Comparison Workflow."""
        self.reco_mode = "MULTI"
        self.navigate_to_widget(self.multi_file_select)

    def start_quick_match(self):
        """Starts Quick CSV Match Workflow."""
        self.reco_mode = "QUICK"
        self.navigate_to_widget(self.quick_match_screen)

    def go_back_from_results(self):
        if hasattr(self, 'reco_mode') and self.reco_mode == "MULTI":
            self.navigate_to_widget(self.multi_mapping)
        else:
            self.navigate_to_widget(self.soa_mapping)

    def goto_soa_mapping(self, base_file, ref_files, column_config=None, match_keys=None, date_col=None, amount_col=None):
        """Loads data and switches to SOA Mapping Screen."""
        self._load_and_goto_mapping(self.soa_mapping, base_file, ref_files, column_config, match_keys, date_col, amount_col)

    def goto_multi_mapping(self, base_file, ref_files, column_config=None, match_keys=None):
        """Loads data and switches to Multi Mapping Screen."""
        self._load_and_goto_mapping(self.multi_mapping, base_file, ref_files, column_config, match_keys)

    def _load_and_goto_mapping(self, target_screen, base_file, ref_files, column_config=None, match_keys=None, date_col=None, amount_col=None):
        try:
            self.current_base_file = base_file
            self.current_ref_files = ref_files
            self.current_column_config = column_config or {}
            
            # Load Base File
            base_usecols = self.current_column_config.get(base_file)
            df_base = DataLoader.load_file(base_file, usecols=base_usecols)
            base_cols = list(df_base.columns.astype(str))
            
            # Load Ref Files
            ref_cols_dict = {}
            for ref in ref_files:
                ref_usecols = self.current_column_config.get(ref)
                df_ref = DataLoader.load_file(ref, usecols=ref_usecols)
                ref_cols_dict[ref] = list(df_ref.columns.astype(str))
            
            # SOA Screen accepts extra args, Multi screen might not (but kwargs safe if we check target type or just pass)
            # Actually, MultiMappingScreen set_data signature is standard: (base, ref, base_cols, ref_cols, match_keys)
            # SOAMappingScreen set_data signature is new: (..., date_col, amount_col, file_column_config)
            
            if isinstance(target_screen, SOAMappingScreen):
                target_screen.set_data(base_file, ref_files, base_cols, ref_cols_dict, match_keys, date_col, amount_col, self.current_column_config)
            else:
                target_screen.set_data(base_file, ref_files, base_cols, ref_cols_dict, match_keys)
            self.navigate_to_widget(target_screen)
            
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Files", f"Could not load file data:\n{str(e)}")

    def run_reconciliation(self, config):
        """
        Executes the reconciliation process using SOAEngine.
        config: dict with 'rules', 'date_col', 'amount_col'
        Rules format: {ref_full_path: {match_col, return_cols, match_type}}
        """
        try:
            print(f"DEBUG: Running Reconciliation with config: {config}")
            
            mapping_rules = config.get("rules", {})
            date_col = config.get("date_col")
            amount_col = config.get("amount_col")
            schema_config = config.get("schema_config", [])

            if not mapping_rules and not schema_config:
                QMessageBox.warning(self, "Reconciliation Error", "No mapping rules provided.")
                return

            # In MULTI mode, mapping_rules is empty and bypassed. Generate mock rules to drive engine data loops.
            if not mapping_rules and schema_config:
                for ref_path in self.current_ref_files:
                    mapping_rules[ref_path] = {
                        "match_col": config.get("match_keys", {}).get(ref_path),
                        "return_cols": []
                    }

            # The SOA match column comes from the base column selected in the left panel.
            # In MULTI mode, it comes from the explicitly selected "Master Match Key".
            # In SOA mode (or fallback), we default to the first column or user selection logic.
            
            soa_match_col = config.get("master_match_col")
            
            if not soa_match_col:
                # Fallback: Check if match_keys has it for the base file
                match_keys = config.get("match_keys", {})
                if self.current_base_file in match_keys:
                    soa_match_col = match_keys[self.current_base_file]
                else:
                    # Original Fallback (Only works if we can access the active screen safely, or just fail)
                    # For simplicty in refactor, if it's not in config or match_keys, we warn.
                    # But SOA mode might pass it via rules? No, config.
                    
                    # If we are in SOA mode, we might grab from screen if absolutely needed?
                    # Better to ensure SOA Mapping passes it in `config`.
                    # SOA Mapping passes `master_match_col` as None usually, relies on auto-detect?
                    # No, logic was "SOA uses first col or internal logic".
                    # Let's try to grab from match_keys again or warn.
                    QMessageBox.warning(self, "Reconciliation Error", "No base match column identified.")
                    return
            
            # Get Schema Config
            schema_config = config.get("schema_config", [])
            
            # Helper to consolidate required columns for schema
            # {ref_basename: set(columns)}
            schema_cols_map = {}
            if schema_config:
                for field in schema_config:
                    mappings = field.get("mappings", {})
                    for ref_path, col_name in mappings.items():
                        if col_name:
                            ref_base = os.path.basename(ref_path)
                            if ref_base not in schema_cols_map:
                                schema_cols_map[ref_base] = set()
                            schema_cols_map[ref_base].add(col_name)

            ref_configs = []
            path_to_name_map = {}
            import pandas as pd
            
            for ref_path, rule in mapping_rules.items():
                ref_display = os.path.basename(ref_path)
                match_col = rule.get("match_col")
                
                # Override with match_keys if present (User selected in FileScreen)
                match_keys = config.get("match_keys", {})
                if ref_path in match_keys:
                    match_col = match_keys[ref_path]

                return_cols = rule.get("return_cols", [])
                
                # Add Schema Columns to Return Columns (if not already present)
                # We match by basename (since schema stores paths but mapping iterates paths)
                # Actually mapping iterates full paths, schema stores full paths in `mappings` keys.
                # Wait, schema uses ref_path as key?
                # In schema_config.py: mappings[ref_path] = val
                # So we can match directly by path!
                
                # Let's re-verify schema usage of path vs basename.
                # In SchemaDialog, I used `ref_path` as key.
                # So we can look up directly.
                
                schema_required = set()
                for field in schema_config:
                    mappings = field.get("mappings", {})
                    if ref_path in mappings and mappings[ref_path]:
                        schema_required.add(mappings[ref_path])
                
                # Merge into return_cols (avoid duplicates)
                # return_cols is a list, let's make it unique
                current_set = set(return_cols)
                for c in schema_required:
                    if c not in current_set and c != match_col:
                        return_cols.append(c)
                        current_set.add(c)
                
                if os.path.exists(ref_path):
                    try:
                        # Load Ref Data (respecting config)
                        current_col_config = config.get("column_config", self.current_column_config)
                        ref_usecols = current_col_config.get(ref_path)
                        
                        # CRITICAL FIX: Ensure match_col is loaded even if user unchecked it
                        if ref_usecols is not None and match_col and match_col not in ref_usecols:
                            ref_usecols = list(ref_usecols)
                            ref_usecols.append(match_col)
                            
                        df = DataLoader.load_file(ref_path, usecols=ref_usecols)
                        
                        # Use Ref1/Ref2 for column prefixing (short, clean headers)
                        ref_name = f"Ref{len(ref_configs) + 1}"
                        path_to_name_map[ref_path] = ref_name
                        ref_configs.append((df, match_col, return_cols, ref_name))
                    except Exception as e:
                        print(f"Error loading {ref_path}: {e}")
                        error_msg = f"Error loading reference file {ref_display}:\n{str(e)}"
                        QMessageBox.critical(self, "File Load Error", error_msg)
                        return
                else:
                    QMessageBox.critical(self, "File Not Found", f"Reference file not found:\n{ref_path}")
                    return

            # Load Base DF (respecting config)
            soa_path = config.get("base_file", self.current_base_file)
            if not soa_path:
                 QMessageBox.critical(self, "Error", "No Base File identified.")
                 return

            try:
                 current_col_config = config.get("column_config", self.current_column_config)
                 base_usecols = current_col_config.get(soa_path)
                 
                 # CRITICAL FIX: Ensure soa_match_col is loaded
                 if base_usecols is not None and soa_match_col and soa_match_col not in base_usecols:
                     base_usecols = list(base_usecols)
                     base_usecols.append(soa_match_col)
                 
                 soa_df = DataLoader.load_file(soa_path, usecols=base_usecols)
            except Exception as e:
                 print(f"Error loading SOA {soa_path}: {e}")
                 QMessageBox.critical(self, "File Load Error", f"Error loading base file {os.path.basename(soa_path)}:\n{str(e)}")
                 return

            # Initialize Engine
            engine = SOAEngine(soa_df, soa_match_col, date_col, amount_col, ref_configs, 
                               mode=self.reco_mode, schema_config=schema_config, 
                               path_mapping=path_to_name_map)
            result_df, saved_path, discrepancy_df, schema_df = engine.run()
            
            print(f"DEBUG: Reconciliation Complete. Saved to {saved_path}")
            
            # Show Results (both detailed and discrepancy)
            self.results_screen.display_results(result_df, discrepancy_df, schema_df)
            self.stack.setCurrentWidget(self.results_screen)
            
            if saved_path:
                 file_name = os.path.basename(saved_path)
                 folder = os.path.dirname(saved_path)
                 msg = QMessageBox(self)
                 msg.setWindowTitle("Reconciliation Complete")
                 msg.setIcon(QMessageBox.Information)
                 msg.setText(f"Reconciliation completed successfully!\n\nFile: {file_name}")
                 msg.setInformativeText(f"Saved to:\n{folder}")
                 msg.setStandardButtons(QMessageBox.Ok)
                 msg.setMinimumWidth(500)
                 msg.setMinimumWidth(500)
                 msg.exec()

            # Check for non-critical errors (partial failures)
            if hasattr(engine, 'errors') and engine.errors:
                error_text = "\n\n".join(engine.errors)
                QMessageBox.warning(self, "Partial Reconciliation Errors", 
                    f"The following errors occurred during processing:\n\n{error_text}\n\n"
                    "Check the logs or file content for more details.")

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
