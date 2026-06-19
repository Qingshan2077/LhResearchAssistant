"""PDF 解析 — 双引擎：PyMuPDF（快速）+ marker-pdf（高精度）"""

import fitz  # PyMuPDF


class PDFParser:
    """PDF 双引擎解析器"""

    @staticmethod
    def extract_text_fast(pdf_path: str) -> str:
        """PyMuPDF 快速提取文本"""
        doc = fitz.open(pdf_path)
        texts = []
        for page in doc:
            texts.append(page.get_text("text"))
        doc.close()
        return "\n\n".join(texts)

    @staticmethod
    def extract_text_precise(pdf_path: str) -> str:
        """marker-pdf 高精度提取（含公式、表格）"""
        try:
            from marker.convert import convert_single_pdf
            from marker.models import load_all_models
            models = load_all_models()
            full_text, _, _ = convert_single_pdf(pdf_path, models)
            return full_text
        except ImportError:
            # marker-pdf 未安装时回退到 PyMuPDF
            return PDFParser.extract_text_fast(pdf_path)

    @staticmethod
    def extract_metadata(pdf_path: str) -> dict:
        """提取 PDF 元数据"""
        doc = fitz.open(pdf_path)
        meta = doc.metadata
        doc.close()
        return {
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
        }

    @staticmethod
    def extract_images(pdf_path: str) -> list[tuple[int, bytes]]:
        """提取所有页面中的图片。返回 [(page_num, png_bytes), ...]"""
        doc = fitz.open(pdf_path)
        images = []
        for page_num, page in enumerate(doc):
            for img in page.get_images():
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                # 转换为 PNG
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                images.append((page_num, pix.tobytes("png")))
                pix = None
        doc.close()
        return images

    @staticmethod
    def extract_text_by_page(pdf_path: str) -> list[dict]:
        """按页提取，每页返回 {page_num, text, images_count}"""
        doc = fitz.open(pdf_path)
        pages = []
        for page_num, page in enumerate(doc):
            pages.append({
                "page_num": page_num + 1,
                "text": page.get_text("text"),
                "images_count": len(page.get_images()),
            })
        doc.close()
        return pages

    @staticmethod
    def get_page_count(pdf_path: str) -> int:
        """获取 PDF 页数"""
        doc = fitz.open(pdf_path)
        count = doc.page_count
        doc.close()
        return count

    @staticmethod
    def extract_sections(pdf_path: str) -> list[dict]:
        """基于文本启发式提取段落和节标题"""
        text = PDFParser.extract_text_fast(pdf_path)
        sections = []
        current_section = {"title": "header", "content": [], "page": 1}

        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # 简单启发式：短行 + 大写/数字开头 → 可能是标题
            if len(line) < 100 and (
                line.isupper()
                or (line[0].isupper() and line[-1] not in ".!?")
                or any(line.startswith(p) for p in ["1.", "2.", "3.", "I.", "II."])
            ):
                if current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": line, "content": [], "page": len(sections) + 1}
            else:
                current_section["content"].append(line)

        if current_section["content"]:
            sections.append(current_section)

        return sections
