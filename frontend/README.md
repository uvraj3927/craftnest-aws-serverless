# CraftNest static storefront

## Run locally
Open `index.html` in a browser, or serve this folder with any static file server.

## Configure your backend
Open `index.html` and set:
`const API_BASE_URL = "https://YOUR_API_BASE_URL";`

The frontend currently expects these endpoints:
- `POST /auth/register` — `{ name, email, password }`
- `POST /auth/login` — `{ email, password }`
- `GET /orders` — authenticated user's orders
- `POST /orders` — `{ items: [{ productId, quantity }], shippingAddress: { name, phone, address }, subtotal }`
- `GET /users/me` is reserved in the API map for a profile endpoint if you want to use it.

Login/register responses should include a session token as `token`, `sessionToken`, or `access_token`, and optionally a `user` object (or `profile`).

All authenticated requests send `Authorization: Bearer <token>`. Adjust endpoint paths and payload shapes to match your backend.

## Static hosting on Amazon S3
1. Create an S3 bucket and enable static website hosting.
2. Upload `index.html` (or the contents of this folder) to the bucket.
3. Set the index document to `index.html`.
4. Configure bucket/public access or CloudFront + OAC according to your preferred hosting setup.
5. For production, use HTTPS via CloudFront and configure your API's CORS policy to allow your storefront origin.

## Important
This is a frontend only. Authentication, order validation, inventory, payment handling, and user/order persistence must be implemented securely by your backend. Do not put secrets in this static file. Use HTTPS for the API. The cart is stored locally in the browser. The demo product images are illustrated placeholders (emoji artwork) and can be replaced with your own product photography.
