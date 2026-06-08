from PySide6.QtCore import QThread, Signal
import traceback
from app.rate_analysis_comparison.parsers import parse_document

class ParsingWorker(QThread):
    """
    Background worker thread for agreement parsing.
    
    Signals:
        progress(int, str): Progress percentage (0-100) and status message
        finished(object): The ParsedAgreement object containing rates and clauses
        error(str): Error message on failure
    """
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the current parsing operation."""
        self._cancelled = True

    def run(self):
        """Execute parsing in the background thread."""
        try:
            self.progress.emit(5, "Initializing parser...")
            
            def emit_progress(pct, msg):
                if not self._cancelled:
                    self.progress.emit(pct, msg)
                    
            result = parse_document(self.file_path, progress_callback=emit_progress)
            
            if self._cancelled:
                self.error.emit("Parsing cancelled by user.")
                return
                
            self.progress.emit(100, "Parsing complete!")
            self.finished.emit(result)
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
