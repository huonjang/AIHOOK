"""Intent routing, scoped read-only queries and focused grounded responses."""
import re
import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Invoice
from app.ocr_service import normalize_text
from app.services.analytics_service import get_analytics, money
from app.services.numerical_validation import validate_analytics


def recognize_intent(question):
    text = normalize_text(question).lower()
    windows = re.findall(r'(\d+)\s*thang\s*(gan|xa|som|moi|cu)\s*nhat', text)
    earliest = next((int(count) for count, kind in windows if kind in ('xa', 'som', 'cu')), None)
    latest = next((int(count) for count, kind in windows if kind in ('gan', 'moi')), None)
    if earliest and latest:
        return 'comparison_windows', {'earliest_months': earliest, 'latest_months': latest}
    if any(word in text for word in ('khuyen nghi', 'de xuat', 'goi y quan ly')):
        match = re.search(r'(\d+)\s*(?:khuyen nghi|de xuat|goi y)', text)
        words = {'mot': 1, 'hai': 2, 'ba': 3, 'bon': 4, 'nam': 5, 'sau': 6, 'bay': 7, 'tam': 8, 'chin': 9, 'muoi': 10}
        word_match = re.search(r'\b(' + '|'.join(words) + r')\s+(?:khuyen nghi|de xuat|goi y)', text)
        return 'recommendation', {'count': int(match[1]) if match else words[word_match[1]] if word_match else 5}
    if any(word in text for word in ('som nhat', 'xa nhat', 'cu nhat', 'gan nhat', 'moi nhat')) and not re.search(
        r'(?:\d+\s*thang|thang\s+(?:gan|som|xa|moi|cu)\s+nhat)', text
    ):
        earliest = any(word in text for word in ('som nhat', 'xa nhat', 'cu nhat'))
        latest = any(word in text for word in ('gan nhat', 'moi nhat'))
        return 'date', {'mode': 'both' if earliest and latest else 'earliest' if earliest else 'latest'}
    if 'nha cung cap' in text or 'khach hang' in text:
        # Named invoice searches and mixed-role questions need the open query path.
        if ('nha cung cap' in text and 'khach hang' in text) or any(word in text for word in ('tim hoa don', 'chi tiet hoa don')):
            return None
        match = re.search(r'top\s*(\d+)', text)
        return ('customer' if 'khach hang' in text else 'supplier'), {'limit': int(match[1]) if match else 5}
    if any(word in text for word in ('tinh nhat quan', 'kiem chung so lieu')):
        return 'validation', {}
    if any(word in text for word in ('tong quan', 'tom tat')):
        return 'overview', {}
    if 'so sanh' in text and len(re.findall(r'thang\s*\d', text)) >= 2:
        return 'comparison', {}
    return None


def scoped_rows(db, business_id, start, end):
    query = select(Invoice).where(Invoice.business_id == business_id,
                                  Invoice.verification_status == 'confirmed')
    if start:
        query = query.where(Invoice.invoice_date >= start)
    if end:
        query = query.where(Invoice.invoice_date <= end)
    return db.scalars(query.order_by(Invoice.id)).all()


def partner_rankings(db, business_id, start, end, role='supplier', limit=5):
    data = get_analytics(db, business_id, start, end)
    key, name = ('suppliers', 'seller_name') if role == 'supplier' else ('customers', 'buyer_name')
    rows = data[key]
    total = sum((Decimal(row['total_amount']) for row in rows), Decimal('0'))
    count = sum(row['invoice_count'] for row in rows)
    by_amount = sorted(rows, key=lambda row: (-Decimal(row['total_amount']), -row['invoice_count'], row[name]))
    by_count = sorted(rows, key=lambda row: (-row['invoice_count'], -Decimal(row['total_amount']), row[name]))
    top_total = sum((Decimal(row['total_amount']) for row in by_amount[:limit]), Decimal('0'))
    return {'role': role, 'limit': limit, 'by_amount': by_amount[:limit], 'by_count': by_count[:limit],
            'total_amount': money(total), 'invoice_count': count, 'partner_count': len(rows),
            'top_share_percent': money(top_total / total * 100) if total else None,
            'unknown_count': data['flow_summary']['unknown']['invoice_count'],
            'validation': validate_analytics(data)}


