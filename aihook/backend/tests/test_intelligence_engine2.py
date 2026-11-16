from datetime import date
from decimal import Decimal

import pytest

from app.models import Business, Invoice
from app.routers import chat
from app.services import intelligence_engine as engine
from app.services.invoice_ai_tools import execute_invoice_tool
from app.services.invoice_intelligence import partner_rankings
from app.services.analytics_service import get_analytics
from app.services.numerical_validation import validate_analytics
from intelligence_prompts import CASES


def seed(sessions):
    with sessions() as db:
        db.add(Business(id=2, name='Other'))
        db.flush()
        for i, (flow, seller, tax, buyer, value, day) in enumerate([
            ('purchase', 'Large supplier', '001', 'Our company', '1000', date(2026, 8, 2)),
            ('purchase', 'Frequent', '002', 'Our company', '10', date(2026, 9, 2)),
            ('purchase', 'Frequent', '002', 'Our company', '10', date(2026, 9, 3)),
            ('purchase', 'Frequent', '002', 'Our company', '10', date(2026, 10, 2)),
            ('sale', 'Our company', 'OWN', None, '5000', date(2026, 10, 3)),
            ('sale', 'Our company', 'OWN', None, '7000', date(2026, 11, 9)),
            ('sale', 'Our company', 'OWN', 'Customer A', '200', date(2026, 11, 9)),
        ]):
            db.add(Invoice(business_id=1, file_name='test', file_path='test', invoice_number=f'INV-{i}',
                           flow_type=flow, seller_name=seller, seller_tax_code=tax, buyer_name=buyer,
                           total_amount=Decimal(value), invoice_date=day, verification_status='confirmed'))
        db.add(Invoice(business_id=2, file_name='test', file_path='test', invoice_number='SECRET',
                       seller_name='OTHER TENANT', flow_type='purchase', total_amount=Decimal('999999'),
                       invoice_date=date(2026, 11, 1), verification_status='confirmed'))
        db.commit()


def configure(monkeypatch):
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'llama3.2:3b')
    monkeypatch.setattr(engine, 'local_today', lambda: date(2026, 11, 17))

    def no_model(*args, **kwargs):
        raise AssertionError('Regression prompt must route deterministically without an LLM')
    monkeypatch.setattr(chat, '_call_model', no_model)


@pytest.mark.parametrize('index', range(len(CASES)))
def test_original_questions_route_and_answer_without_model(client, monkeypatch, index):
    api, sessions, _, _ = client
    seed(sessions)
    configure(monkeypatch)
    question, expected = CASES[index]
    context = None
    if index in (22, 23):
        for previous in range(21, index):
            response = api.post('/api/chat', json={'message': CASES[previous][0], 'use_ai': True, 'context': context})
            assert response.status_code == 200
            context = response.json()['context']
    response = api.post('/api/chat', json={'message': question, 'use_ai': True, 'context': context})
    assert response.status_code == 200
    body = response.json()
    assert body['intent'] == expected
    assert body['answer']
    assert 'OTHER TENANT' not in str(body)
    assert 'Gợi ý bổ sung từ AI' not in body['answer']
    assert body['assurance']['intent'] in ('passed', 'needs_clarification')
    if body['assurance']['verified']:
        assert body['assurance']['data'] == 'sufficient'
        assert body['validation']['status'] == 'passed'
    if expected == 'recommendation':
        assert len(body['answer'].splitlines()) == 5
        assert body['evidence'] == []
    if expected == 'supplier':
        assert len(body['evidence']) == 2
        assert 'Frequent' in body['answer']
    if expected == 'quality':
        assert body['tools_used'] == ['get_invoice_data_quality']
        assert '0 hóa đơn thiếu ít nhất' in body['answer']
        assert 'trường không trả về' in body['answer']
    if expected == 'anomalies':
        assert body['assurance']['data'] == 'insufficient'
        assert 'Không đủ dữ liệu' in body['answer']
        assert 'compare_periods' not in body['tools_used']
    if expected == 'clarification':
        assert '?' in body['answer']
        assert not body['assurance']['verified']


