# Shipping Box Recommendation System

A Django + DRF service that recommends the most suitable (cheapest viable)
shipping box for a customer order, given a catalog of products (dimensions +
weight) and boxes (internal dimensions, max weight, cost).

---

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser  # optional, for /admin/
python manage.py runserver
```

Run the test suite:

```bash
python manage.py test tests -v 2
```

38 tests covering model validation, service-level happy paths, 19 documented
edge cases, and API-level request/response contracts.

---

## 2. Project Structure

```
config/            # Django project settings/urls
common/            # DRY shared code: TimeStampedModel, validators,
                    # custom exceptions, global DRF exception handler
products/          # Product model (dimensions, weight), serializer, admin, CRUD API
boxes/             # Box model (internal dims, max weight, cost), serializer, admin, CRUD API
orders/            # Order / OrderItem models (persisted order history), CRUD API
recommendation/    # The core engine — no ORM coupling in the logic itself
    dto.py         #   Dimensions value object, OrderLine, BoxCandidate,
                    #   SingleBoxRecommendation, MultiBoxRecommendation
    strategies.py  #   Pluggable fit/weight/volume/confidence checks
    services.py    #   BoxRecommendationService — single place all
                    #   "can this be boxed, and how" logic lives
    serializers.py #   Request validation for the recommend-box endpoint
    views.py       #   Thin API view — parses request, builds DTOs, calls
                    #   the service, shapes the response. No business logic here.
tests/
    factories.py                  # factory_boy fixtures
    test_models.py                # model-level validation
    test_services_happy_path.py   # single-box selection, rotation, tie-breaking
    test_services_edge_cases.py   # the 14 originally-identified edge cases
    test_services_multibox.py     # multi-box splitting scenarios
    test_api.py                   # full request/response contract, incl. error shapes
```

### Where DRY is applied
- `TimeStampedModel` — one abstract base for `created_at`/`updated_at`, inherited by every model instead of repeated per-model.
- `common/validators.py` — one `validate_positive_nonzero` function used by every dimension/weight/cost field on both `Product` and `Box`.
- All "does this fit" logic lives in exactly one place: `recommendation/services.py` + `strategies.py`. Views, serializers, and models never re-implement any part of the fitting/costing logic.
- `Dimensions.fits_in()` (in `dto.py`) is the single method used everywhere a rotation-aware dimension comparison is needed — never re-derived per feature.

---

## 3. API Contract

### `POST /api/recommend-box/`

**Request**
```json
{
  "items": [
    {"product_id": 1, "quantity": 3},
    {"product_id": 2, "quantity": 1}
  ]
}
```
Duplicate `product_id`s in the same request are aggregated (summed), not treated as separate lines.

**Response — single box (200)**
```json
{
  "recommendation_type": "single_box",
  "box": {"id": 4, "name": "Medium", "cost": "25.00"},
  "confidence": "comfortable",
  "total_weight": "4.200",
  "total_volume": "1200.000000"
}
```
`confidence` is `"tight"` when the order uses more than `TIGHT_FIT_THRESHOLD` (default 75%) of the box's usable volume — still a valid recommendation, but a signal to the warehouse team to double-check by hand.

**Response — multi box (200)**
```json
{
  "recommendation_type": "multi_box",
  "box": {"id": 2, "name": "Small", "cost": "10.00"},
  "quantity": 3,
  "total_cost": "30.00",
  "reason": "No single box can hold the full order; recommending multiple units of the cheapest viable box type."
}
```
Returned when no single box can hold the whole order but splitting the order across multiple units of one box type can (e.g. a bulk order of one small item). Only same-box-type splits are considered in v1 (see Limitations).

**Response — failure (400 / 422)**
```json
{"error": "NO_BOXES_AVAILABLE", "message": "No boxes are available in the catalog."}
{"error": "ITEM_TOO_LARGE", "message": "Product 'XL Monitor' (id=7) exceeds all box dimensions in every rotation.", "detail": {"product_id": 7}}
{"error": "INVALID_PRODUCT", "message": "Unknown product_id(s): [999]", "detail": {"missing_product_ids": [999]}}
```
- `400` for malformed input (missing/non-numeric fields, empty item list, unknown or inactive product).
- `422` for a well-formed order that genuinely cannot be boxed (`NO_BOXES_AVAILABLE` / `ITEM_TOO_LARGE`).

### CRUD endpoints
`GET/POST/PUT/PATCH/DELETE` on `/api/products/`, `/api/boxes/`, `/api/orders/` — standard DRF `ModelViewSet`s for catalog and order management, backing the admin/warehouse tooling.

---

## 4. Algorithm

1. **Aggregate the order** — total weight, total volume across all lines (Decimal throughout — never float, to avoid precision drift on large quantities).
2. **Per-item fit check (hard constraint)** — for each order line, check whether that product fits inside a candidate box in *some* axis-aligned rotation. Implemented by sorting both dimension triples ascending and comparing element-wise — mathematically equivalent to checking all 6 rotations for a single item in a single box.
3. **Single-box candidacy** — a box qualifies if every line fits individually, total weight ≤ box max weight, and total volume ≤ box internal volume × `PACKING_EFFICIENCY_FACTOR` (default 0.85 — see Assumptions). Among qualifying boxes, pick lowest cost; ties broken by smallest internal volume, then smallest box ID (deterministic).
4. **Multi-box fallback** — if no single box qualifies, for each box type where every line individually fits, compute `boxes_needed = max(ceil(total_weight / box.max_weight), ceil(total_volume / usable_volume))`, cost = `boxes_needed × box.cost`. Pick the cheapest option across box types.
5. **Definitive failure** — if neither works, distinguish `ITEM_TOO_LARGE` (some single unit can never fit any box, in any rotation) from `NO_BOXES_AVAILABLE` (every item fits somewhere individually, but no single box type accommodates all lines together).

---

## 5. Documented Assumptions & Limitations

- **Not a geometric 3D bin-packer.** True multi-item 3D packing is NP-hard and out of scope. This is a deliberate, documented heuristic: per-item rotation checks + aggregate volume/weight checks with an efficiency margin, not a simulation of how items would actually sit together in a box.
- **`PACKING_EFFICIENCY_FACTOR` (default 0.85)** — accounts for real-world dead space (irregular shapes, packing material). Configurable via Django settings, not hardcoded in the service.
- **`TIGHT_FIT_THRESHOLD` (default 0.75)** — flags technically-valid-but-close-to-capacity recommendations as `"tight"` rather than presenting every result with equal confidence, since the volume heuristic can produce false positives right at the boundary.
- **Multi-box splitting is same-box-type only.** v1 does not mix box types or split a single line's quantity across two different box types — it picks the cheapest option among "N units of one box type."
- **Axis-aligned only.** Items fitting only via a diagonal orientation are not detected as fitting — explicitly out of scope, not silently mishandled.
- **Inactive/soft-deleted products are rejected, not silently skipped** — a request referencing an inactive product returns a clear `400 INVALID_PRODUCT` rather than computing a recommendation that ignores that line.

---

## 6. AI Tool Disclosure

This project was built with Claude assisting on scaffolding and boilerplate.
The architecture decisions, DRY structure, algorithm design (including the
single→multi-box fallback ordering and the tight/comfortable confidence
signal), and the edge-case analysis were worked through and confirmed via a
planning conversation before implementation — see the accompanying plan
discussion for that reasoning trail.
# box_recommender
