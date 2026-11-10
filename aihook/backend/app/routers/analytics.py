from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Business
from app.services.analytics_service import get_analytics

router = APIRouter(prefix='/api/analytics', tags=['Analytics'])


def analytics_data(
    business_id: int = Query(default=1, ge=1),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    if (start_date is None) != (end_date is None):
        raise HTTPException(400, 'Vui lòng truyền cả ngày bắt đầu và ngày kết thúc.')
    if start_date and end_date and start_date > end_date:
        raise HTTPException(400, 'Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
    if db.get(Business, business_id) is None:
        raise HTTPException(404, 'Không tìm thấy doanh nghiệp.')
    return get_analytics(db, business_id, start_date, end_date)


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