def invoice_extremes(db, business_id, start, end, mode='both'):
    rows = scoped_rows(db, business_id, start, end)
    dated = sorted((row for row in rows if row.invoice_date), key=lambda row: (row.invoice_date, row.id))

    def record(row):
        partner = row.seller_name if row.flow_type == 'purchase' else row.buyer_name if row.flow_type == 'sale' else None
        return {'invoice_id': row.id, 'invoice_number': row.invoice_number,
                'invoice_date': row.invoice_date.isoformat(), 'partner': partner,
                'seller_name': row.seller_name, 'buyer_name': row.buyer_name,
                'flow_type': row.flow_type, 'total_amount': money(row.total_amount or Decimal('0')),
                'source_page': row.source_page}

    earliest = record(dated[0]) if dated else None
    # ID ascending breaks ties consistently for either endpoint.
    latest_row = min((row for row in dated if row.invoice_date == dated[-1].invoice_date), key=lambda row: row.id) if dated else None
    latest = record(latest_row) if latest_row else None
    selected = ([earliest, latest] if mode == 'both' else [earliest if mode == 'earliest' else latest])
    unique = {row['invoice_id']: row for row in selected if row}
    return {'mode': mode, 'earliest': earliest if mode != 'latest' else None,
            'latest': latest if mode != 'earliest' else None,
            'days_between': (dated[-1].invoice_date - dated[0].invoice_date).days if dated and mode == 'both' else None,
            'undated_count': len(rows) - len(dated), 'invoices': list(unique.values()),
            'tie_policy': 'Cùng ngày: chọn ID nhỏ nhất; ngày lập trống được loại khỏi xếp hạng.'}


def compare_data_windows(db, business_id, start, end, earliest_months=3, latest_months=3):
    rows = [row for row in scoped_rows(db, business_id, start, end) if row.invoice_date]
    if not rows:
        return {'error': 'Không có hóa đơn đã xác nhận có ngày lập để xác định các kỳ so sánh.'}
    first = min(row.invoice_date for row in rows)
    last = max(row.invoice_date for row in rows)

    def month_at(day, offset, last_day=False):
        year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
        return date(year, month + 1, calendar.monthrange(year, month + 1)[1] if last_day else 1)

    def period(left, right):
        left, right = max(left, start) if start else left, min(right, end) if end else right
        data = get_analytics(db, business_id, left, right)
        return {'start_date': left.isoformat(), 'end_date': right.isoformat(),
                **data['overview'], 'validation': validate_analytics(data)}

    a = period(month_at(first, 0), month_at(first, earliest_months - 1, True))
    b = period(month_at(last, 1 - latest_months), month_at(last, 0, True))
    overlap = max(0, (min(date.fromisoformat(a['end_date']), date.fromisoformat(b['end_date'])) -
                      max(date.fromisoformat(a['start_date']), date.fromisoformat(b['start_date']))).days + 1)
    return {'period_a': a, 'period_b': b, 'overlap_days': overlap,
            'amount_delta': money(Decimal(b['total_amount']) - Decimal(a['total_amount'])),
            'count_delta': b['invoice_count'] - a['invoice_count'],
            'latest_data_date': last.isoformat()}


