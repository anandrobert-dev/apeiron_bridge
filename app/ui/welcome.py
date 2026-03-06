from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame, QSpacerItem, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath, QBrush, QFont, QPixmap
from PySide6.QtCore import Qt, QPointF, QRectF

class ApeironBridgeWidget(QWidget):
    """
    A code-generated, distinct visualization of the 'Apeiron Bridge'.
    Draws a stylized, futuristic suspension bridge using QPainter.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250) # Increased height for logo space
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Load Logo
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logo_path = os.path.join(base_dir, "resources", "APIERON.png")
        self.logo_pixmap = QPixmap(logo_path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Dimensions
        w = self.width()
        h = self.height()
        
        # Colors (Apeiron Palette: Cyan, Purple, Gold)
        c_cyan = QColor("#00E5FF")
        c_purple = QColor("#D500F9")
        c_gold = QColor("#FFD700")
        
        # Dynamic Background Based on Theme
        is_dark = True
        main_win = self.window()
        if hasattr(main_win, 'current_theme'):
            is_dark = (main_win.current_theme == "dark")
            
        c_bg = QColor("#121212") if is_dark else QColor("#F8F9FA")

        # 1. Background (Subtle Glow at bottom)
        grad_bg = QLinearGradient(0, h, 0, h/2)
        glow_alpha = 30 if is_dark else 15
        grad_bg.setColorAt(0, QColor(0, 229, 255, glow_alpha)) # Faint Cyan glow
        grad_bg.setColorAt(1, c_bg)
        painter.fillRect(self.rect(), grad_bg)
        
        # 2. Draw Logo at Top
        if not self.logo_pixmap.isNull():
            # Scale logo to reasonable size (e.g. 200px width)
            target_w = 300
            scaled_logo = self.logo_pixmap.scaledToWidth(target_w, Qt.SmoothTransformation)
            local_x = (w - scaled_logo.width()) / 2
            local_y = 10 # Top margin
            painter.drawPixmap(int(local_x), int(local_y), scaled_logo)

        # Adjust bridge vertical position downwards to create gap for logo
        deck_y = h * 0.85
        tower_top_y = h * 0.55
        tower_x1 = w * 0.25
        tower_x2 = w * 0.75
        
        pen_tower = QPen(c_purple, 4)
        pen_tower.setCapStyle(Qt.RoundCap)
        painter.setPen(pen_tower)
        
        # Left Tower
        painter.drawLine(QPointF(tower_x1, deck_y + 20), QPointF(tower_x1, tower_top_y))
        # Right Tower
        painter.drawLine(QPointF(tower_x2, deck_y + 20), QPointF(tower_x2, tower_top_y))
        
        # 3. Draw Main Cables (Catenary Curves)
        path_cables = QPainterPath()
        path_cables.moveTo(0, deck_y * 0.8) # Start off-screen left
        # Curve to T1
        path_cables.quadTo(tower_x1 * 0.5, deck_y * 0.8, tower_x1, tower_top_y)
        # Curve T1 to T2 (The "Bridge" arch)
        path_cables.quadTo(w * 0.5, deck_y * 0.9, tower_x2, tower_top_y)
        # Curve T2 to end
        path_cables.quadTo(w - (tower_x1 * 0.5), deck_y * 0.8, w, deck_y * 0.8)
        
        grad_cable = QLinearGradient(0, 0, w, 0)
        grad_cable.setColorAt(0, c_cyan)
        grad_cable.setColorAt(0.5, c_gold)
        grad_cable.setColorAt(1, c_cyan)
        
        pen_cable = QPen(QBrush(grad_cable), 3)
        painter.setPen(pen_cable)
        painter.drawPath(path_cables)
        
        # 4. Draw Deck (The Connection)
        pen_deck = QPen(c_cyan, 2)
        painter.setPen(pen_deck)
        painter.drawLine(QPointF(0, deck_y), QPointF(w, deck_y))
        
        # 5. Vertical Suspenders
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        steps = 20
        for i in range(steps):
            x = w * (i / steps)
            # Find y on cable roughly (simplified for visual effect)
            # We just draw lines up to a certain height or check path, 
            # but for simple visual we can just clip or draw decorative lines.
            if x > tower_x1 and x < tower_x2:
                 # Center span
                 # Calculate approximate parabolic y
                 mid = w / 2
                 ydiff = (x - mid)**2 / ((tower_x2 - tower_x1)/2)**2
                 cable_y = tower_top_y + (deck_y * 0.9 - tower_top_y) * (0.1 + 0.9*ydiff)
                 # Actually that math is getting complex, let's just stick to "built-in" look
                 # Simple vertical lines from deck up
                 painter.drawLine(QPointF(x, deck_y), QPointF(x, deck_y - 15))
        
        # 6. Title Text "APEIRON" integrated (Moved down)
        text_color = QColor(255, 255, 255) if is_dark else QColor(26, 26, 26)
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(24)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5)
        painter.setFont(font)
        
        # Position drawing text below the deck or remove if redundant.
        # Keeping it but moving it down to not overlap bridge
        text_rect = QRectF(0, h * 0.90, w, 30)
        # painter.drawText(text_rect, Qt.AlignCenter, "APEIRON BRIDGE") # Optional: Remove if logo is enough
        # User said "APEIRON TAKE UP SIDE", maybe they want the text removed if logo is there?
        # But for now, let's just ensure NO overlap.
        # Ideally, with the logo at top, we don't need the text "APEIRON BRIDGE" in the middle/bottom.
        # But let's leave it at the very bottom or hide it if it clashes.
        # I will comment it out to be safe as the logo is "APEIRON".
        # painter.drawText(...) 


class WelcomeScreen(QWidget):
    """
    The initial dashboard shown to the user.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        # Header Section
        header_layout = QVBoxLayout()
        
        # Custom Bridge Widget
        self.bridge_widget = ApeironBridgeWidget()
        header_layout.addWidget(self.bridge_widget)
        
        layout.addLayout(header_layout)

        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

         # Main Actions Container
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(30)
        actions_layout.setAlignment(Qt.AlignCenter)

        # Google Colors
        c_blue = "#4285F4"
        c_red = "#EA4335"
        c_yellow = "#FBBC05"
        c_green = "#34A853"

        # Module 1: SOA Reconciliation (BLUE Theme)
        # Customized card with extra SOP button
        card_soa = QFrame()
        card_soa.setObjectName("Card")
        card_soa.setFixedWidth(280)
        card_soa.setFixedHeight(230) # Taller for extra space
        card_soa.setObjectName("Card")
        card_soa.setFixedWidth(280)
        card_soa.setFixedHeight(230) # Taller for extra space
        # Hardcoded styles removed; now handled by QSS Card selector
        card_soa.setStyleSheet(f"QFrame#Card {{ border: 2px solid {c_blue}; }}")
        
        card_soa_layout = QVBoxLayout(card_soa)
        
        lbl_title = QLabel("SOA Reconciliation")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c_blue}; border: none; background: transparent;")
        lbl_title.setAlignment(Qt.AlignCenter)
        
        lbl_desc = QLabel("Compare Statement of Account against Reference files.")
        lbl_desc.setObjectName("SubTitle") # Use QSS for color/font
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignCenter)
        
        self.btn_soa = QPushButton("Launch")
        self.btn_soa.setObjectName("PrimaryButton")
        # Button Style: Blue Filled
        self.btn_soa.setStyleSheet(f"""
            QPushButton {{
                background-color: {c_blue};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3367D6; }}
        """)
        
        self.btn_sop = QPushButton("SOP FOR SOA") 
        self.btn_sop.setObjectName("SecondaryButton") 
        # Button Style: Yellow Outline (Distinct)
        self.btn_sop.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 2px solid {c_yellow};
                color: {c_yellow};
                border-radius: 4px;
                padding: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: rgba(251, 188, 5, 0.1);
            }}
        """)
        self.btn_sop.clicked.connect(self.show_sop)
        
        card_soa_layout.addWidget(lbl_title)
        card_soa_layout.addWidget(lbl_desc)
        card_soa_layout.addStretch()
        card_soa_layout.addWidget(self.btn_soa)
        card_soa_layout.addWidget(self.btn_sop) 
        
        actions_layout.addWidget(card_soa)

        # Module 2: Multi-File Comparison (RED Theme)
        card_multi, self.btn_multi = self.create_action_card(
            "Multi-File Comparison",
            "Flexible matching across 2 to 5 distinct files.",
            "SecondaryButton",
            color=c_red
        )
        actions_layout.addWidget(card_multi)

        # Module 3: CSV Matcher (GREEN Theme)
        card_csv, self.btn_csv = self.create_action_card(
            "Quick CSV Match",
            "Rapidly join two CSVs based on a common key.",
            "SecondaryButton",
            color=c_green
        )
        actions_layout.addWidget(card_csv)

        layout.addLayout(actions_layout)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Footer
        footer_text = "© 2026 Koinonia Technologies. All rights reserved.\nProprietary Software | Independent Development"
        footer = QLabel(footer_text)
        footer.setAlignment(Qt.AlignCenter)
        # Using a slightly different color to match the subtle look in the screenshot, likely similar to existing #666666 or #556B2F / Muted Blue
        # Using a slightly different color to match the subtle look in the screenshot
        footer.setStyleSheet("color: #78909C; font-size: 11px;") 
        layout.addWidget(footer)

    def create_action_card(self, title_text, desc_text, btn_object_name, color="#FFFFFF"):
        """Creates a visual card for a module."""
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(280)
        card.setFixedHeight(200)
        
        # Apply Card Border Color
        card.setStyleSheet(f"QFrame#Card {{ border: 2px solid {color}; }}")
        
        card_layout = QVBoxLayout(card)
        
        lbl_title = QLabel(title_text)
        # Title Color matching theme
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color}; border: none; background: transparent;")
        lbl_title.setAlignment(Qt.AlignCenter)
        
        lbl_desc = QLabel(desc_text)
        lbl_desc.setObjectName("SubTitle")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignCenter)
        
        btn = QPushButton("Launch")
        btn.setObjectName(btn_object_name)
        # Button Color matching theme
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{ opacity: 0.8; }}
        """)
        
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)
        card_layout.addStretch()
        card_layout.addWidget(btn)
        
        return card, btn

    # Persist the SOP window instance
    sop_window = None

    def show_sop(self):
        """Opens a detached, non-blocking window to display the SOP markdown file."""
        from PySide6.QtWidgets import QDialog, QTextEdit, QVBoxLayout, QPushButton, QDialogButtonBox, QLabel, QWidget
        from PySide6.QtGui import QIcon
        import os
        
        # Check if window already exists
        if self.sop_window is None:
            # Create a new top-level window (no parent = detachable)
            self.sop_window = QDialog(None) 
            self.sop_window.setWindowTitle("SOP for SOA Reconciliation")
            self.sop_window.resize(900, 700)
            
            # Use Fusion style or inherit app style? Default is fine.
            # Make it look like a document viewer
            
            layout = QVBoxLayout(self.sop_window)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # Header Bar
            header = QWidget()
            header.setStyleSheet("background-color: #2D2D30; border-bottom: 2px solid #444;")
            header.setFixedHeight(40)
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(15, 0, 15, 0)
            
            lbl_title = QLabel("Standard Operating Procedure")
            lbl_title.setStyleSheet("color: #DDD; font-weight: bold; font-size: 14px;")
            header_layout.addWidget(lbl_title)
            
            header_layout.addStretch()
            
            # Application Language Toggle
            from PySide6.QtWidgets import QComboBox
            cbo_lang = QComboBox()
            cbo_lang.addItems(["English", "हिन्दी (Hindi)"])
            cbo_lang.setStyleSheet("""
                QComboBox {
                    background-color: #1E1E1E; color: #FFF; 
                    border: 1px solid #444; padding: 2px 10px; border-radius: 4px;
                }
            """)
            header_layout.addWidget(cbo_lang)

            layout.addWidget(header)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            # Use simple reliable styling for the container, content handles its own style
            text_edit.setStyleSheet("background-color: #1E1E1E; border: none;")
            
            # Load HTML content
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sop_path = os.path.join(base_dir, "resources", "SOP_SOA.html")
            
            def load_language(idx):
                if os.path.exists(sop_path):
                    with open(sop_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    head_part = content.split("</head>")[0] + "</head>" if "</head>" in content else ""
                    
                    if idx == 0:
                        start_tag = "<!-- ENGLISH_START -->"
                        end_tag = "<!-- ENGLISH_END -->"
                    else:
                        start_tag = "<!-- HINDI_START -->"
                        end_tag = "<!-- HINDI_END -->"
                        
                    start_idx = content.find(start_tag)
                    end_idx = content.find(end_tag)
                    
                    if start_idx != -1 and end_idx != -1:
                        body_part = content[start_idx + len(start_tag):end_idx]
                        text_edit.setHtml("<html>" + head_part + "<body>" + body_part + "</body></html>")
                    else:
                        text_edit.setHtml(content)
                else:
                    text_edit.setPlainText("SOP file not found.")

            cbo_lang.currentIndexChanged.connect(load_language)
            load_language(0) # Load English by default
                
            layout.addWidget(text_edit)
            
            # Close button footer
            footer = QWidget()
            footer.setStyleSheet("background-color: #2D2D30; border-top: 1px solid #444;")
            footer_layout = QHBoxLayout(footer)
            footer_layout.setContentsMargins(10, 10, 10, 10)
            footer_layout.addStretch()
            
            btn_close = QPushButton("Close Manual")
            btn_close.setMinimumWidth(120)
            btn_close.setStyleSheet("""
                QPushButton {
                    background-color: #444; color: white; border: none; padding: 8px; border-radius: 4px;
                }
                QPushButton:hover { background-color: #555; }
            """)
            btn_close.clicked.connect(self.sop_window.close)
            footer_layout.addWidget(btn_close)
            
            layout.addWidget(footer)
            
            # Clean up when closed? Or keep instance? 
            # If closed, just hide it? 
            # If closed, we might want to recreate it if language changes etc, but for now simple hide on close is fine or standard close.
            # QDialog close usually hides it unless WA_DeleteOnClose is set.
            # We will just let it be.
            
            # Ensure it is destroyed when the main app closes?
            # Since no parent, it might outlive main window if not careful.
            # We can connect app exit or just set attribute.
            self.sop_window.setAttribute(Qt.WA_DeleteOnClose)
            # But if delete on close, self.sop_window becomes dangling C++ object.
            # Safer: reset self.sop_window to None on destroyed signal.
            self.sop_window.destroyed.connect(lambda: setattr(self, 'sop_window', None))

        # Show the window non-modal
        self.sop_window.show()
        self.sop_window.raise_()
        self.sop_window.activateWindow()

