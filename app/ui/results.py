
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QTabWidget, QScrollArea, QFrame, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
import pandas as pd


class ResultsScreen(QWidget):
    """
    Displays the reconciliation results with four tabs:
      1. Detailed View — full row-by-row match output
      2. Discrepancy Report — summarized delta/status per invoice
      3. Normalized Comparison — schema checker (multi-file only)
      4. Insights Dashboard — AI-powered analysis with KPIs, risk, patterns
    """
    go_home = Signal()
    go_back = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result_df = None
        self.discrepancy_df = None
        self.schema_df = None
        self.insights_data = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Reconciliation Results")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)
        
        self.lbl_stats = QLabel("Total Rows: 0")
        layout.addWidget(self.lbl_stats)

        # Tab Widget
        self.tabs = QTabWidget()
        
        # Tab 1: Detailed View
        self.table_detail = QTableWidget()
        self.tabs.addTab(self.table_detail, "📋 Detailed View")
        
        # Tab 2: Discrepancy Report
        self.table_discrepancy = QTableWidget()
        self.tabs.addTab(self.table_discrepancy, "⚠️ Discrepancy Report")
        
        # Tab 3: Normalized Comparison (Schema)
        self.table_schema = QTableWidget()
        self.tabs.addTab(self.table_schema, "🔍 Normalized Comparison")
        
        # Tab 4: Insights Dashboard
        self.insights_widget = QWidget()
        self.insights_scroll = QScrollArea()
        self.insights_scroll.setWidget(self.insights_widget)
        self.insights_scroll.setWidgetResizable(True)
        # Ensure scroll area content doesn't have a forced background that breaks themes
        self.insights_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.tabs.addTab(self.insights_scroll, "🧠 Insights Dashboard")
        
        layout.addWidget(self.tabs)
        
        # Footer
        footer = QHBoxLayout()
        self.btn_back = QPushButton("Back to Mapping")
        self.btn_back.clicked.connect(self.go_back.emit)
        
        self.btn_home = QPushButton("New Reconciliation")
        self.btn_home.clicked.connect(self.go_home.emit)
        
        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setObjectName("PrimaryButton")
        self.btn_export.clicked.connect(self.export_data)
        
        footer.addWidget(self.btn_back)
        footer.addWidget(self.btn_home)
        footer.addStretch()
        footer.addWidget(self.btn_export)
        layout.addLayout(footer)

    def display_results(self, df: pd.DataFrame, discrepancy_df: pd.DataFrame = None, 
                        schema_df: pd.DataFrame = None, insights: dict = None):
        self.result_df = df
        self.discrepancy_df = discrepancy_df
        self.schema_df = schema_df
        self.insights_data = insights
        
        # Update Stats
        total = len(df)
        disc_count = len(discrepancy_df) if discrepancy_df is not None and not discrepancy_df.empty else 0
        match_count = 0
        issue_count = 0
        if discrepancy_df is not None and not discrepancy_df.empty and 'Status' in discrepancy_df.columns:
            match_count = len(discrepancy_df[discrepancy_df['Status'] == 'MATCH'])
            issue_count = disc_count - match_count
        
        self.lbl_stats.setText(
            f"Total Rows: {total}  |  Invoices: {disc_count}  |  "
            f"Matches: {match_count}  |  Issues: {issue_count}"
        )
        
        # --- Tab 1: Detailed View ---
        self._populate_table(self.table_detail, df)
        
        # --- Tab 2: Discrepancy Report ---
        if discrepancy_df is not None and not discrepancy_df.empty:
            self._populate_table(self.table_discrepancy, discrepancy_df)
            self._colorize_discrepancy(self.table_discrepancy, discrepancy_df)
        else:
            self.table_discrepancy.setRowCount(0)
            self.table_discrepancy.setColumnCount(1)
            self.table_discrepancy.setHorizontalHeaderLabels(["Info"])
            self.table_discrepancy.setItem(0, 0, QTableWidgetItem("No discrepancy data available."))

        # --- Tab 3: Normalized Comparison ---
        idx = self.tabs.indexOf(self.table_schema)
        if schema_df is not None and not schema_df.empty:
            if idx == -1:
                self.tabs.insertTab(2, self.table_schema, "🔍 Normalized Comparison")
            self._populate_table(self.table_schema, schema_df)
            self._colorize_schema(self.table_schema, schema_df)
        else:
            if idx != -1:
                self.tabs.removeTab(idx)

        # --- Tab 4: Insights Dashboard ---
        if insights:
            self._build_insights_dashboard(insights)
            # Switch to Insights tab to show the AI analysis first
            self.tabs.setCurrentIndex(3)
        elif discrepancy_df is not None and not discrepancy_df.empty:
            self.tabs.setCurrentIndex(1)

    def _populate_table(self, table: QTableWidget, df: pd.DataFrame):
        """Populate a QTableWidget from a DataFrame."""
        preview_limit = 200
        preview_df = df.head(preview_limit)
        
        table.setColumnCount(len(preview_df.columns))
        table.setRowCount(len(preview_df))
        table.setHorizontalHeaderLabels(preview_df.columns.astype(str))
        
        for i in range(len(preview_df)):
            for j, val in enumerate(preview_df.iloc[i]):
                cell = QTableWidgetItem(str(val) if pd.notna(val) else "")
                table.setItem(i, j, cell)
                
        table.resizeColumnsToContents()

    # ──────────────────────────────────────────────────
    # INSIGHTS DASHBOARD BUILDER (TABBED)
    # ──────────────────────────────────────────────────
    def _build_insights_dashboard(self, insights):
        """Build a clean, tabbed insights dashboard from analysis results."""
        if self.insights_widget.layout():
            old = self.insights_widget.layout()
            while old.count():
                child = old.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
                elif child.layout():
                    while child.layout().count():
                        sub = child.layout().takeAt(0)
                        if sub.widget():
                            sub.widget().deleteLater()
            QWidget().setLayout(old)
        
        # Remove hardcoded background and color
        # Ensure it respects the theme by not forcing anything, but we might need a hint for some styles
        self.insights_widget.setStyleSheet("QWidget { background: transparent; }")
        
        layout = QVBoxLayout(self.insights_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # ── TITLE & TIMESTAMP ──
        header_layout = QHBoxLayout()
        title = QLabel("🧠 AI-Powered Reconciliation Insights")
        title.setObjectName("HeaderTitle") # Use QSS
        header_layout.addWidget(title)
        
        generated = insights.get("generated_at", "")
        if generated:
            ts = QLabel(f"Generated: {generated} (Metrics vs SOA)")
            ts.setObjectName("SubTitle")
            header_layout.addStretch()
            header_layout.addWidget(ts)
        
        layout.addLayout(header_layout)
        
        # ── TABS CONTAINER ──
        insights_tabs = QTabWidget()
        # QSS handle borders and tab styling now
        layout.addWidget(insights_tabs)
        
        def create_tab_page():
            page = QWidget()
            # Theme takes care of background
            p_layout = QVBoxLayout(page)
            p_layout.setSpacing(20)
            p_layout.setContentsMargins(20, 20, 20, 20)
            p_layout.setAlignment(Qt.AlignTop)
            return page, p_layout

        summary = insights.get("summary", {})
        
        # ── TAB 1: EXECUTIVE OVERVIEW ──
        if summary:
            page_exec, lay_exec = create_tab_page()
            
            lay_exec.addWidget(self._make_section("Executive KPIs", "Overall health score is based on match rates and discrepancy values."))
            health = summary.get("health_score", 0)
            kpis = [
                {"Metric": "Health Score (0-100)", "Value": f"{health}"},
                {"Metric": "Overall Match Rate (Avg against SOA)", "Value": f"{summary.get('match_rate', 0)}%"},
                {"Metric": "Total Discrepancies", "Value": str(summary.get('discrepancy_count', 0))},
                {"Metric": "Total Δ Value", "Value": f"${summary.get('total_discrepancy_value', 0):,.2f}"},
                {"Metric": "Total Ref Sources", "Value": str(summary.get('ref_count', 0))},
            ]
            lay_exec.addWidget(self._create_simple_table(kpis))

            ds = summary.get("data_summary", [])
            if ds:
                lay_exec.addWidget(self._make_section("Data Summary comparisons", "Total invoices, values, and match rates per file compared to the SOA."))
                formatted_ds = []
                for row in ds:
                    new_row = row.copy()
                    v = new_row.get("Total Value", 0)
                    new_row["Total Value"] = f"${v:,.2f}"
                    formatted_ds.append(new_row)
                lay_exec.addWidget(self._create_simple_table(formatted_ds))
                
            insights_tabs.addTab(page_exec, "📊 Executive Overview")

        # ── TAB 2: DISCREPANCIES & STATUS ──
        page_disc, lay_disc = create_tab_page()
        added_disc = False
        
        status_bd = summary.get("status_breakdown", {})
        if status_bd:
            lay_disc.addWidget(self._make_section("Status Breakdown", "Counts of each reconciliation status."))
            stat_list = [{"Status Type": k, "Count": v} for k, v in status_bd.items()]
            lay_disc.addWidget(self._create_simple_table(stat_list))
            added_disc = True
            
        top_disc = insights.get("top_discrepancies", pd.DataFrame())
        if not isinstance(top_disc, pd.DataFrame): top_disc = pd.DataFrame()
        if not top_disc.empty:
            lay_disc.addWidget(self._make_section("Top Discrepancies", "The largest absolute discrepancies found."))
            lay_disc.addWidget(self._create_df_table(top_disc))
            added_disc = True
            
        if added_disc:
            insights_tabs.addTab(page_disc, "⚠️ Discrepancies")

        # ── TAB 3: AI PATTERNS & RELIABILITY ──
        page_ai, lay_ai = create_tab_page()
        added_ai = False
        
        patterns = insights.get("patterns", [])
        if patterns:
            lay_ai.addWidget(self._make_section("Detected Patterns", "Systematic issues automatically flagged by AI."))
            lay_ai.addWidget(self._create_simple_table(patterns))
            added_ai = True

        source_rel = insights.get("source_reliability", pd.DataFrame())
        if not isinstance(source_rel, pd.DataFrame): source_rel = pd.DataFrame()
        if not source_rel.empty:
            lay_ai.addWidget(self._make_section("Source Reliability", "Grading accuracy and coverage of each reference file."))
            lay_ai.addWidget(self._create_df_table(source_rel))
            added_ai = True
            
        if added_ai:
            insights_tabs.addTab(page_ai, "🎯 Patterns & Reliability")

        # ── TAB 4: STATISTICAL ANALYSIS ──
        anomaly_data = insights.get("anomalies", {})
        if isinstance(anomaly_data, dict):
            stats = anomaly_data.get("stats", {})
            if stats:
                page_stat, lay_stat = create_tab_page()
                lay_stat.addWidget(self._make_section("Statistical Analysis", "Invoice amount distribution and outlier detection (IQR Method)."))
                stat_items = [
                    {"Statistic": "Mean Amount", "Value": f"${stats.get('mean', 0):,.2f}"},
                    {"Statistic": "Median Amount", "Value": f"${stats.get('median', 0):,.2f}"},
                    {"Statistic": "Std Deviation", "Value": f"${stats.get('std_dev', 0):,.2f}"},
                    {"Statistic": "Outliers Detected", "Value": f"{stats.get('outlier_count', 0)} ({stats.get('outlier_pct', 0)}%)"},
                ]
                lay_stat.addWidget(self._create_simple_table(stat_items))
                insights_tabs.addTab(page_stat, "📐 Statistical Analysis")

        # ── TAB 5: AGING ANALYSIS ──
        aging_data = insights.get("aging", pd.DataFrame())
        if not isinstance(aging_data, pd.DataFrame): aging_data = pd.DataFrame()
        if not aging_data.empty:
            page_age, lay_age = create_tab_page()
            lay_age.addWidget(self._make_section("Age Bucket Report", "Invoice distribution and risk categorization by age."))
            lay_age.addWidget(self._create_df_table(aging_data))
            insights_tabs.addTab(page_age, "📅 Aging Analysis")

    def _make_section(self, title, subtitle=""):
        """Create a standard section header."""
        widget = QWidget()
        vbox = QVBoxLayout(widget)
        vbox.setContentsMargins(0, 10, 0, 0)
        vbox.setSpacing(2)
        
        lbl = QLabel(title)
        lbl.setObjectName("HeaderTitle")
        lbl.setStyleSheet("font-size: 14px;")
        vbox.addWidget(lbl)
        
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("SubTitle")
            sub.setStyleSheet("font-size: 11px;")
            vbox.addWidget(sub)
            
        return widget

    def _create_simple_table(self, data_list):
        """Creates a readable QTableWidget from a list of dicts, left-aligned without stretching."""
        if not data_list:
            return QLabel("No data")

        _TABLE_QSS = """
            QTableWidget {
                background-color: #1A1A2E;
                color: #E0E0E0;
                gridline-color: #333355;
                border: 1px solid #333355;
                font-size: 13px;
                alternate-background-color: #16213E;
                selection-background-color: #7B2FBE;
                selection-color: #FFFFFF;
            }
            QTableWidget::item {
                color: #E0E0E0;
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #009688;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-right: 1px solid #00796B;
            }
        """
            
        table = QTableWidget()
        headers = list(data_list[0].keys())
        table.setColumnCount(len(headers))
        table.setRowCount(len(data_list))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setObjectName("DataTable")
        table.setStyleSheet(_TABLE_QSS)
        
        _text_color = QColor("#E0E0E0")
        for i, row_dict in enumerate(data_list):
            for j, key in enumerate(headers):
                val = row_dict.get(key, "")
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setForeground(QBrush(_text_color))
                table.setItem(i, j, item)
                
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        table.setMinimumWidth(min(1200, table.horizontalHeader().length() + 30))
        table.setMaximumHeight(min(300, 45 + len(data_list) * 35))
        layout.addWidget(table)
        layout.addStretch()
        return container

    def _create_df_table(self, df):
        """Creates a readable QTableWidget from a DataFrame, left-aligned without stretching."""
        _TABLE_QSS = """
            QTableWidget {
                background-color: #1A1A2E;
                color: #E0E0E0;
                gridline-color: #333355;
                border: 1px solid #333355;
                font-size: 13px;
                alternate-background-color: #16213E;
                selection-background-color: #7B2FBE;
                selection-color: #FFFFFF;
            }
            QTableWidget::item {
                color: #E0E0E0;
                padding: 4px 8px;
            }
            QHeaderView::section {
                background-color: #009688;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-right: 1px solid #00796B;
            }
        """
        table = QTableWidget()
        table.setColumnCount(len(df.columns))
        table.setRowCount(len(df))
        table.setHorizontalHeaderLabels(list(df.columns))
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setObjectName("DataTable")
        table.setStyleSheet(_TABLE_QSS)
        
        _text_color = QColor("#E0E0E0")
        for i in range(len(df)):
            for j, val in enumerate(df.iloc[i]):
                val_str = str(val) if pd.notna(val) else "—"
                item = QTableWidgetItem(val_str)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                item.setForeground(QBrush(_text_color))
                table.setItem(i, j, item)
                
        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        table.setMinimumWidth(min(1200, table.horizontalHeader().length() + 30))
        table.setMaximumHeight(min(400, 45 + len(df) * 35))
        layout.addWidget(table)
        layout.addStretch()
        return container

    def _colorize_discrepancy(self, table: QTableWidget, df: pd.DataFrame):
        """Apply color-coding to the discrepancy report table."""
        cols = list(df.columns)
        
        idx_delta = cols.index('Delta') if 'Delta' in cols else -1
        idx_status = cols.index('Status') if 'Status' in cols else -1
        
        # Color Palette Generation
        pal = self._get_theme_palette()
        clr_red_bg = pal['red_bg']
        clr_red_text = pal['red_text']
        clr_green_bg = pal['green_bg']
        clr_green_text = pal['green_text']
        clr_match_bg = pal['blue_bg']
        clr_match_text = pal['blue_text']
        clr_amber_bg = pal['amber_bg']
        clr_amber_text = pal['amber_text']
        
        for row_idx in range(min(len(df), 200)):
            row = df.iloc[row_idx]
            
            # Color Delta column
            if idx_delta >= 0:
                delta = row['Delta']
                item = table.item(row_idx, idx_delta)
                if item:
                    if delta < -0.01:
                        item.setBackground(QBrush(clr_red_bg))
                        item.setForeground(QBrush(clr_red_text))
                    elif delta > 0.01:
                        item.setBackground(QBrush(clr_amber_bg))
                        item.setForeground(QBrush(clr_amber_text))
                    else:
                        item.setBackground(QBrush(clr_green_bg))
                        item.setForeground(QBrush(clr_green_text))
            
            # Color Status column
            if idx_status >= 0:
                status = str(row['Status'])
                item = table.item(row_idx, idx_status)
                if item:
                    if "MATCH" in status and "MIS" not in status:
                        item.setBackground(QBrush(clr_match_bg))
                        item.setForeground(QBrush(clr_match_text))
                    elif "Overpaid" in status or "MISSING IN SOA" in status:
                        item.setBackground(QBrush(clr_red_bg))
                        item.setForeground(QBrush(clr_red_text))
                    elif "Underpaid" in status or "MISSING IN REF" in status:
                        item.setBackground(QBrush(clr_amber_bg))
                        item.setForeground(QBrush(clr_amber_text))
            
            # Color entire row background lightly based on status
            if idx_status >= 0:
                status = str(row['Status'])
                if "MATCH" in status and "MIS" not in status:
                    row_color = pal['row_match_tint']
                elif "Overpaid" in status or "MISSING" in status:
                    row_color = pal['row_error_tint']
                else:
                    row_color = None
                
                if row_color:
                    for col_idx in range(len(cols)):
                        cell = table.item(row_idx, col_idx)
                        if cell:
                            cell.setBackground(QBrush(row_color))

    def _colorize_schema(self, table: QTableWidget, df: pd.DataFrame):
        """Apply color-coding to the schema comparison table."""
        cols = list(df.columns)
        
        # Colors
        pal = self._get_theme_palette()
        clr_red_bg = pal['red_bg']
        clr_red_text = pal['red_text']
        clr_green_bg = pal['green_bg']
        clr_green_text = pal['green_text']
        clr_amber_bg = pal['amber_bg']
        clr_amber_text = pal['amber_text']
        
        for col_idx, col_name in enumerate(cols):
            if "Status" in col_name:
                for row_idx in range(min(len(df), 200)):
                    val = str(df.iloc[row_idx, col_idx])
                    item = table.item(row_idx, col_idx)
                    
                    if item:
                        if "MISMATCH" in val:
                            item.setBackground(QBrush(clr_red_bg))
                            item.setForeground(QBrush(clr_red_text))
                        elif "MATCH" in val and "PARTIAL" not in val:
                            item.setBackground(QBrush(clr_green_bg))
                            item.setForeground(QBrush(clr_green_text))
                        elif "PARTIAL" in val:
                            item.setBackground(QBrush(clr_amber_bg))
                            item.setForeground(QBrush(clr_amber_text))

    def _get_theme_palette(self):
        """Returns a dynamic color palette based on current theme."""
        is_dark = True
        main_win = self.window()
        if hasattr(main_win, 'current_theme'):
             is_dark = (main_win.current_theme == "dark")
        
        if is_dark:
            return {
                'red_bg': QColor("#3D1F1F"),
                'red_text': QColor("#FF8A80"),
                'green_bg': QColor("#1B3320"),
                'green_text': QColor("#A5D6A7"),
                'blue_bg': QColor("#1A237E"),
                'blue_text': QColor("#90CAF9"),
                'amber_bg': QColor("#3E2723"),
                'amber_text': QColor("#FFE082"),
                'row_match_tint': QColor("#1B2A1B"),
                'row_error_tint': QColor("#2A1B1B"),
            }
        else:
            return {
                'red_bg': QColor("#FFEBEE"),
                'red_text': QColor("#C62828"),
                'green_bg': QColor("#E8F5E9"),
                'green_text': QColor("#2E7D32"),
                'blue_bg': QColor("#E3F2FD"),
                'blue_text': QColor("#1565C0"),
                'amber_bg': QColor("#FFF8E1"),
                'amber_text': QColor("#EF6C00"),
                'row_match_tint': QColor("#F1F8E9"),
                'row_error_tint': QColor("#FFEBEE"),
            }

    def export_data(self):
        if self.result_df is None:
            return
            
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Results", "reconciliation_results.xlsx", "Excel Files (*.xlsx)"
        )
        
        if path:
            try:
                with pd.ExcelWriter(path, engine='xlsxwriter') as writer:
                    self.result_df.to_excel(writer, index=False, sheet_name='Detailed View')
                    if self.discrepancy_df is not None and not self.discrepancy_df.empty:
                        self.discrepancy_df.to_excel(writer, index=False, sheet_name='Discrepancy Report')
                    if self.schema_df is not None and not self.schema_df.empty:
                        self.schema_df.to_excel(writer, index=False, sheet_name='Normalized Comparison')
                    
                    # Restore Insights Export logic
                    if self.insights_data:
                        # 1. Insights Summary Sheet
                        summary = self.insights_data.get("summary", {})
                        insights_rows = []
                        insights_rows.append({"Metric": "Executive Summary", "Value": ""})
                        insights_rows.append({"Metric": "Match Rate", "Value": f"{summary.get('match_rate', 0)}%"})
                        insights_rows.append({"Metric": "Total Δ Value", "Value": f"${summary.get('total_discrepancy_value', 0):,.2f}"})
                        insights_rows.append({"Metric": "Health Score", "Value": f"{summary.get('health_score', 0)}/100"})
                        
                        patterns = self.insights_data.get("patterns", [])
                        if patterns:
                            insights_rows.append({"Metric": "Patterns Detected", "Value": len(patterns)})
                        
                        pd.DataFrame(insights_rows).to_excel(writer, index=False, sheet_name='Reconciliation Insights')
                        
                        # 2. Aging Analysis
                        aging = self.insights_data.get("aging", pd.DataFrame())
                        if not aging.empty:
                            aging.to_excel(writer, index=False, sheet_name='Aging Analysis')
                            
                        # 3. Risk Analysis
                        risk = self.insights_data.get("risk_scores", pd.DataFrame())
                        if not risk.empty:
                            risk.to_excel(writer, index=False, sheet_name='Risk Analysis')
                            
                QMessageBox.information(self, "Success", f"Data exported to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", str(e))
