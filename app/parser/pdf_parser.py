import PyPDF2
import re

class PDFParser:
    def __init__(self):
        self.reader = None
    
    def parse(self, file_path):
        with open(file_path, 'rb') as file:
            self.reader = PyPDF2.PdfReader(file)
            text = ''
            for page in self.reader.pages:
                text += page.extract_text()
        return text
