"""Regression tests for useful grounded advice without invented numeric claims."""
from datetime import date
from decimal import Decimal

from app.models import Invoice
from app.routers import chat
from app.services.analytics_narrative import build_observations, build_recommendations


def _put(sessions):
    with sessions() as db:
        for number, amount, seller, day in (
            ('HD-001', '100.00', 'An Phat', date(2026, 8, 2)),
            ('HD-002', '300.00', 'An Phat', date(2026, 8, 20)),
            ('HD-003', '500.00', 'Binh Minh', date(2026, 10, 5)),
            ('HD-004', '200.00', 'Binh Minh', date(2026, 10, 8)),
            ('HD-005', '100.00', 'Binh Minh', date(2026, 10, 11)),
        ):
            db.add(Invoice(
                business_id=1, file_name='test.pdf', file_path='test.pdf', invoice_number=number,
                seller_name=seller, total_amount=Decimal(amount), invoice_date=day,
                verification_status='confirmed',
            ))
        db.commit()


def test_supplier_observations_match_values_and_frequency(client):
    api, sessions, _, _ = client
    _put(sessions)
    with sessions() as db:
        from app.services.invoice_ai_tools import execute_invoice_tool
        result = execute_invoice_tool('get_supplier_summary', {'limit': 5}, db, 1, None, None)
    insights = build_observations([('get_supplier_summary', result)])
    narrative = ' '.join(insights)
    assert 'Binh Minh' in narrative
    assert '800 đ' in narrative
    assert '66.67%' in narrative
    assert 'Binh Minh' in narrative  # top supplier by value and frequency in this fixture
    assert 'Binh Minh dẫn đầu về tổng giá trị' in narrative


def test_monthly_and_partial_month_observations(client):
    _, sessions, _, _ = client
    _put(sessions)
    from app.services.invoice_ai_tools import execute_invoice_tool
    with sessions() as db:
        result = execute_invoice_tool('get_monthly_summary', {}, db, 1, None, None)
    text = '\n'.join(build_observations([('get_monthly_summary', result)], today=date(2026, 10, 15)))
    assert 'tháng 10/2026' in text
    assert '800 đ' in text
    assert 'ngày 15/10/2026' in text
    assert 'tháng 8/2026' in text


def test_narrative_requires_grounding_and_does_not_invent():
    assert build_observations([('get_invoice_overview', {'error': 'bad'})]) == []
    assert build_recommendations('Xin chào', []) == []
    assert chat._strip_numeric_claims('Có 50 hóa đơn.\nCác giao dịch cần được rà soát.') == 'Các giao dịch cần được rà soát.'
    assert chat._strip_numeric_claims('1. Nên kiểm tra hóa đơn gốc.\n2. Tăng 150%') == 'Nên kiểm tra hóa đơn gốc.'
    assert chat._strip_numeric_claims('Mình đã truy vấn dữ liệu. Các số liệu đối chiếu bên dưới.') == ''


def test_broad_questions_expand_tools_without_another_model_call():
    calls = [{'id':'a', 'type':'function', 'function':{'name':'get_invoice_overview', 'arguments':'{}'}}]
    calls = chat._supplement_tool_calls('Phân tích tổng quan mọi hóa đơn và nhận xét', calls)
    assert [x['function']['name'] for x in calls] == ['get_invoice_overview', 'get_monthly_summary', 'get_supplier_summary']
    assert len(chat._supplement_tool_calls('Bao nhiêu hóa đơn', calls)) == 3
    assert len(chat._supplement_tool_calls('Viết báo cáo', calls)) == 3
    assert not chat._is_broad_analysis('Tôi có bao nhiêu hóa đơn?')


def test_compare_periods_observations_and_evidence_columns(client):
    _, sessions, _, _ = client
    _put(sessions)
    from app.services.invoice_ai_tools import execute_invoice_tool
    params = {
        'period_a_start': '2026-08-01', 'period_a_end': '2026-08-31',
        'period_b_start': '2026-10-01', 'period_b_end': '2026-10-31',
    }
    with sessions() as db:
        result = execute_invoice_tool('compare_periods', params, db, 1, None, None)
    assert 'error' not in result
    text = '\n'.join(build_observations([('compare_periods', result)]))
    assert '400 đ' in text
    assert '100.00%' in text
    evidence = chat._evidence_for_tool('compare_periods', result)
    assert evidence['rows'][2][3] == '—' or evidence['rows'][2][3].endswith('đ')
    assert evidence['rows'][3][2] == '100.00%'


def test_report_prompts_yield_contextual_five_recommendations(client):
    _, sessions, _, _ = client
    _put(sessions)
    from app.services.invoice_ai_tools import execute_invoice_tool
    with sessions() as db:
        overview = execute_invoice_tool('get_invoice_overview', {}, db, 1, None, None)
        monthly = execute_invoice_tool('get_monthly_summary', {}, db, 1, None, None)
        suppliers = execute_invoice_tool('get_supplier_summary', {}, db, 1, None, None)
    results = [('get_invoice_overview', overview), ('get_monthly_summary', monthly), ('get_supplier_summary', suppliers)]
    recs = build_recommendations('Hãy tạo báo cáo và 5 khuyến nghị quản lý', results)
    assert len(recs) == 5
    assert any('nhà cung cấp' in x for x in recs)
    assert any('tháng' in x for x in recs)
    assert all('doanh thu đã' not in x for x in recs)


def test_extended_tools_keep_requested_dates():
    calls = [{
        'id': 'abc', 'type': 'function',
        'function': {'name': 'get_invoice_overview', 'arguments': '{"start_date":"2026-10-01","end_date":"2026-10-31"}'},
    }]
    extended = chat._supplement_tool_calls('Phân tích tổng quan tháng 10/2026', calls)
    for call in extended[1:]:
        args = __import__('json').loads(call['function']['arguments'])
        assert args['start_date'] == '2026-10-01'
        assert args['end_date'] == '2026-10-31'


def test_ai_returns_qualitative_facts_even_if_model_only_acknowledges(client, monkeypatch):
    api, sessions, _, _ = client
    _put(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'ollama')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'llama3.2:3b')
    calls = []
    def fake_call(messages, include_tools):
        calls.append(include_tools)
        if include_tools:
            return {'role': 'assistant', 'content': '', 'tool_calls': [{
                'id': 'model_1', 'type': 'function',
                'function': {'name': 'get_invoice_overview', 'arguments': '{}'},
            }]}
        return {'role':'assistant', 'content': 'Mình đã truy vấn dữ liệu. Các số liệu chính xác được hiển thị bên dưới.'}
    monkeypatch.setattr(chat, '_call_model', fake_call)
    response = api.post('/api/chat', json={
        'message': 'Hãy phân tích tổng quan hóa đơn và cho tôi nhận xét.', 'use_ai': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert calls == [True, False]
    assert body['tools_used'] == ['get_invoice_overview', 'get_monthly_summary', 'get_supplier_summary']
    assert body['validation']['status'] == 'passed'
    assert 'Nhận xét dựa trên dữ liệu đã kiểm chứng' in body['answer']
    assert '1.200 đ' in body['answer']
    assert 'Binh Minh' in body['answer']
    assert 'tháng 10/2026' in body['answer']
    assert 'Mình đã truy vấn dữ liệu' not in body['answer']
