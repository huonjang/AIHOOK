from app.ocr_service import extract_fields
from app.main import validate_ocr_fields

SAMPLE = '''HÓA ĐƠN BÁN HÀNG
Mã hóa đơn: HD202600051
Ngày lập: 10/11/2026
Đơn vị bán: Công ty TNHH Dịch vụ Sạc Xanh Demo
Mã số thuế: 0999999999
Cộng tiền hàng: 191.000
Thuế GTGT (10%): 19.100
Tổng tiền: 210.100
'''


def test_alternative_labels():
    fields = extract_fields(SAMPLE)
    assert fields['invoice_number'] == 'HD202600051'
    assert fields['invoice_date'] == '10/11/2026'
    assert fields['seller_name'] == 'Công ty TNHH Dịch vụ Sạc Xanh Demo'
    assert fields['tax_code'] == '0999999999'
    assert fields['total_amount'] == '210.100'
    assert validate_ocr_fields(fields, SAMPLE)['eligible']


def test_currency_label_and_next_line_amount():
    text = SAMPLE.replace('Tổng tiền: 210.100', 'Tổng tiền thanh toán (VND):\n210.100')
    assert extract_fields(text)['total_amount'] == '210.100'


def test_subtotal_is_not_total():
    assert extract_fields(SAMPLE.replace('Tổng tiền: 210.100', ''))['total_amount'] is None
