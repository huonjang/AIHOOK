"""TestClient dùng SQLite riêng, tuyệt đối không truy cập database thật."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.database import Base, get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(main, "UPLOAD_DIR", uploads)

    def override_db():
        with sessions() as db:
            yield db

    main.app.dependency_overrides[get_db] = override_db
    with TestClient(main.app) as test_client:
        from datetime import datetime, timedelta, timezone
        from fastapi import Response
        from http.cookies import SimpleCookie
        from app.models import User
        from app.security import COOKIE, create_login_session, hash_password
        with sessions() as db:
            user = User(business_id=1, email='fixture@example.com',
                        password_hash=hash_password('test-password-2026'), owner_name='Fixture Owner')
            db.add(user)
            db.commit()
            db.refresh(user)
            resp = Response()
            create_login_session(db, resp, user)
            parsed = SimpleCookie()
            parsed.load(resp.headers['set-cookie'])
            test_client.cookies.set(COOKIE, parsed[COOKIE].value, path='/api')
        yield test_client, sessions, uploads, monkeypatch
    main.app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def sample_png():
    image = Image.new("RGB", (80, 100), color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def ocr_text():
    return (
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
        "Số hóa đơn: HĐ-012\n"
        "Ngày 14 tháng 11 năm 2026\n"
        "Đơn vị bán hàng (Seller): Công Ty Cổ Phần Nguyễn Gia\n"
        "Mã số thuế: 0123456789\n"
        "Địa chỉ: Số 3 Đường Lê Lợi, Hà Nội\n"
        "Tổng tiền thanh toán: 1.200.000\n"
    )
