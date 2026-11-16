"""Read-only analytics, using confirmed invoice values and invoice dates."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Invoice
from app.services.partner_identity import partner_identity


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
    flow_counts_by_month = {}
    monthly = {}
    suppliers = {}
    customers = {}
    unidentified = {role: {'count': 0, 'amount': Decimal('0')} for role in ('purchase', 'sale')}
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
            month_counts = flow_counts_by_month.setdefault(month, {key: 0 for key in flow_types})
            month_counts[flow_type] += 1
        else:
            undated_count += 1
            undated_total += value
        if flow_type == 'unknown':
            continue
        is_purchase = flow_type == 'purchase'
        identity = partner_identity(invoice)
        if identity is None:
            unidentified[flow_type]['count'] += 1
            unidentified[flow_type]['amount'] += value
            continue
        key, name, tax = identity
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
        'unidentified_partners': {role: {'invoice_count': item['count'], 'total_amount': money(item['amount'])}
                                  for role, item in unidentified.items()},
        'flow_summary': {name: {'invoice_count': item['count'], 'total_amount': money(item['amount'])}
                         for name, item in flows.items()},
        'flow_monthly': [{'month': month, **{name + '_amount': money(flows_by_month.get(month, {}).get(name, Decimal('0')))
                                                for name in flow_types},
                         **{name + '_count': flow_counts_by_month.get(month, {}).get(name, 0) for name in flow_types}}
                         for month in sorted(monthly)],
    }
