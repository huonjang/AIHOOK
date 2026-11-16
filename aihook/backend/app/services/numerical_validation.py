"""Deterministic consistency checks for invoice analytics results."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")


def _decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def validate_analytics(data: dict[str, Any]) -> dict[str, Any]:
    """Check that independently aggregated analytics reconcile.

    All comparisons use Decimal. The function reports discrepancies instead
    of silently changing or correcting values from the database.
    """
    overview = data.get("overview", {})
    monthly = data.get("monthly", [])
    suppliers = data.get("suppliers", [])

    invoice_count = int(overview.get("invoice_count", 0))
    total_amount = _decimal(overview.get("total_amount"))
    average_amount = _decimal(overview.get("average_amount"))
    undated_count = int(overview.get("undated_count", 0))
    undated_total = _decimal(overview.get("undated_total_amount"))

    monthly_count = sum(int(row.get("invoice_count", 0)) for row in monthly)
    monthly_total = sum((_decimal(row.get("total_amount")) for row in monthly), Decimal("0"))
    supplier_count = sum(int(row.get("invoice_count", 0)) for row in suppliers)
    supplier_group_count = len(suppliers)
    supplier_total = sum((_decimal(row.get("total_amount")) for row in suppliers), Decimal("0"))
    unidentified = data.get('unidentified_partners', {})
    supplier_count += unidentified.get('purchase', {}).get('invoice_count', 0)
    supplier_total += _decimal(unidentified.get('purchase', {}).get('total_amount'))
    purchase = data.get('flow_summary', {}).get('purchase', overview)
    purchase_count = int(purchase.get('invoice_count', 0))
    purchase_total = _decimal(purchase.get('total_amount'))
    expected_average = (
        (total_amount / invoice_count).quantize(CENT, rounding=ROUND_HALF_UP)
        if invoice_count
        else Decimal("0.00")
    )

    checks = [
        {
            "code": "monthly_count_reconciles",
            "label": "Số hóa đơn theo tháng cộng hóa đơn chưa có ngày khớp tổng",
            "passed": monthly_count + undated_count == invoice_count,
            "expected": str(invoice_count),
            "actual": str(monthly_count + undated_count),
        },
        {
            "code": "monthly_total_reconciles",
            "label": "Tổng tiền theo tháng cộng tiền hóa đơn chưa có ngày khớp tổng",
            "passed": monthly_total + undated_total == total_amount,
            "expected": format(total_amount, "f"),
            "actual": format(monthly_total + undated_total, "f"),
        },
        {
            "code": "supplier_count_reconciles",
            "label": "Tổng số hóa đơn theo nhà cung cấp khớp hóa đơn mua vào",
            "passed": supplier_count == purchase_count,
            "expected": str(purchase_count),
            "actual": str(supplier_count),
        },
        {
            "code": "supplier_groups_reconcile",
            "label": "Số nhóm nhà cung cấp khớp chỉ số tổng quan",
            "passed": supplier_group_count == int(overview.get("supplier_count", 0)),
            "expected": str(int(overview.get("supplier_count", 0))),
            "actual": str(supplier_group_count),
        },
        {
            "code": "supplier_total_reconciles",
            "label": "Tổng tiền theo nhà cung cấp khớp tổng mua vào",
            "passed": supplier_total == purchase_total,
            "expected": format(purchase_total, "f"),
            "actual": format(supplier_total, "f"),
        },
        {
            "code": "average_reconciles",
            "label": "Giá trị trung bình khớp tổng chia số hóa đơn",
            "passed": average_amount == expected_average,
            "expected": format(expected_average, "f"),
            "actual": format(average_amount, "f"),
        },
    ]

    if 'customers' in data:
        sale = data.get('flow_summary', {}).get('sale', {})
        for suffix, actual, expected, label in [
            ('count', sum(row['invoice_count'] for row in data['customers']) + unidentified.get('sale', {}).get('invoice_count', 0), sale.get('invoice_count', 0), 'Số hóa đơn khách hàng xác định và chưa xác định khớp hóa đơn bán ra'),
            ('total', sum((_decimal(row['total_amount']) for row in data['customers']), Decimal('0')) + _decimal(unidentified.get('sale', {}).get('total_amount')), _decimal(sale.get('total_amount')), 'Tổng tiền khách hàng xác định và chưa xác định khớp tổng bán ra'),
        ]:
            checks.append({'code': f'customer_{suffix}_reconciles', 'label': label,
                           'passed': actual == expected, 'expected': str(expected), 'actual': str(actual)})
    passed = all(check["passed"] for check in checks)
    return {
        "status": "passed" if passed else "warning",
        "passed_checks": sum(1 for check in checks if check["passed"]),
        "total_checks": len(checks),
        "checks": checks,
    }
