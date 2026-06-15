import fitz


def extract_text_from_pdf(pdf_path: str) -> str:
    document = fitz.open(pdf_path)
    try:
        page_texts = []
        for page in document:
            text = page.get_text("text")
            if text:
                page_texts.append(text.strip())
        return "\n\n".join(page_texts)
    finally:
        document.close()