def test_unidentified_customers_never_become_a_customer(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        data = get_analytics(db, 1, None, None)
        assert len(data['customers']) == 1
        assert data['customers'][0]['buyer_name'] == 'Customer A'
        assert data['unidentified_partners']['sale'] == {'invoice_count': 2, 'total_amount': '12000.00'}
        assert validate_analytics(data)['status'] == 'passed'
        result = partner_rankings(db, 1, None, None, 'customer')
        assert result['partner_count'] == 1
        assert result['invoice_count'] == 3
        assert result['by_amount'][0]['share_percent'] == '1.64'


def test_ranking_overlap_computed_by_identity(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        result = partner_rankings(db, 1, None, None, limit=1)
        assert result['by_amount'][0]['seller_name'] == 'Large supplier'
        assert result['by_count'][0]['seller_name'] == 'Frequent'
        assert result['common_suppliers'] == []
        result = partner_rankings(db, 1, None, None, limit=5)
        assert len(result['common_suppliers']) == 2


def test_calendar_month_query_matches_total_monthly_data(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    configure(monkeypatch)
    body = api.post('/api/chat', json={'message': 'Hoạt động tháng này như thế nào?', 'use_ai': True}).json()
    assert body['context']['query_start'] == '2026-11-01'
    assert body['context']['query_end'] == '2026-11-30'
    assert '2 hóa đơn' in body['answer']
    with sessions() as db:
        monthly = get_analytics(db, 1, None, None)['monthly']
        november = next(row for row in monthly if row['month'] == '2026-11')
        assert november['invoice_count'] == 2
        assert november['total_amount'] == '7200.00'


def test_anomaly_detection_has_actual_baseline_and_tenant_scope(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        for i, value in enumerate([10, 10, 10, 10, 1000]):
            db.add(Invoice(business_id=1, file_name='test', file_path='test', invoice_number=f'OUT-{i}',
                           flow_type='purchase', seller_name='Baseline', seller_tax_code='003',
                           invoice_date=date(2026, 11, 1), total_amount=Decimal(value), verification_status='confirmed'))
        db.commit()
        result = execute_invoice_tool('detect_invoice_anomalies', {}, db, 1, None, None)
        assert result['evaluated_groups'] == 1
        assert result['baselines'][0]['median'] == '10.00'
        assert result['baselines'][0]['mean'] == '208.00'
        assert result['baselines'][0]['mad'] == '0.00'
        assert result['candidates'][0]['invoice']['total_amount'] == '1000.00'
        assert result['candidates'][0]['deviation'] == '990.00'
        assert 'OTHER TENANT' not in str(result)


def test_duplicates_are_suspected_not_confirmed(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        for _ in range(2):
            db.add(Invoice(business_id=1, file_name='test', file_path='test', invoice_number='DUP',
                           flow_type='purchase', seller_name='Same', seller_tax_code='004',
                           invoice_date=date(2026, 11, 1), total_amount=Decimal('100'), verification_status='confirmed'))
        db.commit()
        result = execute_invoice_tool('detect_invoice_duplicates', {}, db, 1, None, None)
        assert len(result['groups']) == 1
        assert result['groups'][0]['classification'] == 'suspected'
        assert result['confirmed_duplicates'] == []


def test_followup_context_scope_reset_and_no_writes(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    configure(monkeypatch)
    before = api.get('/api/invoices').json()
    first = api.post('/api/chat', json={'message': CASES[21][0], 'use_ai': True,
                                      'start_date': '2026-09-01', 'end_date': '2026-09-30'}).json()
    second = api.post('/api/chat', json={'message': CASES[22][0], 'use_ai': True, 'context': first['context'],
                                       'start_date': '2026-09-01', 'end_date': '2026-09-30'}).json()
    assert second['intent'] == 'supplier'
    assert second['context']['criterion'] == 'count'
    assert second['context']['query_start'] == '2026-09-01'
    assert 'Large supplier' not in second['answer']
    reset = api.post('/api/chat', json={'message': CASES[22][0], 'use_ai': True, 'context': second['context']}).json()
    assert reset['intent'] == 'clarification'
    assert api.get('/api/invoices').json() == before


@pytest.mark.parametrize('question,start,end', [
    ('Nhà cung cấp đứng đầu quý 3/2026', date(2026, 7, 1), date(2026, 9, 30)),
    ('Nhà cung cấp đứng đầu từ tháng 8/2026 đến tháng 10/2026', date(2026, 8, 1), date(2026, 10, 31)),
    ('Khách hàng đứng đầu năm 2026', date(2026, 1, 1), date(2026, 12, 31)),
])
def test_supported_calendar_periods(question, start, end):
    assert engine.resolve_periods(question, date(2026, 11, 17)) == [(start, end)]


def test_unsupported_temporal_request_does_not_silently_query_all_time(client, monkeypatch):
    api, sessions, _, _ = client
    seed(sessions)
    configure(monkeypatch)
    body = api.post('/api/chat', json={'message': 'Nhà cung cấp đứng đầu tuần trước', 'use_ai': True}).json()
    assert body['intent'] == 'clarification'
    assert body['tools_used'] == []
    assert not body['assurance']['verified']
    assert body['validation']['status'] == 'not_applicable'


def test_negative_or_zero_total_does_not_invent_customer_identity(client):
    _, sessions, _, _ = client
    with sessions() as db:
        for name in (None, ' ', 'Chưa rõ đối tác', 'N/A'):
            db.add(Invoice(business_id=1, file_name='test', file_path='test', invoice_number='TEST',
                           flow_type='sale', buyer_name=name, total_amount=Decimal('0'),
                           verification_status='confirmed'))
        db.commit()
        ranking = partner_rankings(db, 1, None, None, 'customer')
        assert ranking['partner_count'] == 0
        assert ranking['by_amount'] == []
        assert ranking['unidentified']['invoice_count'] == 4
