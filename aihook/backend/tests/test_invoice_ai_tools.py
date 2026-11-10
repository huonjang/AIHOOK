from datetime import date
from decimal import Decimal

from app.models import Invoice
from app.services.invoice_ai_tools import execute_invoice_tool


def seed(sessions):
    with sessions() as db:
        db.add_all([
            Invoice(business_id=1, file_name='a.pdf', file_path='a.pdf', invoice_number='HD-A-001',
                    invoice_date=date(2026, 1, 10), seller_name='Cong ty An Phat', seller_tax_code='0101',
                    total_amount=Decimal('100.00'), verification_status='confirmed', source_page=1),
            Invoice(business_id=1, file_name='b.pdf', file_path='b.pdf', invoice_number='HD-A-002',
                    invoice_date=date(2026, 1, 20), seller_name='Cong ty An Phat', seller_tax_code='0101',
                    total_amount=Decimal('200.00'), verification_status='confirmed', source_page=2),
            Invoice(business_id=1, file_name='c.pdf', file_path='c.pdf', invoice_number='HD-B-001',
                    invoice_date=date(2026, 2, 5), seller_name='Cong ty Sao Viet', seller_tax_code='0202',
                    total_amount=Decimal('50.00'), verification_status='confirmed', source_page=3),
            Invoice(business_id=1, file_name='review.pdf', file_path='review.pdf', invoice_number='HD-REVIEW',
                    invoice_date=date(2026, 1, 15), seller_name='Cong ty An Phat',
                    total_amount=Decimal('999.00'), verification_status='needs_review'),
            Invoice(business_id=2, file_name='other.pdf', file_path='other.pdf', invoice_number='HD-OTHER',
                    invoice_date=date(2026, 1, 15), seller_name='Other business',
                    total_amount=Decimal('888.00'), verification_status='confirmed'),
        ])
        db.commit()


def test_supplier_summary_uses_exact_backend_aggregates(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        result = execute_invoice_tool('get_supplier_summary', {'sort_by': 'amount', 'limit': 5}, db, 1, None, None)
    assert result['validation']['status'] == 'passed'
    assert result['suppliers'][0]['seller_name'] == 'Cong ty An Phat'
    assert result['suppliers'][0]['invoice_count'] == 2
    assert result['suppliers'][0]['total_amount'] == '300.00'
    assert result['suppliers'][0]['share_percent'] == '85.71'


def test_search_invoices_is_read_only_confirmed_only_and_respects_scope(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        result = execute_invoice_tool(
            'search_invoices',
            {'seller_name': 'An Phat', 'sort_by': 'amount_desc', 'limit': 10},
            db, 1, date(2026, 1, 1), date(2026, 1, 31),
        )
        outside_scope = execute_invoice_tool(
            'search_invoices',
            {'seller_name': 'Sao Viet', 'start_date': '2026-02-01', 'end_date': '2026-02-28'},
            db, 1, date(2026, 1, 1), date(2026, 1, 31),
        )
    assert result['matched_count'] == 2
    assert [row['invoice_number'] for row in result['invoices']] == ['HD-A-002', 'HD-A-001']
    assert outside_scope['matched_count'] == 0


def test_invoice_details_does_not_claim_line_items_exist(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        result = execute_invoice_tool('get_invoice_details', {'invoice_number': 'HD-A-001'}, db, 1, None, None)
    assert result['found'] is True
    assert result['invoices'][0]['total_amount'] == '100.00'
    assert result['line_items_available'] is False


def test_compare_periods_calculates_delta_with_decimal(client):
    _, sessions, _, _ = client
    seed(sessions)
    with sessions() as db:
        result = execute_invoice_tool('compare_periods', {
            'period_a_start': '2026-01-01', 'period_a_end': '2026-01-31',
            'period_b_start': '2026-02-01', 'period_b_end': '2026-02-28',
        }, db, 1, None, None)
    assert result['period_a']['invoice_count'] == 2
    assert result['period_a']['total_amount'] == '300.00'
    assert result['period_b']['total_amount'] == '50.00'
    assert result['difference_b_minus_a']['total_amount'] == '-250.00'
    assert result['difference_b_minus_a']['percent_change'] == '-83.33'
