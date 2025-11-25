"""Tests for document processing functionality."""

import pytest
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.document_processor import DocumentProcessor

class TestDocumentProcessor:
    """Test cases for DocumentProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = DocumentProcessor()
        self.test_data_dir = Path("tests/data")
        self.test_data_dir.mkdir(exist_ok=True)

    def test_load_text_file(self):
        """Test loading plain text files."""
        content = "This is a test document.\nLine 2 of content."
        file_path = self.test_data_dir / "test.txt"

        try:
            # Write test file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Load and verify
            loaded_content = self.processor.load_document(str(file_path))
            assert loaded_content == content

        finally:
            # Cleanup
            if file_path.exists():
                file_path.unlink()

    def test_load_csv_file(self):
        """Test loading CSV files."""
        csv_content = "name,value\nitem1,123\nitem2,456"
        file_path = self.test_data_dir / "test.csv"

        try:
            # Write test file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(csv_content)

            # Load and verify
            loaded_content = self.processor.load_document(str(file_path))
            assert "item1" in loaded_content
            assert "123" in loaded_content

        finally:
            # Cleanup
            if file_path.exists():
                file_path.unlink()

    def test_unsupported_file_type(self):
        """Test handling of unsupported file types."""
        file_path = "nonexistent.xyz"

        with pytest.raises(ValueError, match="Unsupported file format"):
            self.processor.load_document(file_path)

    def test_file_not_found(self):
        """Test handling of missing files."""
        with pytest.raises(FileNotFoundError):
            self.processor.load_document("nonexistent.txt")

    def test_chunk_document(self):
        """Test document chunking functionality."""
        long_text = "This is a test sentence. " * 100  # Long sentence
        chunks = self.processor.chunk_document(long_text, chunk_size=50)

        assert len(chunks) > 1
        assert all(len(chunk) <= 50 for chunk in chunks)

        # Test small text (no chunking needed)
        small_text = "Short text"
        chunks = self.processor.chunk_document(small_text, chunk_size=50)
        assert len(chunks) == 1
        assert chunks[0] == small_text

    def test_processor_initialization(self):
        """Test processor initialization."""
        processor = DocumentProcessor()
        assert processor is not None
        assert hasattr(processor, 'load_document')
        assert hasattr(processor, 'chunk_document')

    def test_file_too_large(self, tmp_path):
        """Reject files larger than 10MB."""
        big_file = tmp_path / "big.txt"
        big_file.write_bytes(b"x" * (10 * 1024 * 1024 + 1))  # just over 10MB

        with pytest.raises(ValueError, match="File too large"):
            self.processor.load_document(str(big_file))

    def test_load_doc_with_textract_success(self, monkeypatch, tmp_path):
        """Load legacy .doc via textract when available."""
        doc_path = tmp_path / "legacy.doc"
        doc_path.write_bytes(b"\x00\x01")  # dummy content

        class FakeTextract:
            @staticmethod
            def process(path):
                assert str(path) == str(doc_path)
                return b"hello world"

        monkeypatch.setitem(sys.modules, "textract", FakeTextract)

        content = self.processor.load_document(str(doc_path))
        assert content == "hello world"

    def test_load_doc_with_textract_failure(self, monkeypatch, tmp_path):
        """Surface helpful error when textract fails."""
        doc_path = tmp_path / "legacy.doc"
        doc_path.write_bytes(b"\x00\x01")

        class FakeTextract:
            @staticmethod
            def process(path):
                raise RuntimeError("boom")

        monkeypatch.setitem(sys.modules, "textract", FakeTextract)

        with pytest.raises(ValueError, match="Failed to process .doc file"):
            self.processor.load_document(str(doc_path))
