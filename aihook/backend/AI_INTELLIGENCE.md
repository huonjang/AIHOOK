# Invoice intelligence

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
  UI date filter. Unresolved temporal or open questions use the model tool path.
- Identical tool names and canonical JSON arguments are deduplicated before
  execution. Distinct filters remain distinct queries.
- Analytics validation reconciles suppliers against purchase totals and customers
  against sale totals, while monthly reconciliation covers all directions.

No model-generated SQL is executed. Amounts and differences use Decimal.
Tests in `tests/test_invoice_intelligence.py` cover intent routing without a model,
role separation, tenant isolation, scopes, date ties, empty data, recommendation
counts, window overlap, deduplication, and read-only behavior.
