"""Allowlisted, read-only invoice tools exposed to the AI model.

The model can request these functions, but every database query is authored
and executed by the backend. No model-generated SQL is ever executed.
"""
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Invoice
from app.services.analytics_service import get_analytics
from app.services.numerical_validation import validate_analytics


logger = logging.getLogger(__name__)
MAX_INVOICE_RESULTS = 50
CENT = Decimal("0.01")


def _money(value: Any) -> str:
    return format(Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP), "f")


def _percentage(numerator: Decimal, denominator: Decimal) -> str:
    if denominator == 0:
        return "0.00"
    return format((numerator / denominator * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP), "f")


class RangeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
        return self


class SupplierArgs(RangeArgs):
    sort_by: Literal["amount", "count"] = "amount"
    limit: int = Field(default=10, ge=1, le=30)


class SearchInvoicesArgs(RangeArgs):
    invoice_number: str | None = Field(default=None, max_length=100)
    seller_name: str | None = Field(default=None, max_length=255)
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    sort_by: Literal["amount_desc", "amount_asc", "date_desc", "date_asc"] = "amount_desc"
    limit: int = Field(default=10, ge=1, le=MAX_INVOICE_RESULTS)

    @model_validator(mode="after")
    def validate_amount_range(self):
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("Giá trị tối thiểu không được lớn hơn giá trị tối đa.")
        return self


class InvoiceDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_id: int | None = Field(default=None, ge=1)
    invoice_number: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_identifier(self):
        if self.invoice_id is None and not self.invoice_number:
            raise ValueError("Cần cung cấp invoice_id hoặc invoice_number.")
        return self


class ComparePeriodsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_a_start: date
    period_a_end: date
    period_b_start: date
    period_b_end: date

    @model_validator(mode="after")
    def validate_periods(self):
        if self.period_a_start > self.period_a_end:
            raise ValueError("Khoảng thời gian A không hợp lệ.")
        if self.period_b_start > self.period_b_end:
            raise ValueError("Khoảng thời gian B không hợp lệ.")
        return self


_DATE_RANGE_PROPERTIES = {
    "start_date": {"type": "string", "format": "date", "description": "Ngày bắt đầu YYYY-MM-DD; phải nằm trong bộ lọc đang chọn nếu bộ lọc có giới hạn."},
    "end_date": {"type": "string", "format": "date", "description": "Ngày kết thúc YYYY-MM-DD; phải nằm trong bộ lọc đang chọn nếu bộ lọc có giới hạn."},
}


def _object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


INVOICE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_invoice_overview",
            "description": "Lấy số lượng hóa đơn đã xác nhận, tổng giá trị, trung bình, số nhà cung cấp và kiểm tra đối chiếu số liệu trong phạm vi ngày.",
            "parameters": _object_schema(dict(_DATE_RANGE_PROPERTIES)),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_summary",
            "description": "Lấy số lượng và tổng giá trị hóa đơn theo từng tháng. Dùng khi câu hỏi hỏi xu hướng hoặc tháng cao/thấp nhất.",
            "parameters": _object_schema(dict(_DATE_RANGE_PROPERTIES)),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_supplier_summary",
            "description": "Xếp hạng nhà cung cấp theo tổng giá trị hoặc số lượng hóa đơn, đồng thời tính tỷ trọng bằng backend.",
            "parameters": _object_schema({
                **_DATE_RANGE_PROPERTIES,
                "sort_by": {"type": "string", "enum": ["amount", "count"], "description": "amount: tổng giá trị; count: số hóa đơn."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 30},
            }),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_invoices",
            "description": "Tìm hóa đơn đã xác nhận theo mã hóa đơn, nhà cung cấp, khoảng tiền hoặc ngày. Trả về tối đa 50 hóa đơn và ID để đối chiếu.",
            "parameters": _object_schema({
                **_DATE_RANGE_PROPERTIES,
                "invoice_number": {"type": "string", "description": "Một phần hoặc toàn bộ mã hóa đơn."},
                "seller_name": {"type": "string", "description": "Một phần hoặc toàn bộ tên nhà cung cấp."},
                "min_amount": {"type": "number", "minimum": 0},
                "max_amount": {"type": "number", "minimum": 0},
                "sort_by": {"type": "string", "enum": ["amount_desc", "amount_asc", "date_desc", "date_asc"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_INVOICE_RESULTS},
            }),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoice_details",
            "description": "Lấy trường dữ liệu đã xác nhận của một hóa đơn theo ID hoặc mã hóa đơn. Hệ thống hiện không lưu dòng sản phẩm chi tiết.",
            "parameters": _object_schema({
                "invoice_id": {"type": "integer", "minimum": 1},
                "invoice_number": {"type": "string"},
            }),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_periods",
            "description": "So sánh số hóa đơn, tổng giá trị, trung bình và mức chênh lệch giữa hai khoảng ngày. Các phép tính do backend thực hiện.",
            "parameters": _object_schema({
                "period_a_start": {"type": "string", "format": "date"},
                "period_a_end": {"type": "string", "format": "date"},
                "period_b_start": {"type": "string", "format": "date"},
                "period_b_end": {"type": "string", "format": "date"},
            }, ["period_a_start", "period_a_end", "period_b_start", "period_b_end"]),
        },
    },
]


