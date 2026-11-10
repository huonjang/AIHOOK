from app.services.numerical_validation import validate_analytics


def valid_analytics():
    return {
        'overview': {
            'invoice_count': 3,
            'total_amount': '350.30',
            'average_amount': '116.77',
            'supplier_count': 2,
            'undated_count': 1,
            'undated_total_amount': '10.00',
        },
        'monthly': [
            {'month': '2026-01', 'invoice_count': 2, 'total_amount': '340.30'},
        ],
        'suppliers': [
            {'seller_name': 'A', 'invoice_count': 2, 'total_amount': '300.30'},
            {'seller_name': 'B', 'invoice_count': 1, 'total_amount': '50.00'},
        ],
    }


def test_numerical_validation_passes_with_undated_invoices():
    result = validate_analytics(valid_analytics())
    assert result['status'] == 'passed'
    assert result['passed_checks'] == result['total_checks'] == 6


def test_numerical_validation_detects_monthly_total_mismatch():
    data = valid_analytics()
    data['monthly'][0]['total_amount'] = '330.30'
    result = validate_analytics(data)
    assert result['status'] == 'warning'
    failed = {item['code'] for item in result['checks'] if not item['passed']}
    assert 'monthly_total_reconciles' in failed
