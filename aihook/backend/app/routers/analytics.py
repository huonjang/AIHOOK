from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.security import current_business_id
from app.database import get_db
from app.models import Business
from app.services.analytics_service import get_analytics

router = APIRouter(prefix='/api/analytics', tags=['Analytics'])


def analytics_data(
    business_id: int | None = Query(default=None, ge=1),
    active_business_id: int = Depends(current_business_id),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    if (start_date is None) != (end_date is None):
        raise HTTPException(400, 'Vui lòng truyền cả ngày bắt đầu và ngày kết thúc.')
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
    if business_id is not None and business_id != active_business_id:
        raise HTTPException(403, 'Không được truy cập dữ liệu doanh nghiệp khác.')
    if db.get(Business, active_business_id) is None:
        raise HTTPException(404, 'Không tìm thấy doanh nghiệp.')
    return get_analytics(db, active_business_id, start_date, end_date)


@router.get('/dashboard')
def dashboard(data: dict = Depends(analytics_data)):
    return data


@router.get('/overview')
def overview(data: dict = Depends(analytics_data)):
    return data['overview']


@router.get('/monthly')
def monthly(data: dict = Depends(analytics_data)):
    return data['monthly']


@router.get('/suppliers')
def suppliers(data: dict = Depends(analytics_data)):
    return data['suppliers']


@router.get('/customers')
def customers(data: dict = Depends(analytics_data)):
    return data['customers']
