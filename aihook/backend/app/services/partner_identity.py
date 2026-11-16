"""Identity keys, never a shared identity for an unidentified counterparty."""
from app.ocr_service import normalize_text


def clean_identity(value):
    text = ' '.join((value or '').split())
    if normalize_text(text).lower() in {'', '-', '—', 'n/a', 'na', 'none', 'null', 'unknown',
                                         'chua ro', 'chua ro doi tac', 'khong ro', 'chua xac dinh'}:
        return None
    return text


def partner_identity(invoice):
    if invoice.flow_type not in ('purchase', 'sale'):
        return None
    purchase = invoice.flow_type == 'purchase'
    name = clean_identity(invoice.seller_name if purchase else invoice.buyer_name)
    tax = clean_identity(invoice.seller_tax_code if purchase else invoice.buyer_tax_code)
    if not name and not tax:
        return None
    return (('tax', tax.casefold()) if tax else ('name', name.casefold()), name or f'MST {tax}', tax)