def recommendations(db, business_id, start, end, count=5):
    rows = scoped_rows(db, business_id, start, end)
    purchase = [row for row in rows if row.flow_type == 'purchase']
    sale = [row for row in rows if row.flow_type == 'sale']
    unknown = len(rows) - len(purchase) - len(sale)
    missing = sum(not row.invoice_date or not row.invoice_number or row.total_amount is None for row in rows)
    missing_tax = sum(not row.seller_tax_code for row in purchase)
    ranks = partner_rankings(db, business_id, start, end)
    head = ranks['by_amount'][0] if ranks['by_amount'] else None
    frequent = ranks['by_count'][0] if ranks['by_count'] else None
    value_reason = (f'{head["seller_name"]} đứng đầu với {amount(head["total_amount"])}'
                    if head else 'chưa có hóa đơn mua vào đã phân loại, cần hoàn tất phân loại trước khi xếp hạng')
    frequency_reason = (f'{frequent["seller_name"]} có {frequent["invoice_count"]} hóa đơn, trung bình {amount(Decimal(frequent["total_amount"]) / frequent["invoice_count"])} mỗi hóa đơn'
                        if frequent else 'chưa có dữ liệu mua vào để xác định tần suất')
    items = [
        f'Chuẩn hóa tên và mã số thuế nhà cung cấp: có {len(purchase)} hóa đơn mua vào, trong đó {missing_tax} hóa đơn thiếu mã số thuế người bán; dùng mã số thuế để tránh tách sai nhóm.',
        f'Theo dõi nhóm mua vào theo giá trị: {value_reason}; đối chiếu file nguồn trước khi lập báo cáo.',
        f'Đối chiếu đồng thời số lượng và giá trị theo nhà cung cấp: {frequency_reason}; xem cả hai tiêu chí trước khi kết luận nhóm có tần suất cao nhưng giá trị nhỏ.',
        f'Rà soát trường dữ liệu và OCR: {missing}/{len(rows)} hóa đơn đã xác nhận thiếu ngày, mã hóa đơn hoặc tổng tiền; trạng thái xác nhận không thay thế đối chiếu bản gốc.',
        f'Đối chiếu mua vào, bán ra và thanh toán riêng: có {len(purchase)} hóa đơn mua vào, {len(sale)} bán ra và {unknown} chưa phân loại; hệ thống chưa có dữ liệu thanh toán để xác định đã thu hoặc đã trả.',
        f'Kiểm tra ngày lập trước khi tổng hợp theo kỳ: {sum(row.invoice_date is None for row in rows)} hóa đơn thiếu ngày nên không thể phân bổ theo tháng.',
        f'Rà soát mã hóa đơn trùng theo người bán: có {len(rows)} bản ghi trong phạm vi; cần đối chiếu thêm mã số thuế và file gốc trước khi xác định bản ghi trùng.',
        f'Chuẩn hóa thông tin khách hàng trên hóa đơn bán ra: có {len(sale)} hóa đơn bán ra, {sum(not row.buyer_name for row in sale)} hóa đơn thiếu tên người mua.',
        f'Hoàn tất phân loại chứng từ: {unknown} hóa đơn chưa phân loại đang được loại khỏi xếp hạng nhà cung cấp và khách hàng.',
        f'Giữ liên kết với file nguồn khi xuất báo cáo: {len(rows)} bản ghi đã xác nhận được dùng trong phạm vi này; cần giữ ID hóa đơn để truy vết từng dòng.',
    ]
    if not 1 <= count <= len(items):
        return {'error': 'Hỗ trợ từ 1 đến 10 khuyến nghị cụ thể; hãy chọn số lượng trong khoảng này.'}
    return {'recommendations': items[:count], 'invoice_count': len(rows)}


def amount(value):
    return f'{Decimal(str(value)):,.0f}'.replace(',', '.') + ' đ'


