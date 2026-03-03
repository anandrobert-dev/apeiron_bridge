import sys
import os
from PySide6.QtWidgets import QApplication, QVBoxLayout

# Add project root
sys.path.append(os.getcwd())

from app.ui.schema_config import SchemaConfigWidget

def verify_schema_widget():
    app = QApplication.instance() or QApplication(sys.argv)
    
    print("Testing SchemaConfigWidget initialization...")
    
    ref_files = ["/tmp/Ref1.xlsx", "/tmp/Ref2.xlsx"]
    ref_cols = {
        "/tmp/Ref1.xlsx": ["ColA", "ColB"],
        "/tmp/Ref2.xlsx": ["ColX", "ColY"]
    }
    
    widget = SchemaConfigWidget(ref_files, ref_cols)
    
    # 1. Initial Init
    print("1. Initial State")
    # init_ui is called in __init__
    layout = widget.layout()
    if not layout:
        print("❌ Error: No layout found.")
        return
        
    print(f"   Layout children: {layout.count()}")
    # Expected: Label, Table, HBox(Buttons) -> 3 items
    
    # 2. Re-Init (Simulate set_data)
    print("2. Re-calling init_ui (Simulation of set_data)")
    widget.ref_files = ["/tmp/Ref3.csv"]
    widget.init_ui()
    
    print(f"   Layout children after re-init: {layout.count()}")
    
    if layout.count() > 3:
        print("❌ Error: Layout children increased! Duplication occurring.")
    else:
        print("✅ Success: Layout children count stable.")
        
    # 3. Check Table Columns
    print("3. Checking Table Structure")
    # Ref3 + Type + Output = 3 columns
    col_count = widget.table.columnCount()
    print(f"   Column Count: {col_count}")
    
    if col_count == 3:
        print("✅ Success: Column count correct for Ref3.")
    else:
        print(f"❌ Error: Expected 3 columns, got {col_count}")

    print("\nVerification Complete.")

if __name__ == "__main__":
    verify_schema_widget()
