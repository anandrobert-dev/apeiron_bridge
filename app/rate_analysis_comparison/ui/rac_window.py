import os
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QStackedWidget, QFrame, QFileDialog, QTableWidget, QTableWidgetItem,
                             QCheckBox, QRadioButton, QButtonGroup, QProgressBar, QLineEdit, 
                             QTextEdit, QHeaderView, QMessageBox, QComboBox, QScrollArea,
                             QDialog, QAbstractItemView, QTabWidget)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon
from app.rate_analysis_comparison.workers.parsing_worker import ParsingWorker
from app.rate_analysis_comparison.db import (get_engine, get_carriers, create_carrier,
                                             check_db_connection, is_db_available)
import uuid
import logging

logger = logging.getLogger(__name__)


class RateAnalysisComparisonWindow(QWidget):
    """
    Main stacked widget housing the workflow screens of the Rate Analysis & Comparison module.
    Replaces Quick CSV Match in the main application flow.
    """
    go_back = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files = []  # List of dicts: {"path": str, "carrier": str, "flag": str, "parsed": object}
        self._parsed_results = {}  # Map: file_path -> ParsedResult
        self.active_mode = None  # "rate_comp", "tc_comp", "rate_analysis"
        self.init_ui()
        
        # Check database connectivity
        if not check_db_connection():
            self.warning_banner.setVisible(True)
            
        self._update_proceed_button_state()

    def init_ui(self):
        # Master layout
        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(30, 30, 30, 30)
        self.master_layout.setSpacing(20)

        # Header Title Bar
        self.header_frame = QFrame()
        self.header_frame.setFrameShape(QFrame.StyledPanel)
        self.header_frame.setStyleSheet("background-color: #252526; border-radius: 8px; border: 1px solid #3C3C3C;")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(15, 10, 15, 10)

        self.lbl_module_title = QLabel("Rate Analysis & Comparison")
        self.lbl_module_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #F59E0B;")
        header_layout.addWidget(self.lbl_module_title)

        header_layout.addStretch()

        self.btn_back_home = QPushButton("Back to Home")
        self.btn_back_home.setStyleSheet("""
            QPushButton {
                background-color: #3E3E42; color: #FFF; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #505054; }
        """)
        self.btn_back_home.clicked.connect(self.handle_back_action)
        header_layout.addWidget(self.btn_back_home)

        self.master_layout.addWidget(self.header_frame)

        # Warning banner for PostgreSQL availability
        self.warning_banner = QFrame()
        self.warning_banner.setFrameShape(QFrame.StyledPanel)
        self.warning_banner.setStyleSheet("""
            QFrame {
                background-color: #4D3C18;
                border: 1px solid #D97706;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        wb_layout = QHBoxLayout(self.warning_banner)
        wb_layout.setContentsMargins(15, 10, 15, 10)
        
        self.lbl_warning_text = QLabel(
            "PostgreSQL is not running. Carrier autocomplete and nearby-lane matching are disabled.\n"
            "To enable: open a terminal and run:  sudo systemctl start postgresql\n"
            "Then re-launch the application."
        )
        self.lbl_warning_text.setStyleSheet("color: #FBBF24; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.lbl_warning_text.setWordWrap(True)
        wb_layout.addWidget(self.lbl_warning_text)
        
        self.warning_banner.setVisible(False)
        self.master_layout.addWidget(self.warning_banner)

        # Stacked widget for sub-screens
        self.stack = QStackedWidget()
        self.master_layout.addWidget(self.stack)

        # Create sub-screens
        self.create_mode_selector_screen()
        self.create_upload_screen()
        self.create_clause_review_screen()
        self.create_config_screen()
        self.create_results_screen()

        # Start with Mode Selector
        self.stack.setCurrentIndex(0)

    def handle_back_action(self):
        current_idx = self.stack.currentIndex()
        if current_idx == 0:
            self.go_back.emit()
        elif current_idx == 1:
            self.stack.setCurrentIndex(0)  # Go back to mode selector
        elif current_idx == 2:
            self.stack.setCurrentIndex(1)  # Go back to upload
        elif current_idx == 3:
            self.stack.setCurrentIndex(1)  # Go back to upload or clause review
        elif current_idx == 4:
            self.stack.setCurrentIndex(3)  # Go back to config

    # =========================================================================
    # Screen 1: Mode Selector
    # =========================================================================
    def create_mode_selector_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(30)

        lbl_prompt = QLabel("Select an intelligence workflow below to proceed:")
        lbl_prompt.setStyleSheet("font-size: 16px; color: #CCC;")
        lbl_prompt.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_prompt)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(30)

        # Card 1: Rate Comparison
        card_rate = self.create_workflow_card(
            "Rate Comparison",
            "Compare line-haul numeric rates, discover missing lanes, identify blank/zero quotes, and compute absolute/percentage deltas across multiple carrier contracts side-by-side.",
            "#F59E0B",
            lambda: self.select_workflow("rate_comp")
        )
        cards_layout.addWidget(card_rate)

        # Card 2: Terms & Conditions Comparison
        card_tc = self.create_workflow_card(
            "Terms & Conditions Comparison",
            "Extract operational contractual clauses (detention, payment terms, fuel surcharges) into a structured taxonomy. Score favorability and compare carrier conditions side-by-side.",
            "#10B981",
            lambda: self.select_workflow("tc_comp")
        )
        cards_layout.addWidget(card_tc)

        # Card 3: Rate Analysis
        card_analysis = self.create_workflow_card(
            "Rate Analysis",
            "Upload historical billed shipments and simulate actual shipments against hypothetical multi-carrier contracts. Accounts for accessorials, fuel methodology, and weight-breaks to find optimal routing and total savings.",
            "#3B82F6",
            lambda: self.select_workflow("rate_analysis")
        )
        cards_layout.addWidget(card_analysis)

        layout.addLayout(cards_layout)
        self.stack.addWidget(screen)

    def create_workflow_card(self, title, desc, color, callback):
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setFixedWidth(280)
        card.setFixedHeight(320)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #2D2D30;
                border: 2px solid {color};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; border: none; background: transparent;")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setWordWrap(True)
        lbl_title.setMinimumWidth(240)
        layout.addWidget(lbl_title)

        lbl_desc = QLabel(desc)
        lbl_desc.setStyleSheet("font-size: 13px; color: #BBB; border: none; background: transparent;")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_desc)

        layout.addStretch()

        btn = QPushButton("Select")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.9; }}
        """)
        btn.clicked.connect(callback)
        layout.addWidget(btn)

        return card

    def select_workflow(self, mode):
        self.active_mode = mode
        # Update Title
        titles = {
            "rate_comp": "Rate Comparison Workflow",
            "tc_comp": "T&C Comparison Workflow",
            "rate_analysis": "Shipment Rate Analysis Workflow"
        }
        self.lbl_module_title.setText(titles[mode])
        self.selected_files.clear()
        self.update_uploaded_files_table()
        self.stack.setCurrentIndex(1)  # Move to upload screen

    # =========================================================================
    # Screen 2: Multi-File Uploader & Autocomplete
    # =========================================================================
    def create_upload_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(15)

        lbl_section = QLabel("Step 1: Upload Carrier Agreement Documents")
        lbl_section.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF;")
        layout.addWidget(lbl_section)

        # Upload Area
        upload_area = QFrame()
        upload_area.setFrameShape(QFrame.StyledPanel)
        upload_area.setStyleSheet("background-color: #2D2D30; border: 2px dashed #555; border-radius: 8px;")
        upload_area_layout = QVBoxLayout(upload_area)
        upload_area_layout.setContentsMargins(30, 30, 30, 30)
        upload_area_layout.setAlignment(Qt.AlignCenter)

        lbl_instructions = QLabel("Select at least 2 files (Excel spreadsheets or PDF agreements) to compare:")
        lbl_instructions.setStyleSheet("font-size: 14px; color: #CCC;")
        upload_area_layout.addWidget(lbl_instructions)

        btn_browse = QPushButton("Add Carrier Agreements...")
        btn_browse.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B; color: white; border: none; padding: 10px 20px; border-radius: 4px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #D97706; }
        """)
        btn_browse.clicked.connect(self.browse_agreements)
        upload_area_layout.addWidget(btn_browse)

        layout.addWidget(upload_area)

        # Selected Files Table
        self.tbl_files = QTableWidget()
        self.tbl_files.setColumnCount(7)
        self.tbl_files.setHorizontalHeaderLabels(["#", "Carrier Name", "Version Flag", "File Path", "Status", "Review", "✕"])
        
        # Set section resize mode to Interactive and set stretch last section to False
        header = self.tbl_files.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        
        # Set initial widths
        self.tbl_files.setColumnWidth(0, 36)    # #
        self.tbl_files.setColumnWidth(1, 200)   # Carrier Name
        self.tbl_files.setColumnWidth(2, 160)   # Version Flag
        self.tbl_files.setColumnWidth(3, 280)   # File Path
        self.tbl_files.setColumnWidth(4, 220)   # Status
        self.tbl_files.setColumnWidth(5, 80)    # Review
        self.tbl_files.setColumnWidth(6, 40)    # ✕
        
        # Minimum widths prevent collapse
        header.setMinimumSectionSize(36)
        
        # Horizontal scrollbar policy
        self.tbl_files.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.tbl_files.setStyleSheet("""
            QTableWidget { background-color: #1E1E1E; color: #FFF; gridline-color: #3C3C3C; border: 1px solid #3C3C3C; border-radius: 4px; }
            QHeaderView::section { background-color: #2D2D30; color: #FFF; padding: 5px; border: 1px solid #3C3C3C; }
        """)
        layout.addWidget(self.tbl_files)

        # Parse Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #3C3C3C; border-radius: 4px; background-color: #2D2D30; text-align: center; color: white; }
            QProgressBar::chunk { background-color: #F59E0B; }
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setStyleSheet("color: #AAA;")
        self.lbl_progress_status.setVisible(False)
        layout.addWidget(self.lbl_progress_status)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addStretch()

        self.btn_proceed_mapping = QPushButton("Proceed to Analysis >>")
        self.btn_proceed_mapping.setStyleSheet("""
            QPushButton {
                background-color: #10B981; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #4B5563; color: #9CA3AF; }
        """)
        self.btn_proceed_mapping.setEnabled(False)
        self.btn_proceed_mapping.setToolTip("Upload and parse at least 2 carrier agreements to compare.")
        self.btn_proceed_mapping.clicked.connect(self.proceed_to_next_step)
        nav_layout.addWidget(self.btn_proceed_mapping)

        layout.addLayout(nav_layout)
        self.stack.addWidget(screen)

    def browse_agreements(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Carrier Agreements", "", "Carrier Agreements (*.xlsx *.xls *.pdf *.docx)"
        )
        if not files:
            return

        # Load carrier list from Postgres autocomplete
        saved_carriers = []
        if is_db_available():
            try:
                 engine = get_engine()
                 with engine.connect() as conn:
                      saved_carriers = [c["name"] for c in get_carriers(conn)]
            except Exception as e:
                 logger.warning("DB unavailable for carrier autocomplete: %s", e)
        
        for file in files:
            # Prevent adding duplicates
            if any(f["path"] == file for f in self.selected_files):
                continue
                
            basename = os.path.basename(file)
            # Try to guess carrier from name
            suggested_carrier = os.path.splitext(basename)[0]
            name_match = re.match(r'^([a-zA-Z\s_]+)', suggested_carrier)
            if name_match:
                suggested_carrier = name_match.group(1).replace("_", " ").strip()

            self.selected_files.append({
                "path": file,
                "carrier": suggested_carrier,
                "flag": "na",  # 'na', 'new', 'old'
                "status": "Ready",
                "parsed": None
            })

        self.update_uploaded_files_table()
        self.trigger_parsing_pipeline()

    def update_uploaded_files_table(self):
        self.tbl_files.setRowCount(len(self.selected_files))
        for row_idx, file_data in enumerate(self.selected_files):
            # Col 0: row index '#'
            num_item = QTableWidgetItem(str(row_idx + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.tbl_files.setItem(row_idx, 0, num_item)

            # Col 1: Carrier Name Autocomplete Combobox
            cbo_carrier = QComboBox()
            cbo_carrier.setEditable(True)
            cbo_carrier.setInsertPolicy(QComboBox.NoInsert)
            # Seed suggested name
            cbo_carrier.addItem(file_data["carrier"])
            
            # Fetch and add previously-saved carriers
            if is_db_available():
                try:
                     engine = get_engine()
                     with engine.connect() as conn:
                          saved = [c["name"] for c in get_carriers(conn)]
                          for c in saved:
                              if c != file_data["carrier"]:
                                  cbo_carrier.addItem(c)
                except Exception as e:
                     logger.warning("DB unavailable for carrier autocomplete: %s", e)
            else:
                cbo_carrier.setCompleter(None)
            
            cbo_carrier.setCurrentText(file_data["carrier"])
            # Update carrier name in model on text change
            cbo_carrier.currentTextChanged.connect(
                lambda text, idx=row_idx: self.update_carrier_name(idx, text)
            )
            self.tbl_files.setCellWidget(row_idx, 1, cbo_carrier)

            # Col 2: Version Flag Combobox
            cbo_flag = QComboBox()
            cbo_flag.addItems(["N/A (only version)", "New", "Old / superseded"])
            flag_map = {"na": 0, "new": 1, "old": 2}
            cbo_flag.setCurrentIndex(flag_map.get(file_data["flag"], 0))
            cbo_flag.currentIndexChanged.connect(
                lambda idx, row=row_idx: self.update_version_flag(row, idx)
            )
            self.tbl_files.setCellWidget(row_idx, 2, cbo_flag)

            # Col 3: Path
            path_item = QTableWidgetItem(os.path.basename(file_data["path"]))
            path_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            path_item.setToolTip(file_data["path"])
            self.tbl_files.setItem(row_idx, 3, path_item)

            # Col 4: Status
            status_item = QTableWidgetItem()
            status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            
            status_str = file_data.get("status", "")
            if status_str.startswith("Parsed"):
                status_item.setText(status_str)
                status_item.setForeground(QColor("#10B981"))
                self.tbl_files.setRowHeight(row_idx, 35)
                if "parsed" in file_data and getattr(file_data["parsed"], "warnings", None):
                    warn_text = "\n".join(w.message for w in file_data["parsed"].warnings if w.message)
                    if warn_text:
                        status_item.setToolTip(f"Warnings:\n{warn_text}")
            elif status_str.startswith("Warning"):
                msg = file_data.get("warning_message", "No data found")
                short = msg[:65] + "…" if len(msg) > 65 else msg
                status_item.setText(f"Warning\n{short}")
                status_item.setForeground(QColor("#F59E0B")) # Amber color
                status_item.setToolTip(msg)
                self.tbl_files.setRowHeight(row_idx, 52)
            elif status_str.startswith("Failed"):
                reason = file_data.get("error_reason", "")
                if reason:
                    short_reason = reason[:45] + "..." if len(reason) > 45 else reason
                    status_item.setText(f"Failed\n{short_reason}")
                    self.tbl_files.setRowHeight(row_idx, 52)
                else:
                    status_item.setText("Failed")
                    self.tbl_files.setRowHeight(row_idx, 35)
                status_item.setForeground(QColor("#EF4444"))
                if "error_detail" in file_data:
                    status_item.setToolTip(file_data["error_detail"])
            else:
                status_item.setText(status_str)
                self.tbl_files.setRowHeight(row_idx, 35)
            self.tbl_files.setItem(row_idx, 4, status_item)

            # Col 5: Review Button
            if status_str.startswith("Parsed"):
                review_btn = QPushButton("Review")
                review_btn.setFixedHeight(28)
                review_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #F59E0B;
                        border: 1px solid #F59E0B;
                        border-radius: 4px;
                        padding: 0 8px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: rgba(245, 158, 11, 0.15);
                    }
                """)
                review_btn.setToolTip("Preview parsed rate rows")
                # Bind dynamic sender-based slot
                review_btn.clicked.connect(lambda _, p=file_data["path"]: self.show_review_dialog_for_button(p))
                self.tbl_files.setCellWidget(row_idx, 5, review_btn)
            else:
                # Remove cell widget if not Parsed
                self.tbl_files.removeCellWidget(row_idx, 5)

            # Col 6: Remove Button "✕"
            remove_btn = QPushButton("✕")
            remove_btn.setFixedWidth(32)
            remove_btn.setFixedHeight(28)
            remove_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #888;
                    border: none;
                    font-size: 14px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    color: #E24B4A;
                    background: rgba(226, 75, 74, 0.12);
                }
            """)
            remove_btn.setToolTip("Remove this file")
            remove_btn.clicked.connect(lambda _, r=row_idx: self.remove_uploaded_file(r))
            self.tbl_files.setCellWidget(row_idx, 6, remove_btn)

        self._update_proceed_button_state()

    def update_carrier_name(self, row_idx, name):
        if row_idx < len(self.selected_files):
            self.selected_files[row_idx]["carrier"] = name

    def update_version_flag(self, row_idx, flag_idx):
        flag_map = {0: "na", 1: "new", 2: "old"}
        if row_idx < len(self.selected_files):
            self.selected_files[row_idx]["flag"] = flag_map.get(flag_idx, "na")

    # =========================================================================
    # Threaded Parsing Pipeline Execution
    # =========================================================================
    def trigger_parsing_pipeline(self):
        # Trigger background parsing for any file that is not yet parsed
        self.progress_bar.setVisible(True)
        self.lbl_progress_status.setVisible(True)
        
        self.parse_next_ready_file()

    def parse_next_ready_file(self):
        target = None
        target_idx = -1
        for idx, file_data in enumerate(self.selected_files):
            if file_data["status"] == "Ready" or file_data["status"] == "Processing":
                target = file_data
                target_idx = idx
                break

        if not target:
            # All done!
            self.progress_bar.setVisible(False)
            self.lbl_progress_status.setVisible(False)
            self.update_uploaded_files_table()
            return

        target["status"] = "Parsing..."
        self.update_uploaded_files_table()

        self.parsing_worker = ParsingWorker(target["path"])
        self.parsing_worker.progress.connect(self.handle_parser_progress)
        self.parsing_worker.error.connect(lambda err, idx=target_idx: self.handle_parser_error(idx, err))
        self.parsing_worker.finished.connect(lambda res, idx=target_idx: self.handle_parser_finished(idx, res))
        self.parsing_worker.start()

    def handle_parser_progress(self, pct, status):
        self.progress_bar.setValue(pct)
        self.lbl_progress_status.setText(status)

    def handle_parser_error(self, idx, err_msg):
        print(f"Error parsing file: {err_msg}")
        if idx < len(self.selected_files):
            # Extract first line (which contains the custom exception message)
            first_line = err_msg.splitlines()[0] if err_msg else "Unknown parsing error"
            
            # Clean up the path prefix (e.g. "[/path/to/file.pdf] Msg" -> "Msg")
            clean_msg = re.sub(r'^\[.*?\]\s*', '', first_line)
            
            self.selected_files[idx]["status"] = "Failed"
            self.selected_files[idx]["error_detail"] = err_msg
            self.selected_files[idx]["error_reason"] = clean_msg
            
        self.update_uploaded_files_table()
        self.parse_next_ready_file()


    def handle_parser_finished(self, idx, parsed_agreement):
        if idx < len(self.selected_files):
            # Overwrite default extracted values if they exist
            if parsed_agreement.carrier_name:
                 self.selected_files[idx]["carrier"] = parsed_agreement.carrier_name
            self.selected_files[idx]["parsed"] = parsed_agreement
            
            # Cache the parsed results
            file_path = self.selected_files[idx]["path"]
            self._parsed_results[file_path] = parsed_agreement

            # Build detailed status message
            has_rates = hasattr(parsed_agreement, "rates") and parsed_agreement.rates
            has_clauses = hasattr(parsed_agreement, "clauses") and parsed_agreement.clauses
            
            if has_rates or has_clauses:
                row_count = len(parsed_agreement.rates) if has_rates else 0
                clause_count = len(parsed_agreement.clauses) if has_clauses else 0
                status_text = f"Parsed — {row_count} rate rows"
                if clause_count:
                    status_text += f", {clause_count} clauses"
                if getattr(parsed_agreement, "warnings", None):
                    status_text += f" ({len(parsed_agreement.warnings)} warnings)"
                self.selected_files[idx]["status"] = status_text
            elif getattr(parsed_agreement, "warnings", None):
                # No rows but has warnings — e.g. form document warning
                self.selected_files[idx]["status"] = "Warning"
                msg = parsed_agreement.warnings[0].message
                self.selected_files[idx]["warning_message"] = msg
            else:
                self.selected_files[idx]["status"] = "Parsed — 0 rows"
        
        self.update_uploaded_files_table()
        self.parse_next_ready_file()

    def remove_uploaded_file(self, row: int):
        """Remove a file row and its parsed data from the upload table."""
        sender = self.sender()
        if not isinstance(sender, QPushButton):
            # Fallback if called directly
            if row < 0 or row >= self.tbl_files.rowCount():
                return
            r = row
        else:
            # Find the row that holds this button widget in Column 6
            r = -1
            for i in range(self.tbl_files.rowCount()):
                if self.tbl_files.cellWidget(i, 6) == sender:
                    r = i
                    break
            if r == -1:
                return

        file_path_item = self.tbl_files.item(r, 3)
        if file_path_item:
            path = file_path_item.toolTip()
            # Clear parsed data if it exists
            self._parsed_results.pop(path, None)
            # Remove from self.selected_files
            self.selected_files = [f for f in self.selected_files if f["path"] != path]

        self.update_uploaded_files_table()

    def show_review_dialog_for_button(self, file_path: str = ""):
        """Helper to safely find file path and route to review dialog."""
        sender = self.sender()
        path = file_path
        if isinstance(sender, QPushButton):
            for i in range(self.tbl_files.rowCount()):
                if self.tbl_files.cellWidget(i, 5) == sender:
                    path_item = self.tbl_files.item(i, 3)
                    if path_item:
                        path = path_item.toolTip()
                    break
        self.show_review_dialog(path)

    def show_review_dialog(self, file_path: str):
        """
        Open a read-only preview of the parsed data for a file.
        Handles both ParsedAgreement (Excel/DOCX/CSV) and ParsedResult (PDF) objects.
        """
        result = self._parsed_results.get(file_path)
        if not result:
            return

        # Normalise to a common interface regardless of which parser produced the result
        # ParsedAgreement has .rates / .clauses
        # ParsedResult    has .rate_rows / .clause_chunks
        if hasattr(result, "rate_rows"):
            rate_items   = result.rate_rows
            clause_items = result.clause_chunks
            rate_count   = len(rate_items)
            clause_count = len(clause_items)
            warnings     = getattr(result, "warnings", [])
            # Build display rows from RawRateRow.raw_fields
            def get_display_row(item):
                f = item.raw_fields
                return [
                    f.get("origin", ""),
                    f.get("destination", ""),
                    f.get("mode", ""),
                    f.get("service", ""),
                    f.get("weight_break", ""),
                    f.get("rate", ""),
                    f.get("no_rate", "False"),
                    f"p{item.source_page}" if item.source_page
                        else (item.source_sheet or ""),
                ]
        else:
            # ParsedAgreement path
            rate_items   = result.rates
            clause_items = result.clauses
            rate_count   = len(rate_items)
            clause_count = len(clause_items)
            warnings     = getattr(result, "warnings", [])
            # Build display rows from CarrierRate canonical fields
            def get_display_row(item):
                return [
                    getattr(item, "origin_city",  "") or "",
                    getattr(item, "dest_city",    "") or "",
                    getattr(item, "service_level","") or "",
                    "",   # mode — not always on CarrierRate
                    str(getattr(item, "weight_break_lo", "") or ""),
                    str(getattr(item, "freight_rate",    "") or ""),
                    "False",
                    getattr(item, "source_locator", "") or "",
                ]

        if not rate_items:
            # Nothing to preview
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Parsed Data Review — {os.path.basename(file_path)}")
        dialog.setMinimumSize(900, 540)
        
        # Style the dialog for a sleek premium dark look matching main UI
        dialog.setStyleSheet("""
            QDialog { background-color: #1E1E24; color: #FFF; }
            QLabel { color: #DDD; }
            QPushButton { background-color: #3E3E42; color: #FFF; border: none; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #505054; }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Summary line
        summary = QLabel(
            f"{rate_count} rate rows   ·   "
            f"{clause_count} clause chunks   ·   "
            f"{len(warnings)} warnings"
        )
        summary.setStyleSheet(
            "color: #F59E0B; font-weight: bold; font-size: 13px; padding: 4px 0;"
        )
        layout.addWidget(summary)

        # Rate rows preview table
        col_headers = [
            "Origin", "Destination", "Mode / Service Level",
            "Service", "Weight Break", "Rate", "No-Rate", "Source"
        ]
        preview = QTableWidget()
        preview.setColumnCount(len(col_headers))
        preview.setHorizontalHeaderLabels(col_headers)
        preview.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        preview.horizontalHeader().setStretchLastSection(True)
        preview.verticalHeader().setVisible(False)
        preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        preview.setSelectionBehavior(QAbstractItemView.SelectRows)
        preview.setAlternatingRowColors(True)
        preview.setShowGrid(True)
        preview.setStyleSheet("""
            QTableWidget { 
                background-color: #1E1E24; 
                alternate-background-color: #2D2D35; 
                color: #FFFFFF; 
                gridline-color: #3C3C3C; 
                border: 1px solid #3C3C3C; 
                border-radius: 4px; 
            }
            QTableWidget::item { 
                color: #FFFFFF; 
                padding: 4px;
            }
            QHeaderView::section { 
                background-color: #2D2D30; 
                color: #FFFFFF; 
                padding: 6px; 
                border: 1px solid #3C3C3C; 
                font-weight: bold;
            }
        """)

        rows_to_show = rate_items[:50]
        preview.setRowCount(len(rows_to_show))

        for r_idx, item in enumerate(rows_to_show):
            values = get_display_row(item)
            for c_idx, val in enumerate(values):
                cell = QTableWidgetItem(str(val) if val is not None else "")
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                preview.setItem(r_idx, c_idx, cell)

        preview.resizeColumnsToContents()
        layout.addWidget(preview)

        if len(rate_items) > 50:
            note = QLabel(f"Showing first 50 of {rate_count} rows.")
            note.setStyleSheet("color: #888; font-size: 11px; padding: 2px 0;")
            layout.addWidget(note)

        # Warnings section
        if warnings:
            warn_label = QLabel(f"Warnings ({len(warnings)}):")
            warn_label.setStyleSheet(
                "color: #F59E0B; font-weight: bold; margin-top: 8px;"
            )
            layout.addWidget(warn_label)
            for w in warnings[:5]:
                msg = w.message if hasattr(w, "message") else str(w)
                wl = QLabel(f"• {msg}")
                wl.setWordWrap(True)
                wl.setStyleSheet("color: #FF8A80; font-size: 11px; padding: 1px 0;")
                layout.addWidget(wl)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        dialog.exec()

    def _update_proceed_button_state(self):
        """Enable Proceed only when ≥2 files have parsed rate rows."""
        parsed_count = sum(
            1 for path, result in self._parsed_results.items()
            if result and self._get_rate_count(result) > 0
        )

        if parsed_count >= 2:
            self.btn_proceed_mapping.setEnabled(True)
            self.btn_proceed_mapping.setToolTip("")
        elif parsed_count == 1:
            self.btn_proceed_mapping.setEnabled(False)
            self.btn_proceed_mapping.setToolTip(
                "1 carrier parsed. Add at least 1 more carrier agreement to compare."
            )
        else:
            self.btn_proceed_mapping.setEnabled(False)
            self.btn_proceed_mapping.setToolTip(
                "Upload and parse at least 2 carrier agreements to compare."
            )

    def _get_rate_count(self, result) -> int:
        """Return the number of rate rows/items from either ParsedResult or ParsedAgreement."""
        if hasattr(result, "rate_rows"):
            return len(result.rate_rows)
        if hasattr(result, "rates"):
            return len(result.rates)
        return 0

    def go_to_config_screen(self):
        self.cbo_baseline.clear()
        carriers = sorted(list(set(f["carrier"] for f in self.selected_files if f.get("carrier"))))
        self.cbo_baseline.addItems(carriers)
        if carriers:
            self.cbo_baseline.setCurrentIndex(0)
        self.stack.setCurrentIndex(3)

    def proceed_to_next_step(self):
        if self.active_mode == "tc_comp":
            self.setup_clause_review_screen()
            self.stack.setCurrentIndex(2)  # Go to Clause Review Screen
        else:
            self.go_to_config_screen()

    # =========================================================================
    # Screen 3: Clause Review Panel
    # =========================================================================
    def create_clause_review_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(15)

        lbl_section = QLabel("Step 2: Review and Approve Extracted T&C Clauses")
        lbl_section.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF;")
        layout.addWidget(lbl_section)

        # Scroll Area for Clauses
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #3C3C3C; border-radius: 4px; background-color: #1E1E1E; }")
        
        self.clause_container = QWidget()
        self.clause_container_layout = QVBoxLayout(self.clause_container)
        self.clause_container_layout.setSpacing(15)
        self.clause_container_layout.addStretch()
        self.scroll_area.setWidget(self.clause_container)
        layout.addWidget(self.scroll_area)

        # Navigation
        nav_layout = QHBoxLayout()
        btn_back = QPushButton("<< Back to Upload")
        btn_back.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            btn_back:hover { background-color: #505054; }
        """)
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        nav_layout.addWidget(btn_back)

        nav_layout.addStretch()

        btn_next = QPushButton("Proceed to Configure >>")
        btn_next.setStyleSheet("""
            QPushButton { background-color: #10B981; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            btn_next:hover { background-color: #059669; }
        """)
        btn_next.clicked.connect(self.go_to_config_screen)
        nav_layout.addWidget(btn_next)

        layout.addLayout(nav_layout)
        self.stack.addWidget(screen)

    def setup_clause_review_screen(self):
        # Clear previous widgets in layout
        for i in reversed(range(self.clause_container_layout.count())):
            item = self.clause_container_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        self.clause_widgets = []

        # Populate clauses from each parsed agreement
        for file_idx, file_data in enumerate(self.selected_files):
            pa = file_data["parsed"]
            if not pa or not pa.clauses:
                continue

            lbl_carrier_header = QLabel(f"Carrier: {file_data['carrier']}")
            lbl_carrier_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #FBBF24; margin-top: 10px;")
            self.clause_container_layout.addWidget(lbl_carrier_header)

            for c_idx, clause in enumerate(pa.clauses):
                clause_frame = QFrame()
                clause_frame.setFrameShape(QFrame.StyledPanel)
                clause_frame.setStyleSheet("background-color: #2D2D30; border: 1px solid #444; border-radius: 6px; padding: 10px;")
                clause_layout = QVBoxLayout(clause_frame)

                # Header with Type and Actions
                header_lay = QHBoxLayout()
                lbl_type = QLabel(f"Clause: {clause.clause_type.upper()}")
                lbl_type.setStyleSheet("font-weight: bold; color: #3B82F6;")
                header_lay.addWidget(lbl_type)

                header_lay.addStretch()

                chk_accept = QCheckBox("Accept")
                chk_accept.setChecked(True)
                header_lay.addWidget(chk_accept)

                chk_reject = QCheckBox("Reject")
                header_lay.addWidget(chk_reject)

                # Exclusive checkbox group
                chk_group = QButtonGroup(clause_frame)
                chk_group.addButton(chk_accept)
                chk_group.addButton(chk_reject)
                chk_group.setExclusive(True)

                clause_layout.addLayout(header_lay)

                # Source info
                if clause.source_locator:
                     lbl_loc = QLabel(f"Source: {clause.source_locator}")
                     lbl_loc.setStyleSheet("color: #78909C; font-size: 11px;")
                     clause_layout.addWidget(lbl_loc)

                # Text Editor
                text_editor = QTextEdit()
                text_editor.setPlainText(clause.extracted_text)
                text_editor.setFixedHeight(80)
                text_editor.setStyleSheet("background-color: #1E1E1E; border: 1px solid #3C3C3C; color: #FFF;")
                clause_layout.addWidget(text_editor)

                self.clause_container_layout.addWidget(clause_frame)
                self.clause_widgets.append({
                    "file_idx": file_idx,
                    "clause_idx": c_idx,
                    "accept_chk": chk_accept,
                    "text_edit": text_editor
                })
        
        self.clause_container_layout.addStretch()

    # =========================================================================
    # Screen 4: Comparison Configuration
    # =========================================================================
    def create_config_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(20)

        lbl_section = QLabel("Step 3: Configure Comparison Parameters")
        lbl_section.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF;")
        layout.addWidget(lbl_section)

        # Options Container
        opt_frame = QFrame()
        opt_frame.setFrameShape(QFrame.StyledPanel)
        opt_frame.setStyleSheet("background-color: #2D2D30; border: 1px solid #3C3C3C; border-radius: 8px; padding: 20px;")
        opt_layout = QVBoxLayout(opt_frame)
        opt_layout.setSpacing(15)

        # Nearby Lane
        self.chk_nearby = QCheckBox("Enable Nearby Lane Lookup (Suburbs / fallbacks)")
        self.chk_nearby.setChecked(True)
        self.chk_nearby.setStyleSheet("font-size: 13px; color: #DDD;")
        if not is_db_available():
            self.chk_nearby.setChecked(False)
            self.chk_nearby.setEnabled(False)
            self.chk_nearby.setToolTip("Requires database")
        opt_layout.addWidget(self.chk_nearby)

        # Missing Lanes
        self.chk_missing = QCheckBox("Flag Missing Lanes (Lanes present in carrier A but missing in B)")
        self.chk_missing.setChecked(True)
        self.chk_missing.setStyleSheet("font-size: 13px; color: #DDD;")
        opt_layout.addWidget(self.chk_missing)

        # No Rates
        self.chk_norate = QCheckBox("Detect Blank/Zero rates and flag 'On Request'")
        self.chk_norate.setChecked(True)
        self.chk_norate.setStyleSheet("font-size: 13px; color: #DDD;")
        opt_layout.addWidget(self.chk_norate)

        # Baseline Carrier Dropdown
        baseline_layout = QHBoxLayout()
        lbl_base = QLabel("Select Baseline Carrier for rate deltas:")
        lbl_base.setStyleSheet("font-size: 13px; color: #DDD;")
        baseline_layout.addWidget(lbl_base)

        self.cbo_baseline = QComboBox()
        self.cbo_baseline.setStyleSheet("background-color: #1E1E1E; border: 1px solid #3C3C3C; padding: 5px; color: white;")
        baseline_layout.addWidget(self.cbo_baseline)
        baseline_layout.addStretch()
        opt_layout.addLayout(baseline_layout)

        layout.addWidget(opt_frame)

        # Navigation
        nav_layout = QHBoxLayout()
        btn_back = QPushButton("<< Back")
        btn_back.setStyleSheet("""
            QPushButton { background-color: #3E3E42; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            btn_back:hover { background-color: #505054; }
        """)
        btn_back.clicked.connect(self.handle_back_action)
        nav_layout.addWidget(btn_back)

        nav_layout.addStretch()

        self.btn_run_comp = QPushButton("Run Comparison! ⚡")
        self.btn_run_comp.setStyleSheet("""
            QPushButton { background-color: #F59E0B; color: white; border: none; padding: 10px 20px; border-radius: 4px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #D97706; }
        """)
        self.btn_run_comp.clicked.connect(self.execute_deterministic_engine)
        nav_layout.addWidget(self.btn_run_comp)

        layout.addLayout(nav_layout)
        self.stack.addWidget(screen)

    # =========================================================================
    # Helpers
    # =========================================================================
    def _create_stats_card(self, title: str, value: str, color_hex: str = "#3E3E42") -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #2D2D30;
                border: 2px solid {color_hex};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(5)
        card_layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 11px; color: #AAAAAA; font-weight: bold; text-transform: uppercase;")
        lbl_title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lbl_title)
        
        lbl_value = QLabel(value)
        lbl_value.setStyleSheet("font-size: 16px; color: #FFFFFF; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(lbl_value)
        
        return card

    def create_results_screen(self):
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setSpacing(15)

        lbl_section = QLabel("Step 4: Rate & T&C Intelligence Analysis Report")
        lbl_section.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF;")
        layout.addWidget(lbl_section)

        # Stats Dashboard Container
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(15)
        layout.addLayout(self.stats_layout)

        # QTabWidget for Multi-Dimensional Results
        self.tab_results = QTabWidget()
        self.tab_results.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #3C3C3C; background: #1E1E1E; border-radius: 4px; }
            QTabBar::tab { background: #2D2D30; color: #AAA; padding: 8px 16px; border: 1px solid #3C3C3C; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }
            QTabBar::tab:selected { background: #1E1E1E; color: #FFF; border-bottom: 1px solid #1E1E1E; }
        """)

        # Helper for creating styled table widgets
        def make_styled_table():
            tbl = QTableWidget()
            tbl.setStyleSheet("""
                QTableWidget { background-color: #1E1E1E; color: #FFF; gridline-color: #3C3C3C; border: none; }
                QHeaderView::section { background-color: #2D2D30; color: #FFF; padding: 5px; border: 1px solid #3C3C3C; }
            """)
            tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            return tbl

        self.tbl_detailed = make_styled_table()
        self.tbl_lane_grid = make_styled_table()
        self.tbl_slab_summary = make_styled_table()
        self.tbl_missing = make_styled_table()

        # Alias for backward compatibility
        self.tbl_results = self.tbl_detailed

        self.tab_results.addTab(self.tbl_detailed, "📋 Detailed Comparison")
        self.tab_results.addTab(self.tbl_lane_grid, "🗺️ Lane Rate Grid")
        self.tab_results.addTab(self.tbl_slab_summary, "⚖️ Weight Slab Summary")
        self.tab_results.addTab(self.tbl_missing, "⚠️ Missing Lanes")

        layout.addWidget(self.tab_results)

        # Export Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_pdf = QPushButton("Export PDF Report")
        btn_pdf.setStyleSheet("""
            QPushButton { background-color: #EA4335; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            btn_pdf:hover { background-color: #D32F2F; }
        """)
        btn_pdf.clicked.connect(self.export_pdf)
        btn_layout.addWidget(btn_pdf)

        btn_excel = QPushButton("Export Excel Report")
        btn_excel.setStyleSheet("""
            QPushButton { background-color: #34A853; color: white; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            btn_excel:hover { background-color: #2E7D32; }
        """)
        btn_excel.clicked.connect(self.export_excel)
        btn_layout.addWidget(btn_excel)

        layout.addLayout(btn_layout)
        self.stack.addWidget(screen)

    # =========================================================================
    # Comparison Computation Execution (Phase 1 Stub)
    # =========================================================================
    def execute_deterministic_engine(self):
        # Persist carriers in database automatically on run!
        if is_db_available():
            try:
                 engine = get_engine()
                 with engine.begin() as conn:
                      for file_data in self.selected_files:
                           c_name = file_data["carrier"]
                           # Check if exists
                           saved = [c["name"] for c in get_carriers(conn)]
                           if c_name not in saved:
                                create_carrier(conn, uuid.uuid4(), c_name)
            except Exception as e:
                 logger.warning("DB unavailable for persisting carriers: %s", e)

        # Compute results
        self.tbl_results.setRowCount(0)
        
        # Prepare display names for the compared sides A and B
        file_a = None
        file_b = None
        
        # Try to find by flag
        for f in self.selected_files:
            if f.get("flag") == "Old":
                file_a = f
            elif f.get("flag") == "New":
                file_b = f
                
        # Fallback to order if not set by flag
        if not file_a and self.selected_files:
            file_a = self.selected_files[0]
        if not file_b and len(self.selected_files) > 1:
            file_b = self.selected_files[1]
            
        if not file_b:
            file_b = file_a
            
        name_a = file_a["carrier"]
        if file_a.get("flag") == "Old":
            name_a += " (Old)"
        elif file_a.get("flag") == "New":
            name_a += " (New)"
            
        name_b = file_b["carrier"]
        if file_b.get("flag") == "Old":
            name_b += " (Old)"
        elif file_b.get("flag") == "New":
            name_b += " (New)"
            
        # Ensure display names are distinct
        if name_a == name_b:
            name_a += " [A]"
            name_b += " [B]"

        STANDARD_BRACKETS = ["MIN", "LTL", "500", "1000", "2000", "5000", "10000"]
        
        def match_bracket(r) -> str:
            if r.source_locator and "Col:" in r.source_locator:
                lbl = r.source_locator.split("Col:")[-1].strip().upper()
                if lbl in STANDARD_BRACKETS:
                    return lbl
            
            if r.weight_break_hi is not None:
                val = r.weight_break_hi
                if val == 0.0:
                    return "MIN"
                if val == 150.0:
                    return "LTL"
                if val == 500.0:
                    return "500"
                if val == 1000.0:
                    return "1000"
                if val == 2000.0:
                    return "2000"
                if val == 5000.0:
                    return "5000"
                if val == 10000.0:
                    return "10000"
            return "MIN"

        # Organize by Lane -> Bracket -> Rate
        rates_a = {}
        rates_b = {}
        distinct_combos = set()

        pa_a = file_a["parsed"]
        if pa_a and pa_a.rates:
            for r in pa_a.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_a[combo] = r

        pa_b = file_b["parsed"]
        if pa_b and pa_b.rates:
            for r in pa_b.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_b[combo] = r

        # Sort combos logically: by Origin, Dest, then Standard Bracket hierarchy
        bracket_order = {b: idx for idx, b in enumerate(STANDARD_BRACKETS)}
        def sort_key(c):
            org, dest, bracket = c
            return (org, dest, bracket_order.get(bracket, 99))
            
        combos_list = sorted(list(distinct_combos), key=sort_key)
        self.tbl_results.setRowCount(len(combos_list))

        # 8 Columns setup
        headers = [
            "Origin", 
            "Destination", 
            "Weight Break", 
            f"Rate ({name_a})", 
            f"Rate ({name_b})", 
            "Delta ($)", 
            "Delta (%)", 
            "Status"
        ]
        self.tbl_results.setColumnCount(len(headers))
        self.tbl_results.setHorizontalHeaderLabels(headers)

        missing_a_count = 0
        missing_b_count = 0
        cheaper_a_count = 0
        cheaper_b_count = 0
        equal_count = 0
        total_savings = 0.0
        
        self.comparison_data_rows = []

        for row_idx, combo in enumerate(combos_list):
            org, dest, bracket = combo
            
            r_a = rates_a.get(combo)
            r_b = rates_b.get(combo)
            
            val_a = r_a.freight_rate if r_a else None
            val_b = r_b.freight_rate if r_b else None
            
            text_a = f"{val_a:.2f}" if val_a is not None else "-"
            text_b = f"{val_b:.2f}" if val_b is not None else "-"
            
            if r_a and r_a.no_rate:
                text_a = "On Request"
            if r_b and r_b.no_rate:
                text_b = "On Request"
                
            delta_val_text = "-"
            delta_pct_text = "-"
            status_text = ""
            
            if val_a is not None and val_b is not None:
                delta_val = val_b - val_a
                delta_pct = (delta_val / val_a) * 100.0 if val_a > 0 else 0.0
                
                delta_val_text = f"{delta_val:+.2f}"
                delta_pct_text = f"{delta_pct:+.1f}%"
                
                if val_a == val_b:
                    status_text = "Rates Equal"
                    equal_count += 1
                else:
                    if val_b < val_a:
                        status_text = f"{name_b} Cheaper"
                        cheaper_b_count += 1
                        total_savings += (val_a - val_b)
                    else:
                        status_text = f"{name_a} Cheaper"
                        cheaper_a_count += 1
                
            elif val_a is not None and val_b is None:
                status_text = f"Missing in {name_b}"
                missing_b_count += 1
                
            elif val_a is None and val_b is not None:
                status_text = f"Missing in {name_a}"
                missing_a_count += 1
                
            # Export data structure
            self.comparison_data_rows.append({
                "Origin": org,
                "Destination": dest,
                "Weight Break": bracket,
                f"Rate ({name_a})": val_a if val_a is not None else "Missing",
                f"Rate ({name_b})": val_b if val_b is not None else "Missing",
                "Delta ($)": delta_val_text,
                "Delta (%)": delta_pct_text,
                "Status": status_text
            })

        # ----------------------------------------------------
        # 1. Populate Detailed Table (matched rates only!)
        # ----------------------------------------------------
        detailed_rows = [r for r in self.comparison_data_rows if "Missing in" not in r["Status"]]
        self.tbl_detailed.setRowCount(len(detailed_rows))
        self.tbl_detailed.setColumnCount(8)
        self.tbl_detailed.setHorizontalHeaderLabels([
            "Origin", "Destination", "Weight Break", 
            f"Rate ({name_a})", f"Rate ({name_b})", 
            "Delta ($)", "Delta (%)", "Status"
        ])
        
        for idx, row in enumerate(detailed_rows):
            self.tbl_detailed.setItem(idx, 0, QTableWidgetItem(row["Origin"]))
            self.tbl_detailed.setItem(idx, 1, QTableWidgetItem(row["Destination"]))
            self.tbl_detailed.setItem(idx, 2, QTableWidgetItem(row["Weight Break"]))
            
            val_a = row[f"Rate ({name_a})"]
            val_b = row[f"Rate ({name_b})"]
            text_a = f"{val_a:.2f}" if isinstance(val_a, (int, float)) else str(val_a)
            text_b = f"{val_b:.2f}" if isinstance(val_b, (int, float)) else str(val_b)
            
            self.tbl_detailed.setItem(idx, 3, QTableWidgetItem(text_a))
            self.tbl_detailed.setItem(idx, 4, QTableWidgetItem(text_b))
            
            item_delta_val = QTableWidgetItem(row["Delta ($)"])
            item_delta_pct = QTableWidgetItem(row["Delta (%)"])
            item_status = QTableWidgetItem(row["Status"])
            
            if row["Status"] == f"{name_b} Cheaper":
                item_delta_val.setForeground(QColor("#10B981"))
                item_delta_pct.setForeground(QColor("#10B981"))
                item_status.setForeground(QColor("#10B981"))
            elif row["Status"] == f"{name_a} Cheaper":
                item_delta_val.setForeground(QColor("#EF4444"))
                item_delta_pct.setForeground(QColor("#EF4444"))
                item_status.setForeground(QColor("#EF4444"))
            else:
                item_status.setForeground(QColor("#AAAAAA"))
                
            self.tbl_detailed.setItem(idx, 5, item_delta_val)
            self.tbl_detailed.setItem(idx, 6, item_delta_pct)
            self.tbl_detailed.setItem(idx, 7, item_status)

        # ----------------------------------------------------
        # 2. Populate Lane Rate Grid Table (with actual rates!)
        # ----------------------------------------------------
        unique_lanes = sorted(list(set((r["Origin"], r["Destination"]) for r in self.comparison_data_rows)))
        self.tbl_lane_grid.setRowCount(len(unique_lanes))
        
        lane_grid_headers = [
            "Origin", "Destination",
            f"MIN ({name_a})", f"MIN ({name_b})",
            f"LTL ({name_a})", f"LTL ({name_b})",
            f"500 ({name_a})", f"500 ({name_b})",
            f"1000 ({name_a})", f"1000 ({name_b})",
            f"2000 ({name_a})", f"2000 ({name_b})",
            f"5000 ({name_a})", f"5000 ({name_b})",
            f"10000 ({name_a})", f"10000 ({name_b})",
            "Overall Winner"
        ]
        self.tbl_lane_grid.setColumnCount(len(lane_grid_headers))
        self.tbl_lane_grid.setHorizontalHeaderLabels(lane_grid_headers)
        
        for idx, (org, dest) in enumerate(unique_lanes):
            self.tbl_lane_grid.setItem(idx, 0, QTableWidgetItem(org))
            self.tbl_lane_grid.setItem(idx, 1, QTableWidgetItem(dest))
            
            bracket_wins_a = 0
            bracket_wins_b = 0
            bracket_equals = 0
            is_missing = False
            missing_carrier_name = ""
            
            for b_idx, b in enumerate(STANDARD_BRACKETS):
                combo = (org, dest, b)
                r_a = rates_a.get(combo)
                r_b = rates_b.get(combo)
                
                val_a = r_a.freight_rate if r_a else None
                val_b = r_b.freight_rate if r_b else None
                
                text_a = f"{val_a:.2f}" if val_a is not None else "-"
                text_b = f"{val_b:.2f}" if val_b is not None else "-"
                
                if r_a and r_a.no_rate:
                    text_a = "On Request"
                if r_b and r_b.no_rate:
                    text_b = "On Request"
                    
                item_a = QTableWidgetItem(text_a)
                item_b = QTableWidgetItem(text_b)
                
                if val_a is not None and val_b is not None:
                    if val_a == val_b:
                        bracket_equals += 1
                    elif val_b < val_a:
                        bracket_wins_b += 1
                        item_b.setForeground(QColor("#10B981"))
                    else:
                        bracket_wins_a += 1
                        item_a.setForeground(QColor("#10B981"))
                elif val_a is not None and val_b is None:
                    is_missing = True
                    missing_carrier_name = name_b
                    item_b.setText("Missing")
                    item_b.setForeground(QColor("#EF4444"))
                elif val_a is None and val_b is not None:
                    is_missing = True
                    missing_carrier_name = name_a
                    item_a.setText("Missing")
                    item_a.setForeground(QColor("#EF4444"))
                    
                self.tbl_lane_grid.setItem(idx, 2 + b_idx * 2, item_a)
                self.tbl_lane_grid.setItem(idx, 2 + b_idx * 2 + 1, item_b)
                
            if is_missing:
                overall_text = f"Missing in {missing_carrier_name}"
                color = QColor("#F59E0B")
            else:
                if bracket_wins_a > bracket_wins_b:
                    overall_text = f"{name_a} Cheaper"
                    color = QColor("#EF4444")
                elif bracket_wins_b > bracket_wins_a:
                    overall_text = f"{name_b} Cheaper"
                    color = QColor("#10B981")
                else:
                    overall_text = "Tie / Equal"
                    color = QColor("#AAAAAA")
                    
            item_overall = QTableWidgetItem(overall_text)
            item_overall.setForeground(color)
            self.tbl_lane_grid.setItem(idx, 16, item_overall)

        # ----------------------------------------------------
        # 3. Populate Weight Slab Summary Table
        # ----------------------------------------------------
        self.tbl_slab_summary.setRowCount(len(STANDARD_BRACKETS))
        self.tbl_slab_summary.setColumnCount(5)
        self.tbl_slab_summary.setHorizontalHeaderLabels([
            "Weight Break", "Winner Carrier", f"{name_a} Wins", f"{name_b} Wins", "Equal Points"
        ])
        
        for idx, b in enumerate(STANDARD_BRACKETS):
            b_rows = [r for r in self.comparison_data_rows if r["Weight Break"] == b]
            wins_a = sum(1 for r in b_rows if r["Status"] == f"{name_a} Cheaper")
            wins_b = sum(1 for r in b_rows if r["Status"] == f"{name_b} Cheaper")
            equals = sum(1 for r in b_rows if r["Status"] == "Rates Equal")
            
            if wins_a > wins_b:
                winner = f"{name_a} Cheaper"
                color = QColor("#EF4444")
            elif wins_b > wins_a:
                winner = f"{name_b} Cheaper"
                color = QColor("#10B981")
            elif wins_a == 0 and wins_b == 0 and equals == 0:
                winner = "No Data"
                color = QColor("#AAAAAA")
            else:
                winner = "Tie / Equal"
                color = QColor("#AAAAAA")
                
            self.tbl_slab_summary.setItem(idx, 0, QTableWidgetItem(b))
            item_winner = QTableWidgetItem(winner)
            item_winner.setForeground(color)
            self.tbl_slab_summary.setItem(idx, 1, item_winner)
            self.tbl_slab_summary.setItem(idx, 2, QTableWidgetItem(str(wins_a)))
            self.tbl_slab_summary.setItem(idx, 3, QTableWidgetItem(str(wins_b)))
            self.tbl_slab_summary.setItem(idx, 4, QTableWidgetItem(str(equals)))

        # ----------------------------------------------------
        # 4. Populate Missing Lanes Table
        # ----------------------------------------------------
        missing_lanes_rows = []
        missing_lanes_set = set()
        for r in self.comparison_data_rows:
            status = r["Status"]
            if "Missing in" in status:
                missing_lanes_set.add((r["Origin"], r["Destination"], status))
        
        for org, dest, status in sorted(list(missing_lanes_set)):
            missing_lanes_rows.append({
                "Origin": org,
                "Destination": dest,
                "Status": status
            })
            
        self.tbl_missing.setRowCount(len(missing_lanes_rows))
        self.tbl_missing.setColumnCount(3)
        self.tbl_missing.setHorizontalHeaderLabels(["Origin", "Destination", "Status"])
        
        for idx, row in enumerate(missing_lanes_rows):
            self.tbl_missing.setItem(idx, 0, QTableWidgetItem(row["Origin"]))
            self.tbl_missing.setItem(idx, 1, QTableWidgetItem(row["Destination"]))
            item_status = QTableWidgetItem(row["Status"])
            item_status.setForeground(QColor("#F59E0B"))
            self.tbl_missing.setItem(idx, 2, item_status)

        # Clear and populate Stats Cards
        for i in reversed(range(self.stats_layout.count())):
            w = self.stats_layout.takeAt(i).widget()
            if w:
                w.deleteLater()

        total_comparisons = len(combos_list)
        
        card_total = self._create_stats_card("Total Comparisons", f"{total_comparisons} entries", "#F59E0B")
        
        color_a = "#10B981" if cheaper_a_count > cheaper_b_count else "#3E3E42"
        card_wins_a = self._create_stats_card(f"{name_a} Cheaper", f"{cheaper_a_count} wins", color_a)
        
        color_b = "#10B981" if cheaper_b_count > cheaper_a_count else "#3E3E42"
        card_wins_b = self._create_stats_card(f"{name_b} Cheaper", f"{cheaper_b_count} wins", color_b)
        
        missing_total_count = len(missing_lanes_rows)
        missing_color = "#EF4444" if missing_total_count > 0 else "#3E3E42"
        card_missing = self._create_stats_card("Missing Lanes", f"{name_a}: {missing_a_count} | {name_b}: {missing_b_count}", missing_color)
        
        self.stats_layout.addWidget(card_total)
        self.stats_layout.addWidget(card_wins_a)
        self.stats_layout.addWidget(card_wins_b)
        self.stats_layout.addWidget(card_missing)

        self.tbl_detailed.resizeColumnsToContents()
        self.tbl_lane_grid.resizeColumnsToContents()
        self.tbl_slab_summary.resizeColumnsToContents()
        self.tbl_missing.resizeColumnsToContents()
        self.stack.setCurrentIndex(4)  # Move to results screen

    def export_excel(self):
        if not hasattr(self, "comparison_data_rows") or not self.comparison_data_rows:
            QMessageBox.warning(self, "Export Failed", "No comparison data to export.")
            return

        import pandas as pd
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Excel Report", "rate_comparison_report.xlsx", "Excel Files (*.xlsx)"
        )
        
        fallback_dir = "/home/grace/Downloads/apeiron_output"
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, "rate_comparison_report.xlsx")

        success_paths = []
        
        # Prepare display names for the compared sides A and B
        file_a = None
        file_b = None
        for f in self.selected_files:
            if f.get("flag") == "Old":
                file_a = f
            elif f.get("flag") == "New":
                file_b = f
        if not file_a and self.selected_files:
            file_a = self.selected_files[0]
        if not file_b and len(self.selected_files) > 1:
            file_b = self.selected_files[1]
        if not file_b:
            file_b = file_a
            
        name_a = file_a["carrier"]
        if file_a.get("flag") == "Old":
            name_a += " (Old)"
        elif file_a.get("flag") == "New":
            name_a += " (New)"
        name_b = file_b["carrier"]
        if file_b.get("flag") == "Old":
            name_b += " (Old)"
        elif file_b.get("flag") == "New":
            name_b += " (New)"
        if name_a == name_b:
            name_a += " [A]"
            name_b += " [B]"

        STANDARD_BRACKETS = ["MIN", "LTL", "500", "1000", "2000", "5000", "10000"]
        bracket_order = {b: idx for idx, b in enumerate(STANDARD_BRACKETS)}
        def match_bracket(r) -> str:
            if r.source_locator and "Col:" in r.source_locator:
                lbl = r.source_locator.split("Col:")[-1].strip().upper()
                if lbl in STANDARD_BRACKETS:
                    return lbl
            if r.weight_break_hi is not None:
                val = r.weight_break_hi
                if val == 0.0: return "MIN"
                if val == 150.0: return "LTL"
                if val == 500.0: return "500"
                if val == 1000.0: return "1000"
                if val == 2000.0: return "2000"
                if val == 5000.0: return "5000"
                if val == 10000.0: return "10000"
            return "MIN"

        rates_a = {}
        rates_b = {}
        distinct_combos = set()
        pa_a = file_a["parsed"]
        if pa_a and pa_a.rates:
            for r in pa_a.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_a[combo] = r
        pa_b = file_b["parsed"]
        if pa_b and pa_b.rates:
            for r in pa_b.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_b[combo] = r

        def write_styled_excel(file_path):
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                # 1. Split out Matched vs Missing
                detailed_rows = [r for r in self.comparison_data_rows if "Missing in" not in r["Status"]]
                df_detailed = pd.DataFrame(detailed_rows)
                
                missing_lanes_set = set()
                for r in self.comparison_data_rows:
                    status = r["Status"]
                    if "Missing in" in status:
                        missing_lanes_set.add((r["Origin"], r["Destination"], status))
                
                missing_lanes_rows = []
                for org, dest, status in sorted(list(missing_lanes_set)):
                    missing_lanes_rows.append({
                        "Origin": org,
                        "Destination": dest,
                        "Status": status
                    })
                df_missing = pd.DataFrame(missing_lanes_rows) if missing_lanes_rows else pd.DataFrame(columns=["Origin", "Destination", "Status"])

                # 2. Lane Rate Grid Analysis (Side-by-Side Rates!)
                lane_wins_rows = []
                unique_lanes = sorted(list(set((r["Origin"], r["Destination"]) for r in self.comparison_data_rows)))
                for org, dest in unique_lanes:
                    row_data = {
                        "Origin": org,
                        "Destination": dest
                    }
                    
                    bracket_wins_a = 0
                    bracket_wins_b = 0
                    bracket_equals = 0
                    is_missing = False
                    missing_carrier_name = ""
                    
                    for b in STANDARD_BRACKETS:
                        combo = (org, dest, b)
                        r_a = rates_a.get(combo)
                        r_b = rates_b.get(combo)
                        
                        val_a = r_a.freight_rate if r_a else None
                        val_b = r_b.freight_rate if r_b else None
                        
                        text_a = f"{val_a:.2f}" if val_a is not None else "-"
                        text_b = f"{val_b:.2f}" if val_b is not None else "-"
                        
                        if r_a and r_a.no_rate:
                            text_a = "On Request"
                        if r_b and r_b.no_rate:
                            text_b = "On Request"
                            
                        row_data[f"MIN ({name_a})" if b == "MIN" else f"{b} ({name_a})"] = text_a
                        row_data[f"MIN ({name_b})" if b == "MIN" else f"{b} ({name_b})"] = text_b
                        
                        if val_a is not None and val_b is not None:
                            if val_a == val_b:
                                bracket_equals += 1
                            elif val_b < val_a:
                                bracket_wins_b += 1
                            else:
                                bracket_wins_a += 1
                        elif val_a is not None and val_b is None:
                            is_missing = True
                            missing_carrier_name = name_b
                        elif val_a is None and val_b is not None:
                            is_missing = True
                            missing_carrier_name = name_a
                            
                    if is_missing:
                        row_data["Overall Winner"] = f"Missing in {missing_carrier_name}"
                    else:
                        if bracket_wins_a > bracket_wins_b:
                            row_data["Overall Winner"] = f"{name_a} Cheaper"
                        elif bracket_wins_b > bracket_wins_a:
                            row_data["Overall Winner"] = f"{name_b} Cheaper"
                        else:
                            row_data["Overall Winner"] = "Tie / Equal"
                            
                    lane_wins_rows.append(row_data)
                df_lane_wins = pd.DataFrame(lane_wins_rows)

                # 3. Weight Bracket Wins Summary
                bracket_summary_rows = []
                for b in STANDARD_BRACKETS:
                    b_rows = [r for r in self.comparison_data_rows if r["Weight Break"] == b]
                    wins_a = sum(1 for r in b_rows if r["Status"] == f"{name_a} Cheaper")
                    wins_b = sum(1 for r in b_rows if r["Status"] == f"{name_b} Cheaper")
                    equals = sum(1 for r in b_rows if r["Status"] == "Rates Equal")
                    
                    if wins_a > wins_b:
                        winner = f"{name_a} Cheaper"
                    elif wins_b > wins_a:
                        winner = f"{name_b} Cheaper"
                    elif wins_a == 0 and wins_b == 0 and equals == 0:
                        winner = "No Data"
                    else:
                        winner = "Tie / Equal"
                        
                    bracket_summary_rows.append({
                        "Weight Break": b,
                        "Winner Carrier": winner,
                        f"{name_a} Wins": wins_a,
                        f"{name_b} Wins": wins_b,
                        "Equal Points": equals
                    })
                df_bracket_wins = pd.DataFrame(bracket_summary_rows)

                # 4. Core Calculations for Executive Summary
                missing_a_count = len([r for r in missing_lanes_rows if f"Missing in {name_a}" in r["Status"]])
                missing_b_count = len([r for r in missing_lanes_rows if f"Missing in {name_b}" in r["Status"]])
                cheaper_a_count = sum(1 for r in self.comparison_data_rows if r["Status"] == f"{name_a} Cheaper")
                cheaper_b_count = sum(1 for r in self.comparison_data_rows if r["Status"] == f"{name_b} Cheaper")
                equal_count = sum(1 for r in self.comparison_data_rows if r["Status"] == "Rates Equal")
                
                total_savings = 0.0
                name_a_col = f"Rate ({name_a})"
                name_b_col = f"Rate ({name_b})"
                for r in self.comparison_data_rows:
                    status = r["Status"]
                    if f"{name_b} Cheaper" in status:
                        val_a = r[name_a_col]
                        val_b = r[name_b_col]
                        if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                            total_savings += (val_a - val_b)

                summary_data = []
                summary_data.append({"KPI Metric": "Total Lanes/Weight Breaks compared", "Value": str(len(self.comparison_data_rows))})
                summary_data.append({"KPI Metric": f"{name_a} Cheaper (Wins)", "Value": str(cheaper_a_count)})
                summary_data.append({"KPI Metric": f"{name_b} Cheaper (Wins)", "Value": str(cheaper_b_count)})
                summary_data.append({"KPI Metric": "Equal Rate Points", "Value": str(equal_count)})
                summary_data.append({"KPI Metric": f"Unique Lanes Missing in {name_a}", "Value": str(missing_a_count)})
                summary_data.append({"KPI Metric": f"Unique Lanes Missing in {name_b}", "Value": str(missing_b_count)})
                summary_data.append({"KPI Metric": "Total Potential Savings ($)", "Value": f"${total_savings:,.2f}"})
                df_summary = pd.DataFrame(summary_data)

                # Write sheets
                df_summary.to_excel(writer, index=False, sheet_name="Executive Summary")
                df_detailed.to_excel(writer, index=False, sheet_name="Detailed Rates Comparison")
                df_missing.to_excel(writer, index=False, sheet_name="Missing Lanes Report")
                df_lane_wins.to_excel(writer, index=False, sheet_name="Lane Wins Analysis")
                df_bracket_wins.to_excel(writer, index=False, sheet_name="Weight Bracket Wins")

                # Style autofit
                workbook = writer.book
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    df_to_use = df_summary if sheet_name == "Executive Summary" else (
                        df_detailed if sheet_name == "Detailed Rates Comparison" else (
                            df_missing if sheet_name == "Missing Lanes Report" else (
                                df_lane_wins if sheet_name == "Lane Wins Analysis" else df_bracket_wins
                            )
                        )
                    )
                    for col_num, col_name in enumerate(df_to_use.columns):
                        max_len = max(df_to_use[col_name].astype(str).map(len).max(), len(col_name)) + 3
                        worksheet.set_column(col_num, col_num, max_len)

        try:
            write_styled_excel(fallback_path)
            success_paths.append(fallback_path)
        except Exception as e:
            logger.error("Fallback export failed: %s", e)

        if path:
            try:
                write_styled_excel(path)
                success_paths.append(path)
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Could not save file to {path}: {e}")
                return

        if success_paths:
            msg = f"Excel Report exported successfully to:\n" + "\n".join(success_paths)
            QMessageBox.information(self, "Export Success", msg)

    def export_pdf(self):
        if not hasattr(self, "comparison_data_rows") or not self.comparison_data_rows:
            QMessageBox.warning(self, "Export Failed", "No comparison data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF Report", "rate_comparison_report.pdf", "PDF Files (*.pdf)"
        )
        
        fallback_dir = "/home/grace/Downloads/apeiron_output"
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, "rate_comparison_report.pdf")

        # Find display names
        first_row = self.comparison_data_rows[0]
        cols = list(first_row.keys())
        name_a_col = cols[3]
        name_b_col = cols[4]
        
        name_a = name_a_col[6:-1]
        name_b = name_b_col[6:-1]

        # Prepare display names for the compared sides A and B
        file_a = None
        file_b = None
        for f in self.selected_files:
            if f.get("flag") == "Old":
                file_a = f
            elif f.get("flag") == "New":
                file_b = f
        if not file_a and self.selected_files:
            file_a = self.selected_files[0]
        if not file_b and len(self.selected_files) > 1:
            file_b = self.selected_files[1]
        if not file_b:
            file_b = file_a

        STANDARD_BRACKETS = ["MIN", "LTL", "500", "1000", "2000", "5000", "10000"]
        rates_a = {}
        rates_b = {}
        distinct_combos = set()
        
        def match_bracket(r) -> str:
            if r.source_locator and "Col:" in r.source_locator:
                lbl = r.source_locator.split("Col:")[-1].strip().upper()
                if lbl in STANDARD_BRACKETS:
                    return lbl
            if r.weight_break_hi is not None:
                val = r.weight_break_hi
                if val == 0.0: return "MIN"
                if val == 150.0: return "LTL"
                if val == 500.0: return "500"
                if val == 1000.0: return "1000"
                if val == 2000.0: return "2000"
                if val == 5000.0: return "5000"
                if val == 10000.0: return "10000"
            return "MIN"

        pa_a = file_a["parsed"]
        if pa_a and pa_a.rates:
            for r in pa_a.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_a[combo] = r
        pa_b = file_b["parsed"]
        if pa_b and pa_b.rates:
            for r in pa_b.rates:
                org = r.origin_city or r.origin_zip or "N/A"
                dest = r.dest_city or r.dest_zip or "N/A"
                bracket = match_bracket(r)
                combo = (org, dest, bracket)
                distinct_combos.add(combo)
                rates_b[combo] = r

        # 1. Splits
        detailed_rows = [r for r in self.comparison_data_rows if "Missing in" not in r["Status"]]
        
        missing_lanes_set = set()
        for r in self.comparison_data_rows:
            status = r["Status"]
            if "Missing in" in status:
                missing_lanes_set.add((r["Origin"], r["Destination"], status))
        
        missing_rows = []
        for org, dest, status in sorted(list(missing_lanes_set)):
            missing_rows.append({
                "Origin": org,
                "Destination": dest,
                "Status": status
            })

        # 2. Stats
        missing_a_count = len([r for r in missing_rows if f"Missing in {name_a}" in r["Status"]])
        missing_b_count = len([r for r in missing_rows if f"Missing in {name_b}" in r["Status"]])
        cheaper_a_count = sum(1 for r in self.comparison_data_rows if r["Status"] == f"{name_a} Cheaper")
        cheaper_b_count = sum(1 for r in self.comparison_data_rows if r["Status"] == f"{name_b} Cheaper")
        equal_count = sum(1 for r in self.comparison_data_rows if r["Status"] == "Rates Equal")
        
        total_savings = 0.0
        for r in self.comparison_data_rows:
            status = r["Status"]
            if f"{name_b} Cheaper" in status:
                val_a = r[name_a_col]
                val_b = r[name_b_col]
                if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
                    total_savings += (val_a - val_b)

        # 3. HTML tables builders
        detailed_headers = ["Origin", "Destination", "Weight Break", name_a_col, name_b_col, "Delta ($)", "Delta (%)", "Status"]
        detailed_headers_html = "".join(f"<th>{h}</th>" for h in detailed_headers)
        
        detailed_rows_html = []
        for row in detailed_rows:
             row_cells = []
             row_cells.append(f"<td>{row['Origin']}</td>")
             row_cells.append(f"<td>{row['Destination']}</td>")
             row_cells.append(f"<td>{row['Weight Break']}</td>")
             
             val_a = row.get(name_a_col)
             val_b = row.get(name_b_col)
             text_a = f"{val_a:.2f}" if isinstance(val_a, (int, float)) else str(val_a)
             text_b = f"{val_b:.2f}" if isinstance(val_b, (int, float)) else str(val_b)
             
             row_cells.append(f"<td>{text_a}</td>")
             row_cells.append(f"<td>{text_b}</td>")
             
             delta_val = row.get("Delta ($)")
             delta_pct = row.get("Delta (%)")
             status = row.get("Status")
             
             if "-" in delta_val and not delta_val.startswith("-0.00"):
                 row_cells.append(f"<td class='saving'>{delta_val}</td>")
                 row_cells.append(f"<td class='saving'>{delta_pct}</td>")
                 row_cells.append(f"<td class='saving'>{status}</td>")
             elif "+" in delta_val:
                 row_cells.append(f"<td class='increase'>{delta_val}</td>")
                 row_cells.append(f"<td class='increase'>{delta_pct}</td>")
                 row_cells.append(f"<td class='increase'>{status}</td>")
             else:
                 row_cells.append(f"<td>{delta_val}</td>")
                 row_cells.append(f"<td>{delta_pct}</td>")
                 row_cells.append(f"<td>{status}</td>")
             detailed_rows_html.append("<tr>" + "".join(row_cells) + "</tr>")

        # Missing lanes builder
        missing_rows_html = []
        for row in missing_rows:
            missing_rows_html.append(f"<tr><td>{row['Origin']}</td><td>{row['Destination']}</td><td class='increase'>{row['Status']}</td></tr>")

        # Lane wins builder (with actual rates side-by-side!)
        lane_wins_headers = ["Origin", "Destination", 
                             f"MIN ({name_a})", f"MIN ({name_b})",
                             f"LTL ({name_a})", f"LTL ({name_b})",
                             f"500 ({name_a})", f"500 ({name_b})",
                             f"1000 ({name_a})", f"1000 ({name_b})",
                             f"2000 ({name_a})", f"2000 ({name_b})",
                             f"5000 ({name_a})", f"5000 ({name_b})",
                             f"10000 ({name_a})", f"10000 ({name_b})",
                             "Overall Winner"]
        lane_wins_headers_html = "".join(f"<th>{h}</th>" for h in lane_wins_headers)

        lane_wins_html = []
        unique_lanes = sorted(list(set((r["Origin"], r["Destination"]) for r in self.comparison_data_rows)))
        for org, dest in unique_lanes:
            row_cells = [f"<td>{org}</td>", f"<td>{dest}</td>"]
            
            bracket_wins_a = 0
            bracket_wins_b = 0
            bracket_equals = 0
            is_missing = False
            missing_carrier_name = ""
            
            for b in STANDARD_BRACKETS:
                combo = (org, dest, b)
                r_a = rates_a.get(combo)
                r_b = rates_b.get(combo)
                
                val_a = r_a.freight_rate if r_a else None
                val_b = r_b.freight_rate if r_b else None
                
                text_a = f"{val_a:.2f}" if val_a is not None else "-"
                text_b = f"{val_b:.2f}" if val_b is not None else "-"
                
                if r_a and r_a.no_rate:
                    text_a = "On Request"
                if r_b and r_b.no_rate:
                    text_b = "On Request"
                    
                row_cells.append(f"<td>{text_a}</td>")
                row_cells.append(f"<td>{text_b}</td>")
                
                if val_a is not None and val_b is not None:
                    if val_a == val_b:
                        bracket_equals += 1
                    elif val_b < val_a:
                        bracket_wins_b += 1
                    else:
                        bracket_wins_a += 1
                elif val_a is not None and val_b is None:
                    is_missing = True
                    missing_carrier_name = name_b
                elif val_a is None and val_b is not None:
                    is_missing = True
                    missing_carrier_name = name_a
            
            if is_missing:
                overall_text = f"Missing in {missing_carrier_name}"
                overall_class = "increase"
            else:
                if bracket_wins_a > bracket_wins_b:
                    overall_text = f"{name_a} Cheaper"
                    overall_class = "increase"
                elif bracket_wins_b > bracket_wins_a:
                    overall_text = f"{name_b} Cheaper"
                    overall_class = "saving"
                else:
                    overall_text = "Tie / Equal"
                    overall_class = ""
                    
            row_cells.append(f"<td class='{overall_class}'>{overall_text}</td>")
            lane_wins_html.append("<tr>" + "".join(row_cells) + "</tr>")

        # Weight brackets summary builder
        bracket_rows_html = []
        for b in STANDARD_BRACKETS:
            b_rows = [r for r in self.comparison_data_rows if r["Weight Break"] == b]
            wins_a = sum(1 for r in b_rows if r["Status"] == f"{name_a} Cheaper")
            wins_b = sum(1 for r in b_rows if r["Status"] == f"{name_b} Cheaper")
            equals = sum(1 for r in b_rows if r["Status"] == "Rates Equal")
            
            if wins_a > wins_b:
                winner = f"{name_a} Cheaper"
            elif wins_b > wins_a:
                winner = f"{name_b} Cheaper"
            elif wins_a == 0 and wins_b == 0 and equals == 0:
                winner = "No Data"
            else:
                winner = "Tie / Equal"
                
            winner_class = "saving" if name_b in winner else ("increase" if name_a in winner else "")
            bracket_rows_html.append(
                f"<tr><td><b>{b}</b></td><td class='{winner_class}'>{winner}</td><td>{wins_a}</td><td>{wins_b}</td><td>{equals}</td></tr>"
            )

        import datetime
        html = f"""
        <html>
        <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 10px; color: #333; }}
            h1 {{ color: #00796B; text-align: center; margin-bottom: 10px; font-size: 16px; }}
            h2 {{ color: #3E2723; border-bottom: 2px solid #00796B; padding-bottom: 3px; font-size: 12px; margin-top: 15px; page-break-after: avoid; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 8px; }}
            th, td {{ border: 1px solid #CCC; padding: 4px 6px; text-align: left; }}
            th {{ background-color: #009688; color: #FFF; font-weight: bold; }}
            tr:nth-child(even) {{ background-color: #F9F9F9; }}
            .saving {{ color: #2E7D32; font-weight: bold; }}
            .increase {{ color: #C62828; font-weight: bold; }}
            .page-break {{ page-break-before: always; }}
        </style>
        </head>
        <body>
            <h1>APEIRON BRIDGE — Rate Intelligence Dimensions & Analysis Report</h1>
            <p style="text-align: right; font-size: 8px; color: #666;">Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
            
            <h2>1. Executive Summary KPIs</h2>
            <table style="width: 50%; font-size: 9px; margin-bottom: 15px;">
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Lane/Weight Breaks Compared</td><td>{len(self.comparison_data_rows)}</td></tr>
                <tr><td>{name_a} Cheaper (Wins)</td><td>{cheaper_a_count}</td></tr>
                <tr><td>{name_b} Cheaper (Wins)</td><td>{cheaper_b_count}</td></tr>
                <tr><td>Equal Rate Points</td><td>{equal_count}</td></tr>
                <tr><td>Unique Lanes Missing in {name_a}</td><td>{missing_a_count}</td></tr>
                <tr><td>Unique Lanes Missing in {name_b}</td><td>{missing_b_count}</td></tr>
                <tr><td>Total Potential Savings</td><td><b>${total_savings:,.2f}</b></td></tr>
            </table>

            <h2>2. Weight Bracket Winners</h2>
            <table>
                <thead>
                    <tr><th>Weight Break</th><th>Winner Carrier</th><th>{name_a} Wins</th><th>{name_b} Wins</th><th>Equal Points</th></tr>
                </thead>
                <tbody>
                    {"".join(bracket_rows_html)}
                </tbody>
            </table>

            <div class="page-break"></div>

            <h2>3. Detailed Lane Comparisons (Matched Rates)</h2>
            <table>
                <thead>
                    <tr>
                        {detailed_headers_html}
                    </tr>
                </thead>
                <tbody>
                    {"".join(detailed_rows_html)}
                </tbody>
            </table>

            <div class="page-break"></div>

            <h2>4. Lane-by-Lane Wins Analysis (Side-by-Side Rates)</h2>
            <table>
                <thead>
                    <tr>
                        {lane_wins_headers_html}
                    </tr>
                </thead>
                <tbody>
                    {"".join(lane_wins_html)}
                </tbody>
            </table>

            {"<div class='page-break'></div><h2>5. Asymmetrical Missing Lanes Report</h2><table><thead><tr><th>Origin</th><th>Destination</th><th>Status</th></tr></thead><tbody>" + "".join(missing_rows_html) + "</tbody></table>" if missing_rows_html else ""}
        </body>
        </html>
        """

        from PySide6.QtGui import QPdfWriter, QTextDocument, QPageLayout
        
        success_paths = []
        
        def render_pdf_file(file_path):
            writer = QPdfWriter(file_path)
            writer.setPageOrientation(QPageLayout.Landscape)
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(writer)

        try:
            render_pdf_file(fallback_path)
            success_paths.append(fallback_path)
        except Exception as e:
            logger.error("PDF fallback export failed: %s", e)

        if path:
            try:
                render_pdf_file(path)
                success_paths.append(path)
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Could not save PDF to {path}: {e}")
                return

        if success_paths:
            msg = "PDF Report exported successfully to:\n" + "\n".join(success_paths)
            QMessageBox.information(self, "Export Success", msg)
