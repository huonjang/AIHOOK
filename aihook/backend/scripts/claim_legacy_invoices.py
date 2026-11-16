"""Explicit offline data migration; never auto-assign demo invoices on registration.

Usage (after backup and signup):
  python -m scripts.claim_legacy_invoices --email owner@example.com --confirm
"""
import argparse
from sqlalchemy import func, select
from app.database import SessionLocal
from app.models import Business, Invoice, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--email', required=True)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    with SessionLocal() as db:
        source = db.get(Business, 1)
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if not user:
            raise SystemExit('Tài khoản đích không tồn tại; hãy đăng ký trước.')
        if not source or source.name != 'Doanh nghiệp demo':
            raise SystemExit('Business #1 không phải bản demo chuẩn; từ chối tự di chuyển.')
        if db.scalar(select(User).where(User.business_id == 1)):
            raise SystemExit('Business #1 đã có chủ; không thể chuyển dữ liệu.')
        count = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.business_id == 1)) or 0
        target_count = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.business_id == user.business_id)) or 0
        if target_count:
            raise SystemExit('Doanh nghiệp đích đã có hóa đơn; ngừng để tránh trộn dữ liệu.')
        print(f'Demo nguồn #1: {count} hóa đơn; doanh nghiệp đích #{user.business_id}: {args.email}.')
        if not args.confirm:
            print('CHƯA SỬA DỮ LIỆU. Sao lưu backend/aihook.db rồi chạy lại kèm --confirm.')
            return
        for invoice in db.scalars(select(Invoice).where(Invoice.business_id == 1)):
            invoice.business_id = user.business_id
        db.commit()
        print(f'Đã chuyển {count} hóa đơn. Trạng thái phân loại vẫn là unknown.')


if __name__ == '__main__':
    main()
