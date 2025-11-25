"""
Document processing utilities for handling various file formats.
Supports PDF, Word, CSV, and plain text files.
"""

import os
from typing import Dict, List, Union
import pandas as pd
from pypdf import PdfReader
from docx import Document
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Processes documents for compliance reviewer system.
    Extracts text content from various formats.
    """

    def __init__(self):
        pass

    def load_document(self, file_path: str) -> str:
        """
        Load and extract text from a document file.

        Args:
            file_path: Path to the document file

        Returns:
            Extracted text content

        Raises:
            ValueError: If file format is unsupported
            FileNotFoundError: If file doesn't exist
        """
        file_extension = os.path.splitext(file_path)[1].lower()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        if file_extension not in ['.pdf', '.docx', '.doc', '.csv', '.txt', '.md']:
            raise ValueError(f"Unsupported file format: {file_extension}")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_size > 10 * 1024 * 1024:
            raise ValueError("File too large (max 10MB). Please provide a file under 10MB.")

        if file_extension == '.pdf':
            return self._load_pdf(file_path)
        elif file_extension == '.docx':
            return self._load_docx(file_path)
        elif file_extension == '.doc':
            return self._load_doc(file_path)
        elif file_extension == '.csv':
            return self._load_csv(file_path)
        elif file_extension in ['.txt', '.md']:
            return self._load_text(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def _load_doc(self, file_path: str) -> str:
        """
        Extract text from legacy Word .doc files using textract.

        Raises:
            ValueError: If textract cannot extract text
        """
        try:
            import textract  # Lazy import to keep optional dependency light
            raw = textract.process(file_path)
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                raise ValueError(f"No extractable text found in DOC: {file_path}")
            logger.info(f"Loaded DOC: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Error loading DOC {file_path}: {e}")
            raise ValueError(f"Failed to process .doc file. Please convert to .docx and retry. Details: {e}")

    def _load_pdf(self, file_path: str) -> str:
        """Extract text from PDF file."""
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + ("\n" if page_text else "")
            logger.info(f"Loaded PDF: {file_path}")
            text = text.strip()
            if not text:
                raise ValueError(f"No extractable text found in PDF: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Error loading PDF {file_path}: {e}")
            raise

    def _load_docx(self, file_path: str) -> str:
        """Extract text from Word document."""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            logger.info(f"Loaded DOCX: {file_path}")
            return text.strip()
        except Exception as e:
            logger.error(f"Error loading DOCX {file_path}: {e}")
            raise

    def _load_csv(self, file_path: str) -> str:
        """Convert CSV to formatted text."""
        try:
            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
            logger.info(f"Loaded CSV: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Error loading CSV {file_path}: {e}")
            raise

    def _load_text(self, file_path: str) -> str:
        """Load plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            logger.info(f"Loaded text: {file_path}")
            return text
        except Exception as e:
            logger.error(f"Error loading text {file_path}: {e}")
            raise

    def chunk_document(self, text: str, chunk_size: int = 1000) -> List[str]:
        """
        Split document text into chunks for processing.

        Args:
            text: Document text
            chunk_size: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        words = text.split()
        chunks = []
        current_chunk = ""

        for word in words:
            if len(current_chunk) + len(word) + 1 <= chunk_size:
                current_chunk += " " + word
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

if __name__ == "__main__":
    # Test the processor
    processor = DocumentProcessor()

    # Create a sample text file for testing
    sample_text = """
    SAMPLE MEDICAL DEVICE REQUIREMENTS DOCUMENT

    1. Requirements Analysis
    - System shall be biocompatible
    - Device must meet FDA Class II standards
    - Verification through testing required

    2. Risk Management
    - Risk assessment per ISO 14971
    - Mitigation strategies documented
    - Residual risks acceptable

    3. Design Controls
    - Design reviews conducted
    - Changes tracked and approved
    """

    with open("data/sample_requirements.txt", "w") as f:
        f.write(sample_text)

    try:
        content = processor.load_document("data/sample_requirements.txt")
        chunks = processor.chunk_document(content, 500)
        print(f"Loaded content length: {len(content)}")
        print(f"Number of chunks: {len(chunks)}")
    except Exception as e:
        print(f"Error: {e}")
