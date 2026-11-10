"""Nhận diện văn bản và trích xuất trường dữ liệu từ hóa đơn.

Chỉ chuẩn hóa văn bản để *tìm* nhãn; luôn trả về giá trị trên bản gốc
để không làm mất dấu tiếng Việt và chữ hoa/chữ thường.
"""

import io
import re
import unicodedata
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

MAX_PDF_PAGES = 30
MAX_IMAGE_PIXELS = 20_000_000


def preprocess_image(image: Image.Image) -> Image.Image:
    """Tiền xử lý ảnh; chặn ảnh giải nén quá lớn trước khi phóng to."""
    image = ImageOps.exif_transpose(image)
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("Ảnh quá lớn để xử lý OCR.")

    image = ImageOps.grayscale(image)
    image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.8)
    return image.filter(ImageFilter.MedianFilter(size=3))


def extract_text(file_path: str) -> str:
    """Đọc text layer trong PDF, OCR các trang scan và ảnh PNG/JPEG."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        contents: list[str] = []
        with fitz.open(path) as document:
            if document.page_count > MAX_PDF_PAGES:
                raise ValueError(f"PDF vượt quá {MAX_PDF_PAGES} trang.")
            for page in document:
                text = page.get_text().strip()
                if not text:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    with Image.open(io.BytesIO(pixmap.tobytes("png"))) as image:
                        text = pytesseract.image_to_string(image, lang="vie+eng")
                contents.append(text)
        return "\n".join(contents)

    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(path) as original:
            image = preprocess_image(original)
            return pytesseract.image_to_string(
                image, lang="vie+eng", config="--oem 3 --psm 6"
            )

    raise ValueError("Chỉ hỗ trợ PDF, PNG, JPG và JPEG.")


def _normalized_and_offsets(text: str) -> tuple[str, list[int]]:
    """Tạo bản tìm kiếm không dấu, ánh xạ mỗi ký tự về vị trí text gốc."""
    normalized_chars: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        for part in unicodedata.normalize("NFD", char.lower().replace("đ", "d")):
            if unicodedata.category(part) != "Mn":
                normalized_chars.append(part)
                offsets.append(index)
    return "".join(normalized_chars), offsets


def normalize_text(text: str) -> str:
    """Bỏ dấu chỉ để dò nhãn trong OCR."""
    return _normalized_and_offsets(text)[0]


def extract_fields(text: str) -> dict[str, str | None]:
    normalized, offsets = _normalized_and_offsets(text)

    def find(patterns: list[str], *, preserve_original: bool = False) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, normalized, re.IGNORECASE)
            if match is None:
                continue
            if preserve_original:
                start, end = match.span(1)
                if start == end:
                    continue
                # end là exclusive; lấy đến ký tự hiển thị tiếp theo để
                # giữ cả dấu kết hợp (Unicode NFD) ở cuối giá trị.
                original_end = offsets[end] if end < len(offsets) else len(text)
                value = text[offsets[start]:original_end]
            else:
                value = match.group(1)
            value = value.strip(" \t:：.-")
            if value:
                return value
        return None

    invoice_date = None
    date_match = re.search(
        r"ngay\s*(?:\([^)]*\)\s*)?(\d{1,2})"
        r"\s*thang\s*(?:\([^)]*\)\s*)?(\d{1,2})"
        r"\s*nam\s*(?:\([^)]*\)\s*)?(\d{4})",
        normalized, re.IGNORECASE,
    )
    if date_match:
        day, month, year = date_match.groups()
        invoice_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    if not invoice_date:
        invoice_date = find([
            r"ngay(?:\s+lap)?\s*(?:\([^)]*\)\s*)?[:.]?\s*"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        ])

    invoice_number = find([
        r"\bso\s*\(\s*no\.?\s*\)\s*[:：.]?\s*([a-z0-9/-]+)",
        r"\b(?:so|ma) hoa don\s*[:：.]?\s*([a-z0-9/-]+)",
        r"\binvoice\s*(?:no\.?|number)\s*[:：.]?\s*([a-z0-9/-]+)",
    ], preserve_original=True)

    seller_name = find([
        r"don vi ban(?: hang)?\s*(?:\(\s*seller\s*\))?\s*[:：]\s*([^\n\r]+)",
        r"ten don vi ban\s*[:：]\s*([^\n\r]+)",
        r"nguoi ban\s*[:：]\s*([^\n\r]+)",
        r"seller(?: name)?\s*[:：]\s*([^\n\r]+)",
    ], preserve_original=True)

    tax_code = find([
        r"ma so thue\s*(?:\(\s*tax code\s*\))?\s*[:：]\s*([0-9-]+)",
        r"tax code\s*[:：]\s*([0-9-]+)",
    ])

    address = find([
        r"dia chi\s*(?:\(\s*address\s*\))?\s*[:：]\s*([^\n\r]+)",
    ], preserve_original=True)

    serial = find([
        r"ky hieu\s*(?:\(\s*serial no\.?\s*\))?\s*[:：]?\s*([a-z0-9/-]+)",
    ], preserve_original=True)

    total_amount = find([
        r"tong tien thanh toan\s*(?:\(\s*vnd\s*\))?\s*[:：]?\s*([\d.,]+)",
        r"tong thanh toan\s*[:：]?\s*([\d.,]+)",
        r"tong cong\s*[:：]?\s*([\d.,]+)",
        r"tong tien\s*(?:\(\s*vnd\s*\))?\s*[:：]\s*([\d.,]+)",
        r"grand total\s*[:：]?\s*([\d.,]+)",
    ])

    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "seller_name": seller_name,
        "tax_code": tax_code,
        "address": address,
        "serial": serial,
        "total_amount": total_amount,
        "raw_text": text,
    }