def focused_response(name, result):
    """Render one relevant narrative and its evidence from query results only."""
    if 'error' in result:
        return result['error'], []
    if name == 'compare_invoice_data_windows':
        a, b = result['period_a'], result['period_b']
        answer = (f'Các kỳ được xác định từ tháng đầu và tháng cuối có hóa đơn trong phạm vi đã chọn. '
                  f'Chênh lệch kỳ gần nhất trừ kỳ sớm nhất: {amount(result["amount_delta"])}, '
                  f'{result["count_delta"]} hóa đơn. Dữ liệu có ngày lập đến {result["latest_data_date"]}.')
        if result['overlap_days']:
            answer += f' Hai kỳ chồng lấp {result["overlap_days"]} ngày; đây không phải hai mẫu độc lập.'
        answer += ' Kết quả phản ánh hóa đơn đã lưu; không chứng minh dữ liệu đủ cả kỳ hoặc hiệu quả kinh doanh.'
        return answer, [{'title': 'So sánh kỳ theo dữ liệu hóa đơn',
                         'columns': ['Kỳ', 'Từ ngày', 'Đến ngày', 'Số hóa đơn', 'Tổng giá trị'],
                         'rows': [[label, item['start_date'], item['end_date'], item['invoice_count'], amount(item['total_amount'])]
                                  for label, item in [('Sớm nhất', a), ('Gần nhất', b)]]}]
    if name in ('get_supplier_rankings', 'get_customer_rankings'):
        label = 'nhà cung cấp' if result['role'] == 'supplier' else 'khách hàng'
        direction = 'mua vào' if result['role'] == 'supplier' else 'bán ra'
        field = 'seller_name' if result['role'] == 'supplier' else 'buyer_name'
        evidence = []
        for key, metric in [('by_amount', 'tổng giá trị'), ('by_count', 'số lượng hóa đơn')]:
            evidence.append({'title': f'Top {result["limit"]} {label} theo {metric} {direction}',
                             'columns': [label.capitalize(), 'Số hóa đơn', 'Tổng giá trị'],
                             'rows': [[row[field], row['invoice_count'], amount(row['total_amount'])] for row in result[key]]})
        if not result['by_amount']:
            answer = f'Chưa có hóa đơn {direction} đã xác nhận trong phạm vi này để xếp hạng {label}.'
        else:
            first, frequent = result['by_amount'][0], result['by_count'][0]
            same = first[field] == frequent[field] and first.get('seller_tax_code', first.get('buyer_tax_code')) == frequent.get('seller_tax_code', frequent.get('buyer_tax_code'))
            answer = f'{first[field]} đứng đầu về giá trị ({amount(first["total_amount"])}). '
            answer += ('Cùng đơn vị này đứng đầu về số lượng' if same else f'{frequent[field]} đứng đầu về số lượng') + f' ({frequent["invoice_count"]} hóa đơn).'
            if result['top_share_percent'] is not None:
                answer += f' Nhóm {len(result["by_amount"])} đơn vị đầu bảng chiếm {result["top_share_percent"]}% tổng giá trị {direction} trong phạm vi này.'
        if result['unknown_count']:
            answer += f' Có {result["unknown_count"]} hóa đơn chưa phân loại được loại khỏi xếp hạng.'
        return answer, evidence
    if name == 'get_invoice_date_extremes':
        selected = [(label, result[key]) for label, key in [('Sớm nhất', 'earliest'), ('Gần nhất', 'latest')] if result[key]]
        if not selected:
            return f'Không có hóa đơn đã xác nhận có ngày lập trong phạm vi này. Có {result["undated_count"]} hóa đơn thiếu ngày.', []
        fields = [('Ngày lập', 'invoice_date'), ('Mã hóa đơn', 'invoice_number'), ('Đối tác', 'partner'), ('Tổng giá trị', 'total_amount')]
        evidence = [{'title': 'Ngày lập hóa đơn', 'columns': ['Thông tin'] + [label for label, _ in selected],
                     'rows': [[label] + [amount(row[key]) if key == 'total_amount' else row[key] or 'Chưa xác định' for _, row in selected] for label, key in fields]}]
        answer = ' '.join(f'Hóa đơn {label.lower()}: {row["invoice_number"] or "ID " + str(row["invoice_id"])} ngày {row["invoice_date"]}, tổng giá trị {amount(row["total_amount"])}.' for label, row in selected)
        if result['days_between'] is not None:
            answer += f' Khoảng cách ngày lập: {result["days_between"]} ngày.'
        answer += f' {result["undated_count"]} hóa đơn thiếu ngày không được xét. Cùng ngày chọn ID nhỏ nhất.'
        return answer, evidence
    if name == 'get_invoice_recommendations':
        return '\n'.join(f'{index}. {item}' for index, item in enumerate(result['recommendations'], 1)), []
    return None
