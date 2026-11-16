"""Purchase/sale direction is a business-meaning annotation, not OCR/legal validation.

All historical invoices remain unknown until the account owner confirms them.
A matching tax code is a suggestion only. It must never auto-create revenue/cost.
"""
from __future__ import annotations

FLOW_TYPES = {'purchase', 'sale', 'unknown'}


def suggest_flow(*, business_tax_code: str | None, seller_tax_code: str | None,
                 buyer_tax_code: str | None = None) -> dict[str, str | None]:
    registered = (business_tax_code or '').strip().replace('-', '')
    seller = (seller_tax_code or '').strip().replace('-', '')
    buyer = (buyer_tax_code or '').strip().replace('-', '')
    if not registered:
        return {'suggestion': None, 'reason': 'Mã số thuế doanh nghiệp chưa được cung cấp; cần xác nhận thủ công.'}
    if registered == seller and registered == buyer:
        return {'suggestion': None, 'reason': 'MST bên bán và mua cùng trùng; cần kiểm tra hóa đơn gốc.'}
    if seller and registered == seller:
        return {'suggestion': 'sale', 'reason': 'MST bên bán trùng với doanh nghiệp đăng ký. Vui lòng xác nhận.'}
    if buyer and registered == buyer:
        return {'suggestion': 'purchase', 'reason': 'MST bên mua trùng với doanh nghiệp đăng ký. Vui lòng xác nhận.'}
    return {'suggestion': None, 'reason': 'Không đủ căn cứ xác định hướng hóa đơn; cần xác nhận thủ công.'}
