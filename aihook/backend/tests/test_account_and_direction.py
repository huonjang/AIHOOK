"""Security boundaries, owner signup, and manual invoice direction."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.models import Invoice
from app.services.invoice_direction import suggest_flow
from app.security import hash_password, verify_password


def registration(email='owner2@example.com'):
    return {'email': email, 'password': 'This-is-a-long-strong-passphrase!',
            'owner_name': 'Owner Two', 'business_name': 'Second Business',
            'tax_code': None}


def test_password_hash_is_salted_and_verifiable():
    a, b = hash_password('abc-def1234!'), hash_password('abc-def1234!')
    assert a != b
    assert verify_password('abc-def1234!', a)
    assert not verify_password('wrong', a)
    assert not verify_password('abc-def1234!', 'malformed')


def test_signup_optional_tax_code_and_private_workspace(client):
    api, sessions, _, _ = client
    with sessions() as db:
        row = Invoice(business_id=1, file_name='private.pdf', file_path='private.pdf',
                      total_amount=Decimal('900'), invoice_date=date(2026, 9, 1),
                      verification_status='confirmed')
        db.add(row)
        db.commit()
        private_id = row.id
    response = api.post('/api/auth/register', json=registration())
    assert response.status_code == 201, response.text
    profile = response.json()
    assert profile['business']['tax_code'] is None
    assert profile['business']['id'] != 1
    assert api.get('/api/auth/me').json()['email'] == 'owner2@example.com'
    assert api.get('/api/invoices').json() == []
    assert api.get('/api/analytics/dashboard').json()['overview']['invoice_count'] == 0
    assert api.get(f'/api/invoices/{private_id}/analysis').status_code == 404
    assert api.get(f'/api/invoices/{private_id}/file').status_code == 404
    assert api.delete(f'/api/invoices/{private_id}').status_code == 404
    assert api.patch(f'/api/invoices/{private_id}/flow', json={'flow_type':'sale'}).status_code == 404
    assert api.get('/api/analytics/dashboard?business_id=1').status_code == 403
    assert api.get('/api/ai-data/summary?business_id=1').status_code == 403
    assert api.post('/api/auth/register', json=registration()).status_code == 409


def test_logout_login_and_requires_auth(client):
    api, _, _, _ = client
    assert api.post('/api/auth/logout').status_code == 200
    assert api.get('/api/invoices').status_code == 401
    assert api.get('/api/analytics/dashboard').status_code == 401
    assert api.post('/api/chat', json={'message':'Hello'}).status_code == 401
    assert api.get('/api/chat/status').status_code == 401
    assert api.get('/api/auth/me').status_code == 401
    assert api.post('/api/auth/login', json={'email':'fixture@example.com','password':'bad'}).status_code == 401
    login = api.post('/api/auth/login', json={'email':'FIXTURE@EXAMPLE.COM', 'password':'test-password-2026'})
    assert login.status_code == 200
    assert login.json()['business']['id'] == 1
    assert api.get('/api/invoices').status_code == 200


def test_manual_flow_reconciles_without_changing_ocr(client):
    api, sessions, _, _ = client
    with sessions() as db:
        for i, amount in enumerate([100, 200, 300]):
            db.add(Invoice(business_id=1, file_name=f'{i}.pdf', file_path=f'{i}.pdf',
                           total_amount=Decimal(str(amount)), invoice_date=date(2026, 9, i+1),
                           verification_status='confirmed'))
        db.commit()
        ids = list(db.scalars(select(Invoice.id).where(Invoice.business_id == 1).order_by(Invoice.id)))
    a, b, c = ids
    before = api.get('/api/analytics/dashboard').json()
    assert before['flow_summary']['unknown']['total_amount'] == '600.00'
    assert api.patch(f'/api/invoices/{a}/flow', json={'flow_type':'purchase'}).status_code == 200
    assert api.patch(f'/api/invoices/{b}/flow', json={'flow_type':'sale'}).status_code == 200
    assert api.patch(f'/api/invoices/{c}/flow', json={'flow_type':'invalid'}).status_code == 422
    after = api.get('/api/analytics/dashboard').json()
    assert after['overview']['total_amount'] == '600.00'
    assert after['flow_summary']['purchase'] == {'invoice_count':1, 'total_amount':'100.00'}
    assert after['flow_summary']['sale'] == {'invoice_count':1, 'total_amount':'200.00'}
    assert after['flow_summary']['unknown'] == {'invoice_count':1, 'total_amount':'300.00'}
    assert after['flow_monthly'][0]['purchase_amount'] == '100.00'
    assert after['flow_monthly'][0]['sale_amount'] == '200.00'
    assert api.patch(f'/api/invoices/{a}/flow', json={'flow_type':'unknown'}).status_code == 200
    assert api.get('/api/analytics/dashboard').json()['flow_summary']['unknown']['invoice_count'] == 2


def test_origin_rejection_and_no_auto_classification(client):
    api, sessions, _, _ = client
    with sessions() as db:
        invoice = Invoice(business_id=1, file_name='invoice.pdf', file_path='invoice.pdf',
                          seller_tax_code='0312345678', verification_status='confirmed')
        db.add(invoice)
        db.commit()
        invoice_id = invoice.id
    assert suggest_flow(business_tax_code='0312345678', seller_tax_code='0312345678')['suggestion'] == 'sale'
    assert suggest_flow(business_tax_code=None, seller_tax_code='0312345678')['suggestion'] is None
    assert suggest_flow(business_tax_code='0312345678', seller_tax_code='9999999999')['suggestion'] is None
    assert api.patch(f'/api/invoices/{invoice_id}/flow', json={'flow_type':'sale'},
                     headers={'Origin':'https://evil.example'}).status_code == 403
    with sessions() as db:
        assert db.get(Invoice, invoice_id).flow_type == 'unknown'


def test_account_profile_edit_and_tax_code_is_only_a_suggestion(client):
    api, sessions, _, _ = client
    with sessions() as db:
        item = Invoice(business_id=1, file_name='sale.pdf', file_path='sale.pdf',
                       seller_tax_code='0312345678', total_amount=Decimal('400.00'),
                       verification_status='confirmed')
        db.add(item)
        db.commit()
        invoice_id = item.id
    updated = api.patch('/api/auth/me', json={
        'business_name': 'Cửa hàng Mới', 'owner_name': 'Nguyễn A',
        'tax_code': '0312345678', 'phone': '',
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()['business']['tax_code'] == '0312345678'
    assert updated.json()['owner_name'] == 'Nguyễn A'
    suggestion = api.get(f'/api/invoices/{invoice_id}/flow-suggestion')
    assert suggestion.status_code == 200
    assert suggestion.json()['suggestion'] == 'sale'
    assert suggestion.json()['flow_type'] == 'unknown'
    assert api.get('/api/invoices').status_code == 200
    with sessions() as db:
        assert db.get(Invoice, invoice_id).flow_type == 'unknown'
    cleared = api.patch('/api/auth/me', json={
        'business_name': 'Cửa hàng Mới', 'owner_name': 'Nguyễn A',
        'tax_code': None, 'phone': None,
    })
    assert cleared.status_code == 200
    assert cleared.json()['business']['tax_code'] is None
