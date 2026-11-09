def extract_text(path, extension):
    if extension == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    if extension == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("PDF support is not installed. Run: pip install pypdf")
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError("Unsupported file type.")
