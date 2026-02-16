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
        c_bg = QColor("#1E1E1E") # Match app background

        # 1. Background (Subtle Glow at bottom)
        grad_bg = QLinearGradient(0, h, 0, h/2)
        grad_bg.setColorAt(0, QColor(0, 229, 255, 30)) # Faint Cyan glow
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
        painter.setPen(QColor(255, 255, 255))
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

        # Module 1: SOA Reconciliation
        card_soa, self.btn_soa = self.create_action_card(
            "SOA Reconciliation",
            "Compare Statement of Account against Reference files.",
            "PrimaryButton"
        )
        actions_layout.addWidget(card_soa)

        # Module 2: Multi-File Comparison
        card_multi, self.btn_multi = self.create_action_card(
            "Multi-File Comparison",
            "Flexible matching across 2 to 5 distinct files.",
            "SecondaryButton"
        )
        actions_layout.addWidget(card_multi)

        # Module 3: CSV Matcher (Placeholder)
        card_csv, self.btn_csv = self.create_action_card(
            "Quick CSV Match",
            "Rapidly join two CSVs based on a common key.",
            "SecondaryButton"
        )
        actions_layout.addWidget(card_csv)

        layout.addLayout(actions_layout)
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Footer
        footer_text = "© 2026 Koinonia Technologies. All rights reserved.\nProprietary Software | Independent Development"
        footer = QLabel(footer_text)
        footer.setAlignment(Qt.AlignCenter)
        # Using a slightly different color to match the subtle look in the screenshot, likely similar to existing #666666 or #556B2F / Muted Blue
        # The screenshot text looks like a muted blue-ish grey. Let's stick to a clean grey/blue info text style.
        footer.setStyleSheet("color: #5c8a8a; font-size: 12px;") 
        layout.addWidget(footer)

    def create_action_card(self, title_text, desc_text, btn_object_name):
        """Creates a visual card for a module."""
        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(280)
        card.setFixedHeight(200)
        
        card_layout = QVBoxLayout(card)
        
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF; border: none;")
        lbl_title.setAlignment(Qt.AlignCenter)
        
        lbl_desc = QLabel(desc_text)
        lbl_desc.setStyleSheet("color: #AAAAAA; font-size: 13px; border: none;")
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignCenter)
        
        btn = QPushButton("Launch")
        btn.setObjectName(btn_object_name)
        
        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_desc)
        card_layout.addStretch()
        card_layout.addWidget(btn)
        
        return card, btn

