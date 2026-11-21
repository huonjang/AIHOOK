"""Regression: fixed deterministic replies for QA-026 and QA-047."""
from datetime import date
from decimal import Decimal

import pytest
from app.models import Invoice
from app.routers import chat


def add_invoice(db, number, amount, direction, day, business_id=1, status='confirmed'):
    db.add(Invoice(
        business_id=business_id,
        file_name=number + '.pdf', file_path=number + '.pdf',
        invoice_number=number, invoice_date=day,
        seller_name='Supplier', buyer_name='Customer',
        total_amount=Decimal(str(amount)),
        flow_type=direction, verification_status=status,
    ))


@pytest.fixture
def invoice_data(client, monkeypatch):
    api, sessions, _, _ = client
    with sessions() as db:
        add_invoice(db, 'MV-2026-0001', '100', 'purchase', date(2026, 1, 5))
        add_invoice(db, 'MV-2026-0002', '200', 'purchase', date(2026, 2, 5))
        add_invoice(db, 'BR-2026-0001', '300', 'sale', date(2026, 3, 5))
        add_invoice(db, 'BR-2026-9999', '8000', 'sale', date(2026, 3, 5), status='needs_review')
        add_invoice(db, 'BR-2026-8888', '9000', 'sale', date(2026, 3, 5), business_id=2)
        db.commit()
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test-model')
    monkeypatch.setattr(chat, '_call_model', lambda *a, **k: (_ for _ in ()).throw(AssertionError('model must not be called')))
    return api


def test_qa026_direction_counts_are_exact(invoice_data):
    response = invoice_data.post('/api/chat', json={
        'message': 'Có bao nhiêu hóa đơn mua vào và bao nhiêu hóa đơn bán ra?', 'use_ai': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert '2 hóa đơn mua vào' in body['answer']
    assert '1 hóa đơn bán ra' in body['answer']
    assert body['tools_used'] == ['get_invoice_overview']


def test_qa047_largest_invoice_is_scope_and_tenant_safe(invoice_data):
    response = invoice_data.post('/api/chat', json={
        'message': 'Hóa đơn nào có giá trị lớn nhất toàn bộ dữ liệu?', 'use_ai': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert 'BR-2026-0001' in body['answer']
    assert '300 đ' in body['answer']
    assert '8.000' not in body['answer']
    assert '9.000' not in body['answer']
    assert body['tools_used'] == ['search_invoices']


def test_qa047_respects_selected_date_filter(invoice_data):
    response = invoice_data.post('/api/chat', json={
        'message': 'Hóa đơn nào có giá trị lớn nhất?', 'use_ai': True,
        'start_date': '2026-01-01', 'end_date': '2026-02-28',
    })
    assert response.status_code == 200
    assert 'MV-2026-0002' in response.json()['answer']
    assert '200 đ' in response.json()['answer']
    assert 'BR-2026-0001' not in response.json()['answer']


def test_qa026_selected_date_filter(invoice_data):
    response = invoice_data.post('/api/chat', json={
        'message': 'Có bao nhiêu hóa đơn mua vào và bao nhiêu hóa đơn bán ra?', 'use_ai': True,
        'start_date': '2026-03-01', 'end_date': '2026-03-31',
    })
    assert response.status_code == 200
    assert '0 hóa đơn mua vào' in response.json()['answer']
    assert '1 hóa đơn bán ra' in response.json()['answer']
