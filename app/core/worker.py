"""
ReconciliationWorker — QThread-based worker for non-blocking reconciliation.

Runs SOAEngine.run() off the main UI thread so the application stays responsive
during processing of large files (200MB+). Emits progress signals for real-time
UI updates.
"""

from PySide6.QtCore import QThread, Signal
import traceback


class ReconciliationWorker(QThread):
    """
    Background worker thread for reconciliation processing.
    
    Signals:
        progress(int, str): Progress percentage (0-100) and status message
        finished(tuple): (df_result, saved_path, df_discrepancy, df_schema, insights_dict)
        error(str): Error message on failure
    """

    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, engine, generate_insights=True, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.generate_insights = generate_insights
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the current operation."""
        self._cancelled = True

    def run(self):
        """Execute reconciliation in background thread."""
        try:
            # Inject progress callback into engine
            self.engine._progress_callback = self._emit_progress
            self.engine._cancel_check = lambda: self._cancelled

            self.progress.emit(5, "Starting reconciliation engine...")
            
            result = self.engine.run()
            
            if self._cancelled:
                self.error.emit("Reconciliation cancelled by user.")
                return

            # Unpack 5 values from engine
            df_result, saved_path, df_discrepancy, df_schema, engine_insights = result
            
            # Use engine insights if available, otherwise generate
            insights = engine_insights or {}
            
            if not insights and self.generate_insights:
                self.progress.emit(85, "Generating AI insights...")
                try:
                    from app.core.insights import ReconciliationInsights
                    ref_names = [cfg[3] for cfg in self.engine.ref_configs if cfg]
                    analyzer = ReconciliationInsights(
                        df_result, df_discrepancy, ref_names,
                        amount_col=self.engine.amount_col,
                        date_col=self.engine.date_col
                    )
                    insights = analyzer.generate_all()
                except Exception as e:
                    print(f"[Worker] Insights generation warning: {e}")
                    traceback.print_exc()

            self.progress.emit(95, "Finalizing output...")
            self.finished.emit((df_result, saved_path, df_discrepancy, df_schema, insights))

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)

    def _emit_progress(self, pct, msg):
        """Thread-safe progress emission."""
        if not self._cancelled:
            self.progress.emit(pct, msg)
