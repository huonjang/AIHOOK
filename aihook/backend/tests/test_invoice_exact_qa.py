"""Regression tests for QA-001..004; no external model calls, isolated test DB."""
from datetime import date
from decimal import Decimal

import pytest

from app.models import Invoice
from app.routers import chat


@pytest.mark.parametrize(('question', 'expected'), [
    ('Đơn vị bán của hóa đơn MV-2026-0009 là ai?', 'Công ty TNHH Nội thất Cây Cào Meow'),
    ('Mã số thuế người bán trên hóa đơn MV-2026-0009?', '0307890167'),
    ('Người mua trên hóa đơn MV-2026-0009 là ai?', 'CÔNG TY TNHH CON MÈO'),
    ('Hóa đơn MV-2026-0009 là mua vào hay bán ra?', 'mua vào'),
])
def test_exact_invoice_answer_is_db_grounded(client, monkeypatch, question, expected):
    api, sessions, _, _ = client
    with sessions() as db:
        db.add(Invoice(
            business_id=1,
            file_name='MV-2026-0009.pdf', file_path='MV-2026-0009.pdf',
            invoice_number='MV-2026-0009', invoice_date=date(2026, 10, 27),
            seller_name='Công ty TNHH Nội thất Cây Cào Meow',
            seller_tax_code='0307890167',
            buyer_name='CÔNG TY TNHH CON MÈO', buyer_tax_code='0312345678',
            flow_type='purchase', verification_status='confirmed',
            total_amount=Decimal('9123840'),
        ))
        db.commit()
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test-model')

    def forbidden_model(*args, **kwargs):
        raise AssertionError('Exact invoice lookup must not call the language model')

    monkeypatch.setattr(chat, '_call_model', forbidden_model)
    response = api.post('/api/chat', json={'message': question, 'use_ai': True})
    assert response.status_code == 200
    data = response.json()
    assert expected.casefold() in data['answer'].casefold()
    assert data['tools_used'] == ['get_invoice_details']
    assert data['sources'][0]['invoice_number'] == 'MV-2026-0009'


def test_nonexistent_code_does_not_hallucinate(client, monkeypatch):
    api, _, _, _ = client
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test-model')
    monkeypatch.setattr(chat, '_call_model', lambda *a, **k: (_ for _ in ()).throw(AssertionError('model called')))
    response = api.post('/api/chat', json={'message': 'Người bán của hóa đơn MV-2099-9999 là ai?', 'use_ai': True})
    assert response.status_code == 200
    assert 'Không tìm thấy hóa đơn' in response.json()['answer']


def test_date_scope_does_not_leak_invoice(client, monkeypatch):
    api, sessions, _, _ = client
    with sessions() as db:
        db.add(Invoice(
            business_id=1, file_name='test.pdf', file_path='test.pdf',
            invoice_number='MV-2026-0009', invoice_date=date(2026, 10, 27),
            seller_name='DO NOT EXPOSE THIS SELLER', verification_status='confirmed',
            flow_type='purchase', total_amount=Decimal('100'),
        ))
        db.commit()
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test-model')
    response = api.post('/api/chat', json={
        'message': 'Người bán của hóa đơn MV-2026-0009?', 'use_ai': True,
        'start_date': '2026-11-01', 'end_date': '2026-11-30',
    })
    assert response.status_code == 200
    answer = response.json()['answer']
    assert 'Không tìm thấy' in answer
    assert 'DO NOT EXPOSE' not in answer


def test_unknown_direction_is_not_inferred(client, monkeypatch):
    api, sessions, _, _ = client
    with sessions() as db:
        db.add(Invoice(
            business_id=1, file_name='test.pdf', file_path='test.pdf',
            invoice_number='MV-2026-0009', invoice_date=date(2026, 10, 27),
            seller_name='Seller', verification_status='confirmed',
            flow_type='unknown', total_amount=Decimal('100'),
        ))
        db.commit()
    monkeypatch.setenv('AIHOOK_AI_KEY', 'test-key')
    monkeypatch.setenv('AIHOOK_AI_MODEL', 'test-model')
    response = api.post('/api/chat', json={
        'message': 'Hóa đơn MV-2026-0009 là mua vào hay bán ra?', 'use_ai': True,
    })
    assert response.status_code == 200
    assert 'chưa được xác nhận' in response.json()['answer']
