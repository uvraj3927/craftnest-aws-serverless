# CraftNest AWS Lambda backend (Python 3.12)

Modular API backend for API Gateway HTTP API or REST API, using DynamoDB and SNS.

## Project layout

```text
craftnest_lambda_backend/
├── app/
│   ├── config.py
│   ├── handlers.py
│   ├── logging_utils.py
│   ├── repository.py
│   ├── responses.py
│   └── security.py
├── lambda_function.py
└── requirements.txt
```

## Environment variables

Required:
- `USERS_TABLE` — DynamoDB users table name (partition key: `email`, String).
- `ORDERS_TABLE` — DynamoDB orders table name (partition key: `order_id`, String).
- `SNS_TOPIC_ARN` — SNS topic ARN used for order confirmation messages.
- `SESSION_SECRET` — long random secret used to sign bearer session tokens. Store it in Secrets Manager or Parameter Store; do not commit it.

Optional:
- `SESSION_TTL_SECONDS` — session lifetime in seconds (default `3600`).
- `PBKDF2_ITERATIONS` — PBKDF2-HMAC-SHA256 iterations (default `310000`).
- `CORS_ALLOW_ORIGIN` — allowed frontend origin (default `*`; set to the exact site origin in production).

## DynamoDB setup

Create `UsersTable`:
- Partition key: `email` (String).

Create `OrdersTable`:
- Partition key: `order_id` (String).
- Add a Global Secondary Index named **`user_email-index`**, partition key `user_email` (String), with `created_at` as an optional sort key (String). The code queries this index for a user's order history.
- Recommended: enable point-in-time recovery and server-side encryption.

The code stores order amounts as DynamoDB Decimal values. Do not store Python floats for money.

## Routes and request formats

All routes return JSON and include CORS headers. Send JSON with `Content-Type: application/json`.

### `POST /register`
```json
{"name":"Aanya","email":"aanya@example.com","password":"a-strong-password"}
```
Returns `201` with `user.user_id`, `user.name`, and `user.email`. Duplicate email returns `409`.

### `POST /login`
```json
{"email":"aanya@example.com","password":"a-strong-password"}
```
Returns `200` with `token` and `user`. Invalid email/password returns `401`.
Use the token on protected routes:
`Authorization: Bearer <token>`

### `POST /orders`
```json
{
  "items":[
    {"product_id":"1","quantity":2,"unit_price":"999.00"}
  ],
  "shipping_address":{
    "name":"Aanya","phone":"9876543210","address":"12 Garden Road, Pune"
  }
}
```
The authenticated user's email is taken from the signed token, not trusted from the request body. The backend recalculates `total_amount` from item quantities and unit prices.

**Important pricing note:** This starter accepts `unit_price` in the request so it can operate with the supplied two-table schema. A production commerce backend must load current prices and discounts from a trusted product catalogue (for example, a `ProductsTable`) and must never trust browser-submitted prices. Add idempotency keys and payment-provider verification before accepting real payments.

An SNS publish failure happens after the order is persisted. In that case the API returns `202` and the order ID, and logs `ORDER_FAILED` with `reason: SNS_FAILURE`; it does not claim the DynamoDB write was rolled back. For production, use an outbox/retry pattern (e.g. DynamoDB Streams) to reliably deliver notifications.

### `GET /orders`
Requires a bearer token. Returns only the authenticated user's order history. The email is derived from the token; callers cannot query another user's email.

## CloudWatch structured logging

`log_event(level, event_type, details)` writes a single-line JSON object to stdout with these top-level keys:
- `timestamp`
- `level`
- `event_type`
- `request_id`
- `details`

The required event types are emitted:
- `USER_REGISTERED` — `INFO`
- `LOGIN_SUCCESS` — `INFO`
- `LOGIN_FAILED` — `WARNING`; `details.reason` is exactly `USER_NOT_FOUND` or `INVALID_PASSWORD`, and includes attempted `details.email`
- `ORDER_CREATED` — `INFO`; includes `details.order_id` and `details.total_amount`
- `ORDER_FAILED` — `ERROR`; includes a reason such as `DYNAMODB_FAILURE` or `SNS_FAILURE`. Empty carts are rejected as a 400 validation error before persistence.
- `UNHANDLED_EXCEPTION` — `ERROR`; includes `details.stack_trace`

### CloudWatch Logs Metric Filter patterns

Create these metric filters on the Lambda log group. Choose a metric namespace such as `CraftNest/Backend`.

| Metric | Filter pattern |
|---|---|
| User registrations | `{ $.event_type = "USER_REGISTERED" }` |
| Successful logins | `{ $.event_type = "LOGIN_SUCCESS" }` |
| Failed logins | `{ $.event_type = "LOGIN_FAILED" }` |
| Orders created | `{ $.event_type = "ORDER_CREATED" }` |
| Order failures | `{ $.event_type = "ORDER_FAILED" }` |
| Unhandled exceptions | `{ $.event_type = "UNHANDLED_EXCEPTION" }` |

For each filter, set metric value to `1`. For warning/error alarms, the same filters can be used to create CloudWatch Alarms. To count login failures by reason, create a separate filter:
`{ $.event_type = "LOGIN_FAILED" && $.details.reason = "USER_NOT_FOUND" }`
and:
`{ $.event_type = "LOGIN_FAILED" && $.details.reason = "INVALID_PASSWORD" }`

## IAM permissions

Attach least-privilege permissions to the Lambda execution role:
- `dynamodb:GetItem`, `dynamodb:PutItem` on the UsersTable ARN.
- `dynamodb:PutItem`, `dynamodb:Query` on the OrdersTable ARN and its `user_email-index` GSI ARN.
- `sns:Publish` on the configured SNS topic ARN.
- Standard Lambda logging permissions (`logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`), typically via `AWSLambdaBasicExecutionRole`.

## API Gateway / Lambda configuration

- Runtime: **Python 3.12**
- Handler: **`lambda_function.lambda_handler`**
- Integration: Lambda proxy integration.
- Route keys: `POST /register`, `POST /login`, `POST /orders`, `GET /orders`, and `OPTIONS /{proxy+}` (or equivalent CORS configuration).
- Set Lambda environment variables above.
- Ensure API Gateway CORS and Lambda CORS settings agree. For production, replace `CORS_ALLOW_ORIGIN=*` with your S3/CloudFront website origin.
- Configure API Gateway throttling and request-size limits.

## Package and deploy

Install dependencies into a build folder and zip the contents (Lambda's Linux-compatible environment is recommended):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -t package/
cp -r app lambda_function.py package/
cd package
zip -r ../craftnest-backend.zip .
```

Upload `craftnest-backend.zip` to Lambda, set handler/runtime, environment variables, and IAM role.

## Security notes

- Passwords are stored using salted PBKDF2-HMAC-SHA256; plaintext passwords are never logged or stored.
- Session tokens are HMAC-signed bearer tokens. Use HTTPS only and rotate `SESSION_SECRET` carefully (rotation invalidates active sessions).
- This starter intentionally does not implement password reset, email verification, refresh tokens, rate limiting, CAPTCHA, payment processing, or admin authorization.
- Consider a Lambda authorizer / Amazon Cognito for production identity management.
