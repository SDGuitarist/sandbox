STATUS: PASS

# swarmlimit C2 smoke report

- planned endpoints: 31
- exercised endpoints: 31
- planned_minus_exercised: 0
- exercised_minus_planned: 0
- suite failures: 0
- unexpected/unasserted status mismatches: 0

## planned_minus_exercised
- (none)

## exercised_minus_planned
- (none)

## exercised set
- DELETE /categories/<int:cid>
- DELETE /products/<int:pid>
- DELETE /suppliers/<int:sid>
- GET /audit
- GET /categories
- GET /categories/<int:cid>
- GET /orders
- GET /orders/<int:oid>
- GET /payments
- GET /payments/<int:pid>
- GET /products
- GET /products/<int:pid>
- GET /returns
- GET /returns/<int:rid>
- GET /shipments/<int:sid>
- GET /suppliers
- GET /suppliers/<int:sid>
- PATCH /categories/<int:cid>
- PATCH /products/<int:pid>
- PATCH /suppliers/<int:sid>
- POST /auth/login
- POST /auth/logout
- POST /auth/register
- POST /categories
- POST /orders
- POST /orders/<int:oid>/shipments
- POST /products
- POST /returns
- POST /shipments/<int:sid>/advance
- POST /suppliers
- PUT /products/<int:pid>/categories

## suite failures
- (none)

## unexpected status mismatches (asserted negatives 400/401/403/404/409 are EXPECTED)
- (none)

