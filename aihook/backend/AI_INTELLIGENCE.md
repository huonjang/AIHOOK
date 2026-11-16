# Invoice intelligence

## Engine 2.0

`services/intelligence_engine.py` routes structured intents before the model path:
ranking, role-specific averages/monthly data, period comparison, extremes, top
invoices, missing-field measurement, suspected duplicates, anomalies, OCR
procedure, recommendations, executive reports, bounded advice and clarification.
The model's unsupported prose is never appended to database findings.

Partner keys are shared through `partner_identity.py`. Missing names and tax IDs
do not form a single artificial customer/supplier. `unidentified_partners` retains
their invoice counts and value, and numerical reconciliation includes these
amounts separately. Concentration uses the entire corresponding flow total;
unknown identity does not disappear from the denominator. Ranking results expose
both top lists and their intersection, computed using identity keys in Python.

The frontend sends only a validated context object (topic, role, criterion, Top N,
query dates and UI scope). Queries always reapply authenticated business ownership.
Changing scope or clearing chat resets context. No raw chat history, invoice data,
or model instructions are accepted as context authority.

Every deterministic result has separate `assurance.intent`, `assurance.data`,
`assurance.numerical` and `assurance.verified` fields. A correct empty sum cannot
turn an unassessed intent or insufficient anomaly sample into a verified answer.
Evidence tables are expanded by default and are labelled query data rather than
unconditionally verified data.

Anomalies use a documented conservative median/MAD rule within each partner and
direction, with at least five invoices. Sparse/unidentified groups are reported
as unassessed. Duplicate matches are **suspected**, never confirmed merely from
equal fields. OCR correctness, payment, profitability, product-level price quality,
and completeness of a calendar period are not established by these queries.

Calendar parsing uses UTC+7 and supports explicit month/year, ISO date ranges,
quarters, years, current/previous month and month ranges. Unresolved temporal
constraints on recognized questions trigger clarification rather than all-time
queries. Earliest/latest data windows report overlap.

`tests/intelligence_prompts.py` freezes the 26 verbatim turns supplied by the user
(the evaluation described them as 25, but its transcript includes 26). Regression
tests use independent expected intents, deliberate missing identities, tenant
isolation, known arithmetic, actual anomaly baselines, suspected duplicate groups,
and context/scope resets. Older tests remain; assertions about a second model
synthesis call, tool names, or table counts were updated where the behavior was
intentionally replaced. This fixture is not a claim of general natural-language
accuracy outside these cases.

Run from `backend`: `python -m pytest tests -q`.

## Existing query foundation

`services/invoice_intelligence.py` separates intent recognition, scoped data queries,
and grounded response formatting. `routers/chat.py` dispatches clear intents before
calling a model. Open questions retain the allowlisted model tool path.

- Supplier rankings use confirmed **purchase** invoices and group sellers by tax
  code, falling back to normalized name. Customer rankings use confirmed **sale**
  invoices and buyer information. Unknown direction is excluded and reported.
- Each ranking query produces both value and count rankings (Top 5 by default),
  with concentration calculated against the corresponding role's total.
- Date extremes use invoice issue date, exclude undated records, and break ties
  using the smallest invoice ID. A single-extreme question returns one column;
  a comparison returns both and the day difference.
- Recommendations return only the requested numbered items with data-based
  reasons. Supported counts are 1–10; this limit is validated, never silently
  truncated. No additional overview or evidence table is appended.
- Explicit month comparisons are routed directly. Earliest/latest month windows
  use actual data boundaries, include zero-activity months between boundaries,
  and report overlapping periods. Stored invoices do not establish complete
  coverage of a calendar period or business performance.
- All queries retain authenticated business scope, confirmed status, and the
  UI date filter. Engine 2.0 asks for clarification on unresolved dates for
  structured questions; other open questions retain the unverified model tool path.
- Identical tool names and canonical JSON arguments are deduplicated before
  execution. Distinct filters remain distinct queries.
- Analytics validation reconciles suppliers against purchase totals and customers
  against sale totals, while monthly reconciliation covers all directions.

No model-generated SQL is executed. Amounts and differences use Decimal.
Tests in `tests/test_invoice_intelligence.py` cover intent routing without a model,
role separation, tenant isolation, scopes, date ties, empty data, recommendation
counts, window overlap, deduplication, and read-only behavior.
