import os
import unittest
import tempfile
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.rate_analysis_comparison.parsers.pdf_parser import PdfParser
from app.rate_analysis_comparison.parsers.base_parser import ParsedResult, ParseError

class TestPdfParser(unittest.TestCase):
    """
    Unit test suite for the PDF Parser of the Apeiron Bridge
    Rate Analysis & Comparison (RA&C) Module.
    """

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_minimal_text_pdf_bordered_parsing(self):
        """Test parsing of a generated text-based PDF containing a rate table."""
        file_path = os.path.join(self.test_dir.name, "test_agreement.pdf")

        # Create a basic PDF with some text using ReportLab
        c = canvas.Canvas(file_path, pagesize=letter)
        
        # Draw some metadata / context
        c.drawString(100, 750, "Carrier: Test Express")
        c.drawString(100, 735, "Effective: 01/01/2026")
        c.drawString(100, 720, "Mode: LTL")
        c.drawString(100, 705, "Origin: Toronto, ON")

        # Draw a table with gridlines to trigger Mode A
        c.rect(100, 500, 400, 150, stroke=1, fill=0) # Outer boundary
        
        # Horizontal lines (rows)
        c.line(100, 620, 500, 620) # Header separator
        c.line(100, 590, 500, 590)
        c.line(100, 560, 500, 560)
        c.line(100, 530, 500, 530)
        
        # Vertical lines (columns)
        c.line(200, 500, 200, 650)
        c.line(300, 500, 300, 650)
        c.line(400, 500, 400, 650)

        # Draw text inside table cells
        # Row 1 (Header)
        c.drawString(105, 630, "Destination")
        c.drawString(205, 630, "Min")
        c.drawString(305, 630, "500 Lbs")
        c.drawString(405, 630, "1000 Lbs")

        # Row 2 (Data 1)
        c.drawString(105, 600, "Montreal, QC")
        c.drawString(205, 600, "45.00")
        c.drawString(305, 600, "6.50")
        c.drawString(405, 600, "5.20")

        # Row 3 (Data 2)
        c.drawString(105, 570, "Vancouver, BC")
        c.drawString(205, 570, "95.00")
        c.drawString(305, 570, "12.80")
        c.drawString(405, 570, "11.10")

        # Row 4 (Data 3)
        c.drawString(105, 540, "Calgary, AB")
        c.drawString(205, 540, "85.00")
        c.drawString(305, 540, "11.20")
        c.drawString(405, 540, "9.80")

        # Row 5 (regular rate row or empty rate row)
        c.drawString(105, 510, "Halifax, NS")
        c.drawString(205, 510, "115.00")
        c.drawString(305, 510, "15.50")
        c.drawString(405, 510, "14.20")

        # Draw a second table (T&C clause table) to test clause extraction
        c.rect(100, 300, 400, 100, stroke=1, fill=0) # Outer boundary of second table
        
        # Horizontal lines (rows)
        c.line(100, 370, 500, 370) # Header separator
        c.line(100, 340, 500, 340)
        
        # Vertical lines (columns)
        c.line(250, 300, 250, 400)
        c.line(350, 300, 350, 400)
        
        # Header Row
        c.drawString(105, 380, "Service Name")
        c.drawString(255, 380, "Min Charge")
        c.drawString(355, 380, "Description")
        
        # Data Row 1
        c.drawString(105, 350, "Tailgate Service")
        c.drawString(255, 350, "75.00")
        c.drawString(355, 350, "Driver tailgate service fee")
        
        # Data Row 2
        c.drawString(105, 310, "Detention dry")
        c.drawString(255, 310, "85.00")
        c.drawString(355, 310, "2 hours free then $85.00 per hour detention fee")

        c.save()

        # Parse the PDF using our PdfParser
        parser = PdfParser()
        result = parser.parse(file_path)

        # Assertions
        self.assertIsInstance(result, ParsedResult)
        self.assertEqual(result.carrier_name, "Test Express")
        self.assertEqual(result.service_level, "LTL")
        
        # Verify rate extraction (Mode A)
        self.assertGreater(len(result.rates), 0)
        self.assertGreater(len(result.rate_rows), 0)
        
        # Verify first rate
        first_rate = result.rates[0]
        self.assertEqual(first_rate.dest_city, "Montreal")
        self.assertEqual(first_rate.dest_state, "QC")
        self.assertEqual(first_rate.minimum_charge, 45.00)

        # Verify clause extraction
        self.assertGreater(len(result.clauses), 0)
        self.assertGreater(len(result.clause_chunks), 0)
        
    def test_scanned_pdf_detection(self):
        """Test that scanned (blank text) PDFs raise ParseError gracefully."""
        file_path = os.path.join(self.test_dir.name, "scanned_agreement.pdf")
        
        # Create an empty/scanned mock PDF using ReportLab
        c = canvas.Canvas(file_path, pagesize=letter)
        c.rect(50, 50, 500, 700, stroke=1, fill=1) # Solid fill, no text
        c.save()

        parser = PdfParser()
        with self.assertRaises(ParseError) as context:
            parser.parse(file_path)
            
        self.assertIn("scanned", str(context.exception).lower())

    def test_transposed_destination_table(self):
        """PdfParser detects and correctly unpivots a destination-as-columns table."""
        file_path = os.path.join(self.test_dir.name, "transposed_agreement.pdf")
        
        c = canvas.Canvas(file_path, pagesize=letter)
        
        # Draw some metadata / context
        c.drawString(100, 750, "Carrier: Test Transposed")
        c.drawString(100, 735, "Effective: 01/01/2026")
        c.drawString(100, 720, "Mode: LTL")
        c.drawString(100, 705, "Origin: Toronto, ON")

        # Draw a bordered table to trigger Mode A
        c.rect(100, 500, 450, 150, stroke=1, fill=0) # Outer boundary: width 450 (ends at 550)
        
        # Horizontal lines (rows)
        c.line(100, 620, 550, 620) # Header separator
        c.line(100, 590, 550, 590)
        c.line(100, 560, 550, 560)
        
        # Vertical lines (columns)
        c.line(200, 500, 200, 650)
        c.line(310, 500, 310, 650)
        c.line(420, 500, 420, 650)

        # Draw text inside table cells
        # Row 1 (Header)
        c.drawString(105, 630, "NO. OF SKIDS")
        c.drawString(205, 630, "WINNIPEG, MB")
        c.drawString(315, 630, "CALGARY, AB")
        c.drawString(425, 630, "VANCOUVER, BC")

        # Row 2 (Data 1)
        c.drawString(105, 600, "1")
        c.drawString(205, 600, "$357.00")
        c.drawString(315, 600, "$405.00")
        c.drawString(425, 600, "$458.00")

        # Row 3 (Data 2)
        c.drawString(105, 570, "2")
        c.drawString(205, 570, "$420.00")
        c.drawString(315, 570, "$480.00")
        c.drawString(425, 570, "$530.00")

        c.save()

        # Parse using our PdfParser
        parser = PdfParser()
        result = parser.parse(file_path)

        # Assertions
        self.assertEqual(len(result.rate_rows), 6)
        destinations = {r.raw_fields["destination"] for r in result.rate_rows}
        self.assertIn("WINNIPEG, MB", destinations)
        self.assertIn("CALGARY, AB", destinations)
        self.assertIn("VANCOUVER, BC", destinations)
        skid_counts = {r.raw_fields["weight_break"] for r in result.rate_rows}
        self.assertIn("1", skid_counts)
        self.assertIn("2", skid_counts)

if __name__ == '__main__':
    unittest.main()
