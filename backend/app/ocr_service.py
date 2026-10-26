
import io
import re
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageOps


from PIL import Image, ImageOps, ImageFilter, ImageEnhance


def preprocess_image(image: Image.Image) -> Image.Image:
    """Tăng khả năng nhận dạng chữ trên hóa đơn."""
    image = ImageOps.exif_transpose(image)
    image = ImageOps.grayscale(image)

    # Phóng to ảnh để cải thiện khả năng đọc chữ nhỏ.
    image = image.resize(
        (image.width * 2, image.height * 2),
        Image.Resampling.LANCZOS,
    )

    # Tăng tương phản và giảm nhiễu nhẹ.
    image = ImageEnhance.Contrast(image).enhance(1.8)
    image = image.filter(ImageFilter.MedianFilter(size=3))

    return image



def extract_text(file_path: str) -> str:
    """Đọc văn bản từ PDF, PNG, JPG hoặc JPEG."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        with fitz.open(path) as document:
            text = "\n".join(page.get_text() for page in document)

        if text.strip():
            return text

        # PDF scan: OCR từng trang.
        pages = []
        with fitz.open(path) as document:
            for page in document:
                pixmap = page.get_pixmap(
                    matrix=fitz.Matrix(2, 2),
                    alpha=False,
                )
                image = Image.open(
                    io.BytesIO(pixmap.tobytes("png"))
                )
                pages.append(
                    pytesseract.image_to_string(
                        image,
                        lang="vie+eng",
                    )
                )
        return "\n".join(pages)

    
    if suffix in {".png", ".jpg", ".jpeg"}:
        with Image.open(path) as image:
            image = preprocess_image(image)

            return pytesseract.image_to_string(
                image,
                lang="vie+eng",
                config="--oem 3 --psm 6",
            )


    raise ValueError("Chỉ hỗ trợ PDF, PNG, JPG và JPEG.")




import re
import unicodedata


def normalize_text(text: str) -> str:
    """Chuyển về chữ thường và bỏ dấu để dò nhãn ổn định hơn."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(
        char for char in text
        if unicodedata.category(char) != "Mn"
    )
    return text.replace("đ", "d")


def extract_fields(text: str) -> dict:
    # Dò trên bản không dấu, nhưng giữ nguyên text gốc để trả về.
    normalized = normalize_text(text)

    def find(patterns, source=normalized):
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                value = match.group(1).strip(" \t:：.-")
                if value:
                    return value
        return None

    # Ngày: Ngay (date) 14 thang (month) 11 nam (year) 2021
    invoice_date = None

   
    date_match = re.search(
        r"ngay\s*(?:\([^)]*\)\s*)?(\d{1,2})"
        r"\s*thang\s*(?:\([^)]*\)\s*)?(\d{1,2})"
        r"\s*nam\s*(?:\([^)]*\)\s*)?(\d{4})",
        normalized,
        re.IGNORECASE,
    )

    invoice_date = None

    if date_match:
        day, month, year = date_match.groups()
        invoice_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"

    if not invoice_date:
        invoice_date = find([
            r"ngay\s*(?:\([^)]*\)\s*)?[:.]?\s*"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        ])

    # Số hóa đơn: Số (No.): 7
    invoice_number = find([
        r"\bso\s*\(\s*no\.?\s*\)\s*[:：.]?\s*"
        r"([a-z0-9/-]+)",
        r"\bso hoa don\s*[:：.]?\s*([a-z0-9/-]+)",
        r"\binvoice\s*(?:no\.?|number)\s*[:：.]?\s*"
        r"([a-z0-9/-]+)",
    ])

    # Đơn vị bán hàng: ... (Seller): TÊN ĐƠN VỊ
    seller_name = find([
        r"don vi ban hang\s*\(\s*seller\s*\)\s*[:：]\s*([^\n]+)",
        r"don vi ban hang\s*[:：]\s*([^\n]+)",
        r"ten don vi ban\s*[:：]\s*([^\n]+)",
        r"nguoi ban\s*[:：]\s*([^\n]+)",
    ])

    tax_code = find([
        r"ma so thue\s*\(\s*tax code\s*\)\s*[:：]\s*"
        r"([0-9-]+)",
        r"ma so thue\s*[:：]\s*([0-9-]+)",
    ])

    address = find([
        r"dia chi\s*\(\s*address\s*\)\s*[:：]\s*([^\n]+)",
        r"dia chi\s*[:：]\s*([^\n]+)",
    ])

    serial = find([
        r"ky hieu\s*\(\s*serial no\.?\s*\)\s*[:：]?\s*"
        r"([a-z0-9/-]+)",
    ])

    # Chỉ lấy tổng hóa đơn, không lấy thành tiền của một dòng hàng.
    total_amount = find([
        r"tong tien thanh toan\s*[:：]?\s*([\d.,]+)",
        r"tong thanh toan\s*[:：]?\s*([\d.,]+)",
        r"tong cong\s*[:：]?\s*([\d.,]+)",
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