def _intersect_range(
    requested_start: date | None,
    requested_end: date | None,
    scope_start: date | None,
    scope_end: date | None,
) -> tuple[date | None, date | None]:
    starts = [value for value in (requested_start, scope_start) if value is not None]
    ends = [value for value in (requested_end, scope_end) if value is not None]
    return (max(starts) if starts else None, min(ends) if ends else None)


def _analytics_in_scope(
    db: Session,
    business_id: int,
    requested_start: date | None,
    requested_end: date | None,
    scope_start: date | None,
    scope_end: date | None,
) -> dict[str, Any]:
    start, end = _intersect_range(requested_start, requested_end, scope_start, scope_end)
    return get_analytics(db, business_id, start, end)


def _optional_money(value: Any) -> str | None:
    return _money(value) if value is not None else None


def _invoice_dict(invoice: Invoice) -> dict[str, Any]:
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "seller_name": invoice.seller_name,
        "seller_tax_code": invoice.seller_tax_code,
        "buyer_name": invoice.buyer_name,
        "subtotal": _optional_money(invoice.subtotal),
        "tax_amount": _optional_money(invoice.tax_amount),
        "total_amount": _optional_money(invoice.total_amount),
        "source_page": invoice.source_page,
        "line_items_available": False,
    }


def _base_query(business_id: int):
    return select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.verification_status == "confirmed",
    )


def _apply_date_scope(query, start: date | None, end: date | None):
    if start is not None:
        query = query.where(Invoice.invoice_date >= start)
    if end is not None:
        query = query.where(Invoice.invoice_date <= end)
    return query


def _period_summary(db: Session, business_id: int, start: date, end: date) -> dict[str, Any]:
    analytics = get_analytics(db, business_id, start, end)
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        **analytics["overview"],
        "validation": validate_analytics(analytics),
    }


