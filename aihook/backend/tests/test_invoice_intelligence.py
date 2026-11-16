from datetime import date
from decimal import Decimal

import pytest

from app.models import Business, Invoice
from app.routers import chat
from app.services.invoice_ai_tools import execute_invoice_tool
from app.services.analytics_service import get_analytics
from app.services.numerical_validation import validate_analytics


def seed(sessions):
    with sessions() as db:
        db.add(Business(id=2, name='Other'))
        db.flush()
        for business, flow, seller, tax, buyer, value, day, status in [
            (1, 'purchase', 'High value', '001', 'Our company', '1000', date(2026, 1, 1), 'confirmed'),
            (1, 'purchase', 'Frequent', '002', 'Our company', '10', date(2026, 2, 1), 'confirmed'),
            (1, 'purchase', 'Frequent alias', '002', 'Our company', '20', date(2026, 2, 2), 'confirmed'),
            (1, 'sale', 'Our company', '999', 'Customer A', '9000', date(2026, 3, 1), 'confirmed'),
            (1, 'unknown', 'Unknown seller', None, 'Unknown buyer', '50000', None, 'confirmed'),
            (1, 'purchase', 'Unverified', None, 'Our company', '100000', date(2025, 1, 1), 'needs_review'),
            (2, 'purchase', 'Other tenant', None, 'Other', '999999', date(2024, 1, 1), 'confirmed'),
        ]:
            db.add(Invoice(business_id=business, flow_type=flow, file_name='test.pdf', file_path='test.pdf',
                           seller_name=seller, seller_tax_code=tax, buyer_name=buyer,
                           invoice_date=day, invoice_number=f'INV-{value}',
                           total_amount=Decimal(value), verification_status=status))
        db.commit()


def no_model(*args, **kwargs):
    raise AssertionError('Clear intent must query the backend without calling a model')


