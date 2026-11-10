from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice


def get_invoice_summary(
    db: Session,
    business_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
):
    statement = select(
        func.count(Invoice.id),
        func.coalesce(
            func.sum(Invoice.total_amount),
            Decimal("0"),
        ),
    ).where(
        Invoice.business_id == business_id,
        Invoice.verification_status == "confirmed",
    )

    # Không truyền ngày: tính toàn bộ hóa đơn đã xác nhận.
    # Có truyền ngày: lọc theo ngày lập hóa đơn.
    if start_date is not None:
        statement = statement.where(
            Invoice.invoice_date >= start_date
        )

    if end_date is not None:
        statement = statement.where(
            Invoice.invoice_date <= end_date
        )

    count, total = db.execute(statement).one()

    return {
        "business_id": business_id,
        "start_date": (
            start_date.isoformat()
            if start_date is not None
            else None
        ),
        "end_date": (
            end_date.isoformat()
            if end_date is not None
            else None
        ),
        "invoice_count": count,
        "total_amount": str(total),
        "currency": "VND",
    }
