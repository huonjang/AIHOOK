from datetime import date
from decimal import Decimal
from app.models import Business, Invoice


def seed(sessions):
    with sessions() as db:
        db.add(Business(id=2, name='Other'))
        db.flush()
        for day, amount, status, business, name, tax in [
            (date(2026,1,1),'100.10','confirmed',1,'Công ty A','001'),
            (date(2026,3,31),'200.20','confirmed',1,'Tên khác của A','001'),
            (date(2026,3,31),'50.00','confirmed',1,'Công ty B',None),
            (date(2026,3,1),'999','needs_review',1,'X',None),
            (date(2026,3,1),'888','uploaded',1,'X',None),
            (date(2026,3,1),'777','confirmed',2,'Other',None),
        ]:
            db.add(Invoice(business_id=business,file_name='sample.pdf',file_path='sample.pdf',invoice_date=day,total_amount=Decimal(amount),verification_status=status,seller_name=name,seller_tax_code=tax))
        db.commit()


def test_totals_months_suppliers_and_read_only(client):
    api, sessions, _, _ = client
    seed(sessions)
    before = api.get('/api/invoices').json()
    response=api.get('/api/analytics/dashboard')
    assert response.status_code == 200
    data=response.json()
    assert data['overview'] == {'invoice_count':3,'total_amount':'350.30','average_amount':'116.77','supplier_count':2,'undated_count':0,'undated_total_amount':'0.00'}
    assert [r['month'] for r in data['monthly']] == ['2026-01','2026-02','2026-03']
    assert data['monthly'][1]['total_amount'] == '0.00'
    assert data['suppliers'][0]['total_amount'] == '300.30'
    assert data['suppliers'][0]['invoice_count'] == 2
    for endpoint in ['overview','monthly','suppliers']:
        assert api.get('/api/analytics/'+endpoint).json()==data[endpoint]
    assert api.get('/api/invoices').json()==before


def test_inclusive_invoice_dates_and_empty(client):
    api,sessions,_,_=client
    seed(sessions)
    data=api.get('/api/analytics/dashboard?start_date=2026-03-31&end_date=2026-03-31').json()
    assert data['overview']['invoice_count']==2
    assert data['overview']['total_amount']=='250.20'
    empty=api.get('/api/analytics/dashboard?start_date=2025-01-01&end_date=2025-02-28').json()
    assert empty['overview']['average_amount']=='0.00'
    assert len(empty['monthly'])==2
    assert empty['suppliers']==[]


def test_invalid_ranges_and_business(client):
    api,_,_,_=client
    for query in ['start_date=2026-01-01','start_date=2026-03-01&end_date=2026-01-01']:
        assert api.get('/api/analytics/dashboard?'+query).status_code==400
    assert api.get('/api/analytics/dashboard?start_date=bad&end_date=bad').status_code==422
    assert api.get('/api/analytics/dashboard?business_id=99').status_code==404


def test_undated_legacy_invoice(client):
    api,sessions,_,_=client
    with sessions() as db:
        db.add(Invoice(business_id=1,file_name='old.pdf',file_path='old.pdf',total_amount=Decimal('10'),verification_status='confirmed'))
        db.commit()
    data=api.get('/api/analytics/dashboard').json()
    assert data['overview']['undated_count']==1
    assert data['overview']['undated_total_amount']=='10.00'
    assert data['overview']['total_amount']=='10.00'
    assert data['monthly']==[]
    assert api.get('/api/analytics/dashboard?start_date=2026-01-01&end_date=2026-12-31').json()['overview']['invoice_count']==0
