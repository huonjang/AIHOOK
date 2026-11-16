"""Read-only analytics, using confirmed invoice values and invoice dates."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Invoice


def money(value):
    return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')


def get_analytics(db: Session, business_id: int, start: date | None, end: date | None):
    query = select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.verification_status == 'confirmed',
    ).order_by(Invoice.invoice_date, Invoice.id)
    if start:
        query = query.where(Invoice.invoice_date >= start)
    if end:
        query = query.where(Invoice.invoice_date <= end)
    invoices = db.scalars(query).all()
    total = Decimal('0')
    flow_types = ('purchase', 'sale', 'unknown')
    flows = {name: {'count': 0, 'amount': Decimal('0')} for name in flow_types}
    flows_by_month = {}
    monthly = {}
    suppliers = {}
    customers = {}
    undated_count = 0
    undated_total = Decimal('0')
    for invoice in invoices:
        value = invoice.total_amount or Decimal('0')
        total += value
        flow_type = invoice.flow_type if invoice.flow_type in flow_types else 'unknown'
        flows[flow_type]['count'] += 1
        flows[flow_type]['amount'] += value
        if invoice.invoice_date:
            month = invoice.invoice_date.isoformat()[:7]
            item = monthly.setdefault(month, {'count': 0, 'amount': Decimal('0')})
            item['count'] += 1
            item['amount'] += value
            month_flows = flows_by_month.setdefault(month, {key: Decimal('0') for key in flow_types})
            month_flows[flow_type] += value
        else:
            undated_count += 1
            undated_total += value
        if flow_type == 'unknown':
            continue
        is_purchase = flow_type == 'purchase'
        name = ' '.join(((invoice.seller_name if is_purchase else invoice.buyer_name) or '').split()) or 'Chưa rõ đối tác'
        tax = ((invoice.seller_tax_code if is_purchase else invoice.buyer_tax_code) or '').strip() or None
        key = ('tax', tax) if tax else ('name', name.casefold())
        groups = suppliers if is_purchase else customers
        supplier = groups.setdefault(key, {'name': name, 'tax_code': tax, 'count': 0, 'amount': Decimal('0')})
        supplier['count'] += 1
        supplier['amount'] += value
    # Include zero months within the selected range (or first/last data month).
    first = start.isoformat()[:7] if start else min(monthly, default=None)
    last = end.isoformat()[:7] if end else max(monthly, default=None)
    if first and last:
        first_year, first_month = map(int, first.split('-'))
        last_year, last_month = map(int, last.split('-'))
        for index in range(first_year * 12 + first_month - 1, last_year * 12 + last_month):
            year, month_index = divmod(index, 12)
            monthly.setdefault(f'{year:04d}-{month_index + 1:02d}', {'count': 0, 'amount': Decimal('0')})
    ranked = sorted(suppliers.values(), key=lambda s: (-s['amount'], s['name'], s['tax_code'] or ''))
    ranked_customers = sorted(customers.values(), key=lambda s: (-s['amount'], s['name'], s['tax_code'] or ''))
    return {
        'business_id': business_id, 'start_date': start, 'end_date': end, 'currency': 'VND',
        'overview': {'invoice_count': len(invoices), 'total_amount': money(total),
                     'average_amount': money(total / len(invoices)) if invoices else '0.00',
                     'supplier_count': len(suppliers), 'undated_count': undated_count,
                     'undated_total_amount': money(undated_total)},
        'monthly': [{'month': month, 'invoice_count': item['count'], 'total_amount': money(item['amount'])}
                    for month, item in sorted(monthly.items())],
        'suppliers': [{'seller_name': s['name'], 'seller_tax_code': s['tax_code'],
                       'invoice_count': s['count'], 'total_amount': money(s['amount'])} for s in ranked],
        'customers': [{'buyer_name': s['name'], 'buyer_tax_code': s['tax_code'],
                       'invoice_count': s['count'], 'total_amount': money(s['amount'])} for s in ranked_customers],
        'flow_summary': {name: {'invoice_count': item['count'], 'total_amount': money(item['amount'])}
                         for name, item in flows.items()},
        'flow_monthly': [{'month': month, **{name + '_amount': money(flows_by_month.get(month, {}).get(name, Decimal('0')))
                                                for name in flow_types}}
                         for month in sorted(monthly)],
    }