def test_role_aware_analytics_and_validation(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        data = get_analytics(db, 1, None, None)
        assert data['overview']['invoice_count'] == 5
        assert len(data['suppliers']) == 2
        assert sum(Decimal(row['total_amount']) for row in data['suppliers']) == Decimal('1030')
        assert data['customers'][0]['buyer_name'] == 'Customer A'
        assert data['customers'][0]['total_amount'] == '9000.00'
        assert validate_analytics(data)['status'] == 'passed'
        data['customers'][0]['total_amount'] = '1'
        assert validate_analytics(data)['status'] == 'warning'


@pytest.mark.parametrize('question,tool', [
    ('Nhà cung cấp nào có tổng giá trị lớn nhất? So sánh nhóm đứng đầu theo tổng giá trị và số lượng.', 'get_supplier_rankings'),
    ('Top 5 khách hàng theo giá trị và số lượng hóa đơn', 'get_customer_rankings'),
])
def test_rankings_are_single_role_aware_query(client, monkeypatch, question, tool):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    before = api.get('/api/invoices').json()
    body = api.post('/api/chat', json={'message': question, 'use_ai': True}).json()
    assert body['tools_used'] == [tool]
    assert len(body['evidence']) == 2
    if tool == 'get_supplier_rankings':
        assert body['evidence'][0]['rows'][0][0] == 'High value'
        assert body['evidence'][1]['rows'][0][0] == 'Frequent'
        assert 'Other tenant' not in str(body)
        assert 'Our company' not in str(body)
    else:
        assert body['evidence'][0]['rows'][0][0] == 'Customer A'
    assert before == api.get('/api/invoices').json()


@pytest.mark.parametrize('question,columns,expected_days', [
    ('Hóa đơn gần nhất và sớm nhất khác nhau thế nào?', 3, True),
    ('Hóa đơn sớm nhất là ngày mấy?', 2, False),
    ('Hóa đơn gần nhất là hóa đơn nào?', 2, False),
])
def test_date_extremes_focused_and_scoped(client, monkeypatch, question, columns, expected_days):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    body = api.post('/api/chat', json={'message': question, 'use_ai': True}).json()
    assert body['tools_used'] == ['get_invoice_date_extremes']
    assert len(body['evidence']) == 1
    assert len(body['evidence'][0]['columns']) == columns
    assert ('59 ngày' in body['answer']) == expected_days
    assert 'thống kê theo tháng' not in body['answer']
    scoped = api.post('/api/chat', json={'message': question, 'use_ai': True,
                      'start_date': '2026-02-01', 'end_date': '2026-02-28'}).json()
    assert all(source['invoice_date'].startswith('2026-02') for source in scoped['sources'])


@pytest.mark.parametrize('count', [1, 3, 5, 7, 10])
def test_recommendations_exact_count_no_unrequested_report(client, monkeypatch, count):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    body = api.post('/api/chat', json={'message': f'Đưa ra {count} khuyến nghị quản lý dữ liệu hóa đơn', 'use_ai': True}).json()
    assert len(body['answer'].splitlines()) == count
    assert body['evidence'] == []
    assert body['tools_used'] == ['get_invoice_recommendations']
    assert 'Nhận xét dựa trên' not in body['answer']
    assert '999999' not in body['answer']


def test_extremes_empty_undated_and_ties(client):
    _, sessions, _, _ = client
    with sessions() as db:
        db.add(Invoice(business_id=1, file_name='test', file_path='test', verification_status='confirmed'))
        db.commit()
        result = execute_invoice_tool('get_invoice_date_extremes', {}, db, 1, None, None)
        assert result['earliest'] is None
        assert result['undated_count'] == 1
        for number in ('FIRST', 'SECOND'):
            db.add(Invoice(business_id=1, file_name='test', file_path='test', verification_status='confirmed',
                           invoice_date=date(2026, 1, 1), invoice_number=number))
        db.commit()
        result = execute_invoice_tool('get_invoice_date_extremes', {}, db, 1, None, None)
        assert result['earliest']['invoice_number'] == result['latest']['invoice_number'] == 'FIRST'
        assert result['days_between'] == 0


def test_identical_model_calls_are_deduplicated(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')

    def model(messages, include_tools):
        if include_tools:
            return {'tool_calls': [
                {'id': 'one', 'type': 'function', 'function': {'name': 'get_invoice_overview', 'arguments': '{}'}},
                {'id': 'two', 'type': 'function', 'function': {'name': 'get_invoice_overview', 'arguments': '{ }'}},
            ]}
        return {'content': ''}

    monkeypatch.setattr(chat, '_call_model', model)
    body = api.post('/api/chat', json={'message': 'Có bao nhiêu hóa đơn?', 'use_ai': True}).json()
    assert body['tools_used'] == ['get_invoice_overview']
    assert len(body['evidence']) == 1


def test_three_month_windows_use_data_boundaries_and_report_overlap(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    body = api.post('/api/chat', json={
        'message': 'Truy vấn 3 tháng gần nhất và 3 tháng xa nhất, so sánh việc kinh doanh', 'use_ai': True,
    }).json()
    assert body['tools_used'] == ['compare_invoice_data_windows']
    assert body['evidence'][0]['rows'][0][1:3] == ['2026-01-01', '2026-03-31']
    assert body['evidence'][0]['rows'][1][1:3] == ['2026-01-01', '2026-03-31']
    assert 'chồng lấp 90 ngày' in body['answer']
    assert body['validation']['status'] == 'passed'


def test_date_extremes_explicit_month_routes_without_model(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    body = api.post('/api/chat', json={'message': 'Hóa đơn sớm nhất tháng 2/2026', 'use_ai': True}).json()
    assert body['tools_used'] == ['get_invoice_date_extremes']
    assert body['sources'][0]['invoice_date'] == '2026-02-01'


def test_explicit_month_comparison_routes_without_model(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test')
    monkeypatch.setattr(chat, '_call_model', no_model)
    body = api.post('/api/chat', json={'message': 'So sánh tháng 1/2026 với tháng 2/2026', 'use_ai': True}).json()
    assert body['tools_used'] == ['compare_periods']
    assert len(body['evidence']) == 2  # Separate role-aware tables for A and B.