def execute_invoice_tool(
    name: str,
    arguments: dict[str, Any],
    db: Session,
    business_id: int,
    scope_start: date | None,
    scope_end: date | None,
) -> dict[str, Any]:
    """Validate and execute one allowlisted read-only tool call."""
    if not isinstance(arguments, dict):
        return {"error": "Tham số công cụ phải là một object JSON."}

    try:
        if name == "get_invoice_overview":
            args = RangeArgs.model_validate(arguments)
            data = _analytics_in_scope(db, business_id, args.start_date, args.end_date, scope_start, scope_end)
            return {"overview": data["overview"], "validation": validate_analytics(data)}

        if name == "get_monthly_summary":
            args = RangeArgs.model_validate(arguments)
            data = _analytics_in_scope(db, business_id, args.start_date, args.end_date, scope_start, scope_end)
            return {
                "overview": data["overview"],
                "monthly": data["monthly"][-120:],
                "monthly_truncated": len(data["monthly"]) > 120,
                "validation": validate_analytics(data),
            }

        if name == "get_supplier_summary":
            args = SupplierArgs.model_validate(arguments)
            data = _analytics_in_scope(db, business_id, args.start_date, args.end_date, scope_start, scope_end)
            suppliers = list(data["suppliers"])
            if args.sort_by == "count":
                suppliers.sort(key=lambda row: (-row["invoice_count"], -Decimal(row["total_amount"]), row["seller_name"]))
            total = Decimal(data["overview"]["total_amount"])
            for row in suppliers:
                row["share_percent"] = _percentage(Decimal(row["total_amount"]), total)
            return {
                "total_amount": data["overview"]["total_amount"],
                "sort_by": args.sort_by,
                "suppliers": suppliers[:args.limit],
                "validation": validate_analytics(data),
            }

        if name == "search_invoices":
            args = SearchInvoicesArgs.model_validate(arguments)
            start, end = _intersect_range(args.start_date, args.end_date, scope_start, scope_end)
            filters = [Invoice.business_id == business_id, Invoice.verification_status == "confirmed"]
            query = _base_query(business_id)
            if start is not None:
                filters.append(Invoice.invoice_date >= start)
                query = query.where(Invoice.invoice_date >= start)
            if end is not None:
                filters.append(Invoice.invoice_date <= end)
                query = query.where(Invoice.invoice_date <= end)
            if args.invoice_number and args.invoice_number.strip():
                escaped = args.invoice_number.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                filters.append(Invoice.invoice_number.ilike(pattern, escape="\\"))
                query = query.where(Invoice.invoice_number.ilike(pattern, escape="\\"))
            if args.seller_name and args.seller_name.strip():
                escaped = args.seller_name.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                filters.append(Invoice.seller_name.ilike(pattern, escape="\\"))
                query = query.where(Invoice.seller_name.ilike(pattern, escape="\\"))
            if args.min_amount is not None:
                filters.append(Invoice.total_amount >= args.min_amount)
                query = query.where(Invoice.total_amount >= args.min_amount)
            if args.max_amount is not None:
                filters.append(Invoice.total_amount <= args.max_amount)
                query = query.where(Invoice.total_amount <= args.max_amount)

            if args.sort_by == "amount_asc":
                ordering = [Invoice.total_amount.asc(), Invoice.id.asc()]
            elif args.sort_by == "date_desc":
                ordering = [Invoice.invoice_date.desc(), Invoice.id.desc()]
            elif args.sort_by == "date_asc":
                ordering = [Invoice.invoice_date.asc(), Invoice.id.asc()]
            else:
                ordering = [Invoice.total_amount.desc(), Invoice.id.asc()]

            matched_count = db.scalar(select(func.count(Invoice.id)).where(*filters)) or 0
            rows = db.scalars(query.order_by(*ordering).limit(args.limit)).all()
            return {
                "matched_count": matched_count,
                "returned_count": len(rows),
                "invoices": [_invoice_dict(row) for row in rows],
            }

        if name == "get_invoice_details":
            args = InvoiceDetailsArgs.model_validate(arguments)
            query = _base_query(business_id)
            if args.invoice_id is not None:
                query = query.where(Invoice.id == args.invoice_id)
            else:
                query = query.where(Invoice.invoice_number.ilike(args.invoice_number.strip()))
            query = _apply_date_scope(query, scope_start, scope_end)
            rows = db.scalars(query.order_by(Invoice.id.desc()).limit(5)).all()
            return {
                "found": bool(rows),
                "match_count": len(rows),
                "invoices": [_invoice_dict(row) for row in rows],
                "line_items_available": False,
                "limitation": "Database hiện lưu thông tin tổng hợp hóa đơn, chưa có bảng dòng sản phẩm/số lượng/đơn giá.",
            }

        if name == "compare_periods":
            args = ComparePeriodsArgs.model_validate(arguments)
            a_start, a_end = _intersect_range(args.period_a_start, args.period_a_end, scope_start, scope_end)
            b_start, b_end = _intersect_range(args.period_b_start, args.period_b_end, scope_start, scope_end)
            if a_start is None or a_end is None or b_start is None or b_end is None:
                return {"error": "Không xác định được phạm vi so sánh trong bộ lọc hiện tại."}
            if a_start > a_end or b_start > b_end:
                return {"error": "Một hoặc cả hai giai đoạn không giao với bộ lọc ngày hiện tại."}
            period_a = _period_summary(db, business_id, a_start, a_end)
            period_b = _period_summary(db, business_id, b_start, b_end)
            amount_a = Decimal(period_a["total_amount"])
            amount_b = Decimal(period_b["total_amount"])
            count_delta = int(period_b["invoice_count"]) - int(period_a["invoice_count"])
            amount_delta = amount_b - amount_a
            percent_delta = None if amount_a == 0 else _percentage(amount_delta, amount_a)
            return {
                "period_a": period_a,
                "period_b": period_b,
                "difference_b_minus_a": {
                    "invoice_count": count_delta,
                    "total_amount": _money(amount_delta),
                    "percent_change": percent_delta,
                },
            }

        return {"error": "Công cụ không nằm trong danh sách được cho phép."}

    except ValidationError as exc:
        return {
            "error": "Tham số truy vấn không hợp lệ.",
            "details": [item["msg"] for item in exc.errors(include_url=False)],
        }
    except Exception:
        # Do not return database paths, SQL, or driver details to the model/user.
        logger.exception("Invoice AI tool execution failed: %s", name)
        return {"error": "Không thể hoàn tất truy vấn dữ liệu hóa đơn."}
