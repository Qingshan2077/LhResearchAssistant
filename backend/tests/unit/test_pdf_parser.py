"""Boundary tests for PDF parsing."""

import pytest

from app.services.pdf_parser import PDFParser


def test_extract_text_fast_missing_file_raises():
    with pytest.raises(Exception):
        PDFParser.extract_text_fast("/nonexistent/path/test.pdf")


def test_get_page_count_missing_file_raises():
    with pytest.raises(Exception):
        PDFParser.get_page_count("/nonexistent/path/test.pdf")
