"""Engine 2.0: deterministic intent, grounded tools, controlled context and assurance."""
import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from app.ocr_service import normalize_text
from app.services.analytics_service import get_analytics, money
from app.services.invoice_intelligence import scoped_rows, partner_rankings, invoice_extremes, recommendations, focused_response, amount, recognize_intent, compare_data_windows
from app.services.numerical_validation import validate_analytics
from app.services.partner_identity import clean_identity, partner_identity


def local_today():
    return datetime.now(timezone(timedelta(hours=7))).date()


def month_bounds(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def resolve_periods(question, today=None):
    """Return explicit calendar periods; never ask a model to invent dates."""
    text = normalize_text(question).lower()
    today = today or local_today()
    if 'toan bo thoi gian' in text or 'toan thoi gian' in text:
        return []
    months = re.findall(r'thang\s*(\d{1,2})(?:\s*[/\-]\s*(\d{4}))?', text)
    if months:
        year = next((int(year) for _, year in months if year), today.year)
        bounds = [month_bounds(int(y) if y else year, int(m)) for m, y in months]
        if len(bounds) == 2 and 'tu thang' in text and 'den thang' in text:
            if bounds[0][0] > bounds[1][1]:
                raise ValueError('Khoảng tháng không hợp lệ.')
            return [(bounds[0][0], bounds[1][1])]
        return bounds
    if any(word in text for word in ('thang nay', 'thang hien tai')):
        return [month_bounds(today.year, today.month)]
    if 'thang truoc' in text:
        day = date(today.year, today.month, 1) - timedelta(days=1)
        return [month_bounds(day.year, day.month)]
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
    if dates:
        parsed = [date.fromisoformat(day) for day in dates]
        if len(parsed) > 2 or parsed[0] > parsed[-1]:
            raise ValueError('Khoảng ngày không hợp lệ.')
        return [(parsed[0], parsed[-1])]
    quarter = re.search(r'quy\s*([1-4])(?:\s*(?:/|nam)\s*(\d{4}))?', text)
    if quarter:
        year = int(quarter[2]) if quarter[2] else today.year
        first_month = (int(quarter[1]) - 1) * 3 + 1
        return [(date(year, first_month, 1), month_bounds(year, first_month + 2)[1])]
    year_match = re.search(r'nam\s*(\d{4}|nay|truoc)', text)
    if year_match:
        value = year_match[1]
        year = today.year if value == 'nay' else today.year - 1 if value == 'truoc' else int(value)
        return [(date(year, 1, 1), date(year, 12, 31))]
    return []


def intersect(period, start, end):
    left, right = period if period else (None, None)
    return max(x for x in (left, start) if x) if left or start else None, min(x for x in (right, end) if x) if right or end else None


def intent_for(question, context=None):
    text = normalize_text(question).lower()
    context = context or {}
    if 'doi tac nao tot nhat' in text or ('tot nhat' in text and not any(x in text for x in ('gia ban', 'nha cung cap'))):
        return 'clarification', {}
    if any(x in text for x in ('loi nhuan', 'co lai', 'gia ban tot nhat')):
        return 'limits', {}
    if 'tai sao' in text and any(x in text for x in ('quan trong', 'gia tri lon')):
        return 'advice', {'role': 'supplier'}
    if any(x in text for x in ('bao cao dieu hanh', 'bao cao cho chu doanh nghiep')):
        return 'report', {}
    if 'ocr' in text and any(x in text for x in ('quy trinh', 'xac nhan', 'giam sai sot')):
        return 'ocr', {}
    if any(x in text for x in ('trung lap', 'nghi trung', 'trung ma', 'trung gia tri', 'trung doi tac')):
        return 'duplicates', {}
    if any(x in text for x in ('bat thuong', 'khac biet dang ke', 'giao dich thong thuong')):
        return 'anomalies', {}
    if any(x in text for x in ('chat luong du lieu', 'truong bi thieu', 'du lieu thieu')):
        return 'quality', {}
    if any(x in text for x in ('phu thuoc', 'tap trung giao dich')):
        return 'partners', {'both': True}
    if 'nha cung cap' in text and 'khach hang' in text:
        return 'partners', {'both': True}
    if text.startswith(('con neu', 'vay ', 'neu xet')):
        if context.get('topic') in ('supplier', 'customer', 'partners', 'advice'):
            role = context.get('role', 'supplier')
            return ('advice' if 'dang quan tam' in text else role), {'role': role, 'criterion': 'count' if 'so luong' in text else context.get('criterion', 'amount'), 'limit': context.get('limit', 5)}
        return 'clarification', {}
    if 'trung binh' in text and any(x in text for x in ('mua vao', 'ban ra')) and 'so sanh' not in text:
        return 'averages', {}
    if re.search(r'(?:tim|top)\s*\d+\s*hoa don', text) or 'hoa don co tong gia tri lon nhat' in text:
        match = re.search(r'(?:tim|top)\s*(\d+)', text)
        return 'top_invoices', {'limit': int(match[1]) if match else 5}
    existing = recognize_intent(question)
    if existing and existing[0] not in ('comparison', 'overview'):
        return existing
    if 'so sanh' in text and len(re.findall(r'thang\s*\d', text)) >= 2:
        return 'comparison', {}
    if any(x in text for x in ('theo thang', 'tung thang', 'thang nay', 'thang hien tai', 'thang nao', 'thang truoc')) or re.search(r'thang\s*\d', text):
        return 'monthly', {}
    if existing:
        return existing
    return None


def invoice_record(row):
    identity = partner_identity(row)
    return {'invoice_id': row.id, 'invoice_number': row.invoice_number, 'invoice_date': row.invoice_date.isoformat() if row.invoice_date else None,
            'partner': identity[1] if identity else None, 'flow_type': row.flow_type,
            'seller_name': row.seller_name, 'buyer_name': row.buyer_name,
            'total_amount': money(row.total_amount or Decimal('0')), 'source_page': row.source_page}


def data_quality(rows):
    fields = ('invoice_date', 'invoice_number', 'seller_tax_code', 'buyer_tax_code', 'seller_name', 'buyer_name', 'total_amount')
    counts = {field: sum((getattr(row, field) is None if field in ('invoice_date', 'total_amount') else clean_identity(getattr(row, field)) is None) for row in rows) for field in fields}
    return {'invoice_count': len(rows), 'missing_fields': counts,
            'field_state': {field: 'measured' for field in fields},
            'ocr_correctness': 'not_evaluated', 'missing_any_core': sum(not row.invoice_date or not clean_identity(row.invoice_number) or row.total_amount is None for row in rows)}


def duplicate_candidates(rows):
    strict, loose, numbers = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        identity = partner_identity(row)
        if not identity:
            continue
        key = (row.flow_type, identity[0])
        if clean_identity(row.invoice_number):
            numbers[(*key, row.invoice_number.strip().casefold())].append(row)
            if row.invoice_date and row.total_amount is not None:
                strict[(*key, row.invoice_number.strip().casefold(), row.invoice_date, row.total_amount)].append(row)
        if row.invoice_date and row.total_amount is not None:
            loose[(*key, row.invoice_date, row.total_amount)].append(row)
    groups, seen = [], set()
    for mapping, reason in ((strict, 'Trùng hướng, đối tác, mã, ngày và giá trị'),
                            (numbers, 'Trùng hướng, đối tác và mã hóa đơn'),
                            (loose, 'Trùng hướng, đối tác, ngày và giá trị')):
        for matches in mapping.values():
            ids = tuple(sorted(row.id for row in matches))
            if len(matches) > 1 and ids not in seen:
                seen.add(ids)
                groups.append({'classification': 'suspected', 'reason': reason, 'invoices': [invoice_record(row) for row in matches]})
    return {'groups': groups, 'confirmed_duplicates': [], 'evaluated_count': len(rows),
            'unidentified_count': sum(partner_identity(row) is None for row in rows),
            'limitation': 'Trùng trường dữ liệu chỉ là nghi trùng; chưa đối chiếu nội dung/file gốc nên không xác nhận trùng thực sự.'}


def detect_anomalies(rows):
    groups = defaultdict(list)
    excluded = 0
    for row in rows:
        identity = partner_identity(row)
        if identity and row.total_amount is not None:
            groups[(row.flow_type, identity[0])].append(row)
        else:
            excluded += 1
    candidates, baselines = [], []
    insufficient = 0
    for matches in groups.values():
        if len(matches) < 5:
            insufficient += len(matches)
            continue
        values = [row.total_amount for row in matches]
        center = median(values)
        mad = median([abs(value - center) for value in values])
        mean = sum(values, Decimal('0')) / len(values)
        # Conservative rule when MAD is zero: require a 3x typical-value deviation.
        threshold = Decimal('3') * mad if mad else max(abs(center) * 3, Decimal('1'))
        baseline = {'partner': partner_identity(matches[0])[1], 'flow_type': matches[0].flow_type,
                    'sample_count': len(values), 'mean': money(mean), 'median': money(center),
                    'mad': money(mad), 'threshold': money(threshold)}
        baselines.append(baseline)
        for row in matches:
            if abs(row.total_amount - center) > threshold:
                candidates.append({'invoice': invoice_record(row), 'baseline': baseline,
                                   'deviation': money(abs(row.total_amount - center))})
    return {'candidates': candidates, 'baselines': baselines, 'evaluated_groups': len(baselines),
            'insufficient_count': insufficient, 'excluded_count': excluded,
            'method': 'Theo cùng đối tác và hướng; tối thiểu 5 mẫu; độ lệch tuyệt đối so với trung vị > 3 MAD. MAD=0: ngưỡng max(3×|trung vị|,1đ).'}


def execute_engine_tool(name, arguments, db, business_id, start, end):
    """Called by both deterministic routing and the allowlisted model dispatcher."""
    rows = scoped_rows(db, business_id, start, end)
    if name == 'get_invoice_data_quality':
        return data_quality(rows)
    if name == 'detect_invoice_duplicates':
        return duplicate_candidates(rows)
    if name == 'detect_invoice_anomalies':
        return detect_anomalies(rows)
    if name in ('get_flow_monthly_summary', 'get_flow_averages'):
        data = get_analytics(db, business_id, start, end)
        return {'analytics': data, 'validation': validate_analytics(data)}
    if name == 'get_top_invoices':
        ordered = sorted((row for row in rows if row.total_amount is not None), key=lambda row: (-row.total_amount, row.id))
        return {'invoices': [invoice_record(row) for row in ordered[:arguments.get('limit', 5)]], 'matched_count': len(ordered)}
    return {'error': 'Công cụ không được hỗ trợ.'}


def table(title, columns, rows):
    return {'title': title, 'columns': columns, 'rows': rows}


def flow_evidence(data, title='Theo hướng hóa đơn'):
    return table(title, ['Hướng', 'Số hóa đơn', 'Tổng giá trị', 'Trung bình'], [
        [label, item['invoice_count'], amount(item['total_amount']), amount(Decimal(item['total_amount']) / item['invoice_count']) if item['invoice_count'] else 'Không có dữ liệu']
        for key, label in [('purchase', 'Mua vào'), ('sale', 'Bán ra'), ('unknown', 'Chưa phân loại')]
        for item in [data['flow_summary'][key]]])


def monthly_evidence(data):
    flow = {row['month']: row for row in data['flow_monthly']}
    return table('Hóa đơn theo tháng và hướng', ['Tháng', 'Số hóa đơn', 'Số mua vào', 'Mua vào', 'Số bán ra', 'Bán ra', 'Chưa phân loại', 'Tổng'],
                 [[row['month'], row['invoice_count'], flow[row['month']]['purchase_count'], amount(flow[row['month']]['purchase_amount']), flow[row['month']]['sale_count'], amount(flow[row['month']]['sale_amount']),
                   amount(flow[row['month']]['unknown_amount']), amount(row['total_amount'])] for row in data['monthly']])


def process_question(question, db, business_id, start, end, context=None):
    """No model prose is accepted as database evidence."""
    if context and (context.get('scope_start') != (start.isoformat() if start else None) or context.get('scope_end') != (end.isoformat() if end else None)):
        context = None
    selected = intent_for(question, context)
    if not selected:
        return None
    intent, args = selected
    text = normalize_text(question).lower()
    try:
        periods = resolve_periods(question)
    except (ValueError, OverflowError):
        return response('clarification', 'Khoảng ngày chưa hợp lệ. Bạn cho biết tháng/năm hoặc khoảng ngày cần truy vấn?', [], [], None, False, {}, start, end)
    if not periods and intent != 'comparison_windows' and re.search(
        r'\b(?:quy\s*(?:\d|nay|truoc)|nam\s*(?:\d|nay|truoc)|\d+\s*(?:ngay|tuan|thang)|tuan nay|tuan truoc|hom nay|hom qua)\b', text
    ):
        return response('clarification', 'Mình chưa xác định được chính xác khoảng thời gian này. Bạn cho biết ngày bắt đầu và kết thúc (YYYY-MM-DD)?', [], [], None, False, {}, start, end)
    if not periods and context and text.startswith(('con neu', 'vay ', 'neu xet')):
        if context.get('query_start') and context.get('query_end'):
            periods = [(date.fromisoformat(context['query_start']), date.fromisoformat(context['query_end']))]
    query_start, query_end = intersect(periods[0] if periods else None, start, end)
    data = get_analytics(db, business_id, query_start, query_end)
    rows = scoped_rows(db, business_id, query_start, query_end)
    numerical = validate_analytics(data)
    tools, evidence, sources = [], [], []
    sufficient = bool(rows)
    new_context = {'topic': intent, 'role': args.get('role', intent if intent in ('supplier', 'customer') else 'supplier'),
                   'criterion': args.get('criterion', 'count' if 'so luong' in text and 'gia tri' not in text else 'amount'),
                   'limit': args.get('limit', 5), 'query_start': query_start.isoformat() if query_start else None,
                   'query_end': query_end.isoformat() if query_end else None}
    if intent == 'clarification':
        return response(intent, 'Bạn muốn đánh giá nhà cung cấp hay khách hàng, và theo tổng giá trị, số lượng hóa đơn, giá bán hay tiêu chí chất lượng? Dữ liệu hóa đơn chưa có chất lượng hàng hóa hoặc hiệu quả hợp tác.', [], [], None, False, context or {}, start, end)
    if intent in ('limits', 'advice'):
        tools = ['get_invoice_overview']
        evidence = [flow_evidence(data)]
        if intent == 'limits':
            answer = 'Chưa thể xác định lợi nhuận hoặc nhà cung cấp có giá bán tốt nhất từ tổng giá trị hóa đơn. Cần giá vốn, chi phí vận hành, tồn kho, doanh thu được ghi nhận và dữ liệu đơn giá của cùng sản phẩm/điều kiện giao dịch. Bán ra cao hơn mua vào không chứng minh có lãi.'
            sufficient = False
        else:
            role = args.get('role', 'supplier')
            ranking = partner_rankings(db, business_id, query_start, query_end, role)
            answer, evidence = focused_response('get_supplier_rankings' if role == 'supplier' else 'get_customer_rankings', ranking)
            tools = ['get_supplier_rankings' if role == 'supplier' else 'get_customer_rankings']
            answer += ' Giá trị lớn cho biết quy mô giao dịch; số lượng cho biết tần suất xử lý. Để ưu tiên rà soát chứng từ, xem cả tỷ trọng, tần suất và dữ liệu thiếu. Chưa có dữ liệu về mức độ thiết yếu, chất lượng, đơn giá cùng sản phẩm hoặc thanh toán để chọn đối tác quan trọng nhất.'
    elif intent in ('supplier', 'customer', 'partners'):
        roles = ('supplier', 'customer') if intent == 'partners' else (intent,)
        parts = []
        for role in roles:
            limit = args.get('limit', 5)
            if not 1 <= limit <= 30:
                return response('clarification', 'Hãy chọn Top từ 1 đến 30 đối tác.', [], [], None, False, {}, start, end)
            result = partner_rankings(db, business_id, query_start, query_end, role, limit)
            name = 'get_supplier_rankings' if role == 'supplier' else 'get_customer_rankings'
            description, tables = focused_response(name, result)
            parts.append(description)
            evidence.extend(tables)
            tools.append(name)
            sufficient &= result['unidentified']['invoice_count'] == 0 and result['partner_count'] > 0
            if result['common_partners'] and any(x in text for x in ('uu tien', 'phu thuoc', 'tap trung', 'dang quan tam')):
                parts.append('Ưu tiên đối chiếu chứng từ của các đối tác xuất hiện trong cả hai bảng; tỷ trọng thể hiện mức tập trung giao dịch đã lưu, chưa đủ kết luận phụ thuộc hoặc rủi ro kinh doanh.')
        answer = '\n'.join(parts)
    elif intent == 'date':
        result = invoice_extremes(db, business_id, query_start, query_end, args['mode'])
        answer, evidence = focused_response('get_invoice_date_extremes', result)
        sources, tools = result['invoices'], ['get_invoice_date_extremes']
        sufficient = bool(sources)
    elif intent == 'recommendation':
        result = recommendations(db, business_id, query_start, query_end, args['count'])
        answer, evidence = focused_response('get_invoice_recommendations', result)
        tools = ['get_invoice_recommendations']
        sufficient &= 'error' not in result
    elif intent == 'comparison_windows':
        if not all(1 <= args[key] <= 24 for key in ('earliest_months', 'latest_months')):
            return response('clarification', 'Hãy chọn mỗi kỳ từ 1 đến 24 tháng.', [], [], None, False, {}, start, end)
        result = compare_data_windows(db, business_id, query_start, query_end, **args)
        answer, evidence = focused_response('compare_invoice_data_windows', result)
        tools = ['compare_invoice_data_windows']
        sufficient &= 'error' not in result
        if 'error' not in result:
            numerical = combine_validation([result['period_a']['validation'], result['period_b']['validation']])
    elif intent in ('quality', 'ocr'):
        result = data_quality(rows)
        tools = ['get_invoice_data_quality']
        labels = {'invoice_date': 'Ngày lập', 'invoice_number': 'Mã hóa đơn', 'seller_tax_code': 'MST người bán', 'buyer_tax_code': 'MST người mua', 'seller_name': 'Tên người bán', 'buyer_name': 'Tên người mua', 'total_amount': 'Tổng giá trị'}
        evidence = [table('Trường thực sự thiếu trong database', ['Trường', 'Thiếu', 'Đã kiểm tra'], [[labels[key], value, len(rows)] for key, value in result['missing_fields'].items()])]
        answer = f'Đã kiểm tra {len(rows)} hóa đơn trong phạm vi. {result["missing_any_core"]} hóa đơn thiếu ít nhất một trường ngày lập, mã hóa đơn hoặc tổng tiền. Các trường trong bảng đều đã được truy vấn; trường không trả về ở công cụ khác không đồng nghĩa bị thiếu. Chưa đánh giá độ đúng OCR so với bản gốc.'
        if intent == 'ocr' or 'cai thien' in text:
            answer += '\n1. Đối chiếu ngày, mã và MST với bản gốc trước khi ghi nhận.\n2. Kiểm tra tổng tiền, tiền trước thuế và thuế bằng phép cộng; rà soát đơn vị tiền và dấu phân cách.\n3. Kiểm tra tên/MST đối tác đúng hướng mua vào hoặc bán ra; bổ sung các trường thiếu trong bảng.\n4. Chạy kiểm tra nghi trùng và lưu file nguồn để truy vết; không tự xác nhận trùng hoặc sai OCR chỉ từ thống kê.'
    elif intent in ('duplicates', 'anomalies'):
        name = 'detect_invoice_duplicates' if intent == 'duplicates' else 'detect_invoice_anomalies'
        result = execute_engine_tool(name, {}, db, business_id, query_start, query_end)
        tools = [name]
        if intent == 'duplicates':
            answer = f'Có {len(result["groups"])} nhóm nghi trùng trong {len(rows)} hóa đơn được xét. {result["limitation"]} {result["unidentified_count"]} hóa đơn thiếu định danh đối tác không được ghép nhóm.'
            for index, group in enumerate(result['groups'], 1):
                evidence.append(table(f'Nhóm nghi trùng {index}: {group["reason"]}', ['ID', 'Mã', 'Ngày', 'Đối tác', 'Giá trị'], [[r['invoice_id'], r['invoice_number'], r['invoice_date'], r['partner'], amount(r['total_amount'])] for r in group['invoices']]))
                sources.extend(group['invoices'])
            sufficient &= result['unidentified_count'] == 0
        else:
            answer = (f'Đã đánh giá {result["evaluated_groups"]} nhóm đủ mẫu; {result["insufficient_count"]} hóa đơn thuộc nhóm dưới 5 mẫu, '
                      f'{result["excluded_count"]} hóa đơn thiếu định danh hoặc tổng tiền. {result["method"]} ')
            answer += f'Có {len(result["candidates"])} hóa đơn cần rà soát theo quy tắc này; đây không phải kết luận gian lận.' if result['evaluated_groups'] else 'Không đủ dữ liệu để đánh giá bất thường; không thể kết luận không có hóa đơn bất thường.'
            evidence = [table('Cơ sở so sánh', ['Đối tác', 'Hướng', 'Số mẫu', 'Trung bình', 'Trung vị', 'MAD', 'Ngưỡng'], [[r['partner'], r['flow_type'], r['sample_count'], amount(r['mean']), amount(r['median']), amount(r['mad']), amount(r['threshold'])] for r in result['baselines']])]
            if result['candidates']:
                evidence.append(table('Hóa đơn cần rà soát', ['ID', 'Đối tác', 'Hướng', 'Giá trị', 'Độ lệch'], [[r['invoice']['invoice_id'], r['invoice']['partner'], r['invoice']['flow_type'], amount(r['invoice']['total_amount']), amount(r['deviation'])] for r in result['candidates']]))
                sources = [r['invoice'] for r in result['candidates']]
            sufficient = bool(result['evaluated_groups']) and not result['insufficient_count'] and not result['excluded_count']
    elif intent == 'top_invoices':
        limit = args['limit']
        if not 1 <= limit <= 50:
            return response('clarification', 'Hãy chọn từ 1 đến 50 hóa đơn.', [], [], None, False, {}, start, end)
        result = execute_engine_tool('get_top_invoices', {'limit': limit}, db, business_id, query_start, query_end)
        sources = result['invoices']
        tools = ['get_top_invoices']
        answer = f'Hiển thị {len(sources)}/{result["matched_count"]} hóa đơn theo tổng giá trị giảm dần. Có thể ưu tiên đối chiếu các bản ghi đầu bảng với file gốc; giá trị lớn tự nó không chứng minh bất thường.'
        evidence = [table('Top hóa đơn theo giá trị', ['ID', 'Ngày lập', 'Mã hóa đơn', 'Đối tác', 'Hướng', 'Tổng giá trị'], [[r['invoice_id'], r['invoice_date'], r['invoice_number'], r['partner'] or 'Chưa xác định', r['flow_type'], amount(r['total_amount'])] for r in sources])]
    elif intent == 'averages':
        tools, evidence = ['get_flow_averages'], [flow_evidence(data)]
        p, s = data['flow_summary']['purchase'], data['flow_summary']['sale']
        if p['invoice_count'] and s['invoice_count']:
            pa, sa = Decimal(p['total_amount']) / p['invoice_count'], Decimal(s['total_amount']) / s['invoice_count']
            answer = f'Trung bình mua vào {amount(pa)}, bán ra {amount(sa)} mỗi hóa đơn. ' + ('Mua vào cao hơn.' if pa > sa else 'Bán ra cao hơn.' if sa > pa else 'Hai hướng bằng nhau.') + ' Chỉ số mô tả quy mô chứng từ; không cho biết lợi nhuận hoặc đơn giá cùng sản phẩm.'
        else:
            answer, sufficient = 'Chưa đủ hóa đơn ở cả hai hướng để so sánh trung bình.', False
    elif intent == 'comparison' and len(periods) >= 2:
        evidence, parts = [], []
        tools = ['compare_periods']
        snapshots = []
        for label, period in zip(('A', 'B'), periods[:2]):
            left, right = intersect(period, start, end)
            snapshot = get_analytics(db, business_id, left, right)
            snapshots.append(snapshot)
            evidence.append(flow_evidence(snapshot, f'Kỳ {label}: {left} đến {right}'))
        a, b = snapshots
        total_a, total_b = Decimal(a['overview']['total_amount']), Decimal(b['overview']['total_amount'])
        percent = f' ({money((total_b-total_a)/abs(total_a)*100)}%)' if total_a else ' (không tính tỷ lệ vì kỳ A bằng 0)'
        parts.append(f'Chênh lệch tổng giá trị B − A: {amount(total_b-total_a)}{percent}.')
        for flow, label in (('purchase', 'Mua vào'), ('sale', 'Bán ra')):
            p, q = a['flow_summary'][flow], b['flow_summary'][flow]
            parts.append(f'{label}: chênh lệch {q["invoice_count"]-p["invoice_count"]} hóa đơn, {amount(Decimal(q["total_amount"])-Decimal(p["total_amount"]))}. Trung bình riêng từng hướng nằm trong hai bảng.')
        answer = ' '.join(parts)
        sufficient = all(x['overview']['invoice_count'] > 0 for x in snapshots)
        numerical = combine_validation([validate_analytics(x) for x in snapshots])
    elif intent in ('monthly', 'overview', 'report', 'validation'):
        tools = ['get_flow_monthly_summary'] if intent == 'monthly' else ['get_invoice_overview']
        # A question comparing the selected month with earlier months needs both scopes.
        history = get_analytics(db, business_id, start, end) if intent == 'monthly' and periods and 'thang truoc' in text else data
        if intent == 'monthly':
            evidence = [monthly_evidence(history)]
            if periods:
                evidence.insert(0, flow_evidence(data, f'Kỳ được hỏi: {query_start} đến {query_end}'))
            answer = f'Phạm vi kỳ được hỏi có {data["overview"]["invoice_count"]} hóa đơn, tổng giá trị {amount(data["overview"]["total_amount"])}. Bảng tách riêng mua vào, bán ra và chưa phân loại.'
            for flow, label in (('purchase', 'Mua vào'), ('sale', 'Bán ra')):
                key = flow + '_amount'
                active = [x for x in history['flow_monthly'] if Decimal(x[key]) != 0]
                if active:
                    high, low = max(active, key=lambda r: Decimal(r[key])), min(active, key=lambda r: Decimal(r[key]))
                    answer += f' {label}: cao nhất {high["month"]} ({amount(high[key])}), thấp nhất trong các tháng có giá trị {low["month"]} ({amount(low[key])}).'
            answer += ' Tháng hiện tại có thể chưa kết thúc; mức tổng thấp hơn không chứng minh hoạt động suy giảm.'
        elif intent == 'validation':
            answer = f'Đối chiếu số học: {numerical["passed_checks"]}/{numerical["total_checks"]} phép kiểm tra khớp. Kết quả này chỉ kiểm tra số học, không xác nhận OCR, ý định truy vấn hoặc tính pháp lý.'
            evidence = [flow_evidence(data)]
        else:
            answer = f'Có {len(rows)} hóa đơn đã xác nhận, tổng giá trị {amount(data["overview"]["total_amount"])}. '
            evidence = [flow_evidence(data), monthly_evidence(data)]
            for role in ('supplier', 'customer'):
                ranking = partner_rankings(db, business_id, query_start, query_end, role)
                description, tables = focused_response('get_supplier_rankings' if role == 'supplier' else 'get_customer_rankings', ranking)
                answer += '\n' + description
                evidence.extend(tables)
                sufficient &= ranking['unidentified']['invoice_count'] == 0
            quality = data_quality(rows)
            answer += f'\n{quality["missing_any_core"]} hóa đơn thiếu ngày/mã/tổng tiền. Chưa xác minh độ đúng OCR, thanh toán, lợi nhuận hoặc mức độ đầy đủ của kỳ dữ liệu.'
            if intent == 'report':
                tools = ['get_invoice_overview', 'get_supplier_rankings', 'get_customer_rankings', 'get_flow_monthly_summary', 'get_invoice_data_quality']
                answer += '\nHành động ưu tiên:\n' + '\n'.join(f'{i}. {value}' for i, value in enumerate(recommendations(db, business_id, query_start, query_end, 5)['recommendations'], 1))
    else:
        return None
    return response(intent, answer, evidence, tools, numerical, sufficient, new_context, start, end, sources)


def combine_validation(validations):
    checks = [{**check, 'code': f'{i}.{check["code"]}'} for i, value in enumerate(validations) for check in value['checks']]
    return {'status': 'passed' if all(x['passed'] for x in checks) else 'warning',
            'passed_checks': sum(x['passed'] for x in checks), 'total_checks': len(checks), 'checks': checks}


def response(intent, answer, evidence, tools, numerical, sufficient, context, start, end, sources=None):
    numerical = numerical or {'status': 'not_applicable', 'passed_checks': 0, 'total_checks': 0, 'checks': []}
    allowed = {
        'supplier': {'get_supplier_rankings'}, 'customer': {'get_customer_rankings'},
        'partners': {'get_supplier_rankings', 'get_customer_rankings'},
        'date': {'get_invoice_date_extremes'}, 'quality': {'get_invoice_data_quality'},
        'ocr': {'get_invoice_data_quality'}, 'duplicates': {'detect_invoice_duplicates'},
        'anomalies': {'detect_invoice_anomalies'}, 'top_invoices': {'get_top_invoices'},
        'averages': {'get_flow_averages'}, 'monthly': {'get_flow_monthly_summary'},
        'comparison': {'compare_periods'}, 'recommendation': {'get_invoice_recommendations'},
        'comparison_windows': {'compare_invoice_data_windows'},
        'overview': {'get_invoice_overview'}, 'validation': {'get_invoice_overview'},
        'report': {'get_invoice_overview', 'get_supplier_rankings', 'get_customer_rankings', 'get_flow_monthly_summary', 'get_invoice_data_quality'},
        'advice': {'get_supplier_rankings', 'get_customer_rankings'}, 'limits': {'get_invoice_overview'},
    }
    intent_valid = bool(tools) and set(tools) <= allowed.get(intent, set())
    verified = intent_valid and sufficient and numerical['status'] == 'passed'
    return {'answer': answer, 'evidence': evidence, 'tools_used': tools, 'sources': sources or [],
            'validation': numerical, 'intent': intent,
            'context': {**context, 'scope_start': start.isoformat() if start else None, 'scope_end': end.isoformat() if end else None},
            'assurance': {'verified': verified, 'intent': 'needs_clarification' if intent == 'clarification' else 'passed' if intent_valid else 'not_evaluated',
                          'data': 'sufficient' if sufficient else 'insufficient', 'numerical': numerical['status']}}
