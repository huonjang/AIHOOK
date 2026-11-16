from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.security import current_business_id
from app.database import get_db
from app.models import Business
from app.services.invoice_queries import get_invoice_summary

router = APIRouter(
    prefix="/api/ai-data",
    tags=["AI Data Tools"],
)



@router.get("/summary")
def invoice_summary_endpoint(
    business_id: int | None = Query(default=None, ge=1),
    active_business_id: int = Depends(current_business_id),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    # Chỉ cho phép truyền cả hai ngày hoặc không truyền ngày nào.
    if (start_date is None) != (end_date is None):
        raise HTTPException(
            status_code=400,
            detail="start_date and end_date must be provided together",
        )

    if (
        start_date is not None
        and end_date is not None
        and start_date > end_date
    ):
        raise HTTPException(
            status_code=400,
            detail="start_date must be on or before end_date",
        )

    if business_id is not None and business_id != active_business_id:
        raise HTTPException(403, 'Không được truy cập dữ liệu doanh nghiệp khác.')
    business = db.scalar(
        select(Business).where(Business.id == active_business_id)
    )

    if business is None:
        raise HTTPException(
            status_code=404,
            detail="Business not found",
        )

    result = get_invoice_summary(
        db=db,
        business_id=active_business_id,
        start_date=start_date,
        end_date=end_date,
    )

    result["business_name"] = business.name
    return result
