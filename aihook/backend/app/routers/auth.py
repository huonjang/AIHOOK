"""Owner signup/login and minimal profile (one owner = one business for MVP)."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Business, User
from app.security import (_allowed_origin, clear_login_session, create_login_session,
                          current_user, hash_password, verify_password)

router = APIRouter(prefix='/api/auth', tags=['Account'])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    owner_name: str = Field(min_length=2, max_length=150)
    business_name: str = Field(min_length=2, max_length=255)
    tax_code: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value):
            raise ValueError('Email không hợp lệ.')
        return value

    @field_validator('owner_name', 'business_name')
    @classmethod
    def name_nonempty(cls, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Thông tin tên không hợp lệ.')
        return value

    @field_validator('tax_code', 'phone')
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class LoginRequest(BaseModel):
    email: str
    password: str


def _profile(user: User, db: Session) -> dict:
    business = db.get(Business, user.business_id)
    if business is None:
        raise HTTPException(500, 'Không tìm thấy doanh nghiệp liên kết.')
    return {'id': user.id, 'email': user.email, 'owner_name': user.owner_name,
            'phone': user.phone, 'business': {'id': business.id, 'name': business.name, 'tax_code': business.tax_code}}


@router.post('/register', status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _allowed_origin(request)
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, 'Email đã được sử dụng.')
    try:
        business = Business(name=payload.business_name, tax_code=payload.tax_code)
        db.add(business)
        db.flush()
        user = User(business_id=business.id, email=payload.email,
                    password_hash=hash_password(payload.password),
                    owner_name=payload.owner_name, phone=payload.phone)
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Email đã được sử dụng.') from exc
    create_login_session(db, response, user)
    return _profile(user, db)


@router.post('/login')
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _allowed_origin(request)
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, 'Thông tin đăng nhập không đúng.')
    create_login_session(db, response, user)
    return _profile(user, db)


@router.post('/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    _allowed_origin(request)
    clear_login_session(db, request, response)
    return {'message': 'Đã đăng xuất.'}


@router.get('/me')
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _profile(user, db)


class ProfileUpdate(BaseModel):
    business_name: str = Field(min_length=2, max_length=255)
    owner_name: str = Field(min_length=2, max_length=150)
    tax_code: str | None = Field(default=None, max_length=30)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator('business_name', 'owner_name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Tên quá ngắn.')
        return value

    @field_validator('tax_code', 'phone')
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


@router.patch('/me')
def update_profile(payload: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    business = db.get(Business, user.business_id)
    if business is None:
        raise HTTPException(404, 'Không tìm thấy doanh nghiệp.')
    business.name = payload.business_name
    business.tax_code = payload.tax_code
    user.owner_name = payload.owner_name
    user.phone = payload.phone
    db.commit()
    return _profile(user, db)
