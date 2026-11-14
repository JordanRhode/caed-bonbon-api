# Caed Bonbon Management API

Backend service for managing artisan bonbon flavors, controlling active/seasonal status, and processing raw bonbon photos through an AI background-removal and centering pipeline.

Built with **FastAPI**, **PostgreSQL**, **rembg (birefnet-general-lite)**, and designed for deployment on **Railway**.

---

## Features

- **Flavor Management**: Create, edit, reorder, and delete bonbons.
- **Activation Control**: Toggle `is_active` to instantly add/remove flavors from your active showcase or Shopify bundle builder.
- **AI Image Pipeline**: Upload raw photos (`.jpg`, `.png`, `.webp`) and automatically:
  - Remove background using `birefnet-general-lite` ONNX model.
  - Crop tightly to subject bounding box.
  - Scale and center on a 500×500 transparent canvas.
  - Apply contrast (1.08), color boost (1.05), and unsharp masking.
  - Export to optimized `.webp` (quality 92, method 6).
- **Single-Password Authentication**:
  - Secure single admin password set via `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`.
  - Database-backed session table with token hashing and automatic expiration.
  - Supports both `Authorization: Bearer <token>` and `HttpOnly` secure cookies.
- **Railway Ready**:
  - Persistent volume mount for media storage (`/data`).
  - Pre-cached ONNX model in Docker build for fast startup without cold-start timeouts.
  - Automated database migrations via Alembic on deploy.

---

## Architecture & Database Schema

### Database Tables (PostgreSQL)

1. **`bonbons`**:
   - `id`: UUID (Primary Key)
   - `slug`: Unique slug (e.g. `salted-caramel`)
   - `name`: Display name (e.g. `Salted Caramel`)
   - `description`: Flavor description
   - `shell`: Shell chocolate type (`dark`, `milk`, `white`, `ruby`)
   - `category`: `signature`, `seasonal`, `archived`
   - `allergens`: List of allergen strings (`["Milk", "Soy", "Nuts"]`)
   - `is_active`: Boolean toggle
   - `sort_order`: Integer display sort index
   - `primary_image_id`: Foreign key to active image in `bonbon_images`
   - `created_at`, `updated_at`: Timestamps

2. **`bonbon_images`**:
   - `id`: UUID (Primary Key)
   - `bonbon_id`: Foreign Key to `bonbons.id` (CASCADE)
   - `raw_filename`: Filename of uploaded raw photo
   - `processed_filename`: Filename of generated 500×500 `.webp`
   - `status`: `pending`, `processing`, `completed`, `failed`
   - `width`, `height`: Canvas dimensions (500x500)
   - `model_used`: `birefnet-general-lite`
   - `created_at`: Timestamp

3. **`sessions`**:
   - `id`: UUID (Primary Key)
   - `token_hash`: SHA-256 hash of secret token (Unique, Indexed)
   - `expires_at`: Expiration timestamp (30 days rolling)
   - `created_at`, `last_used_at`, `ip_address`, `user_agent`

---

## API Endpoints

### Authentication
- `POST /api/auth/login`: Authenticate with admin password. Returns `{ "token": "...", "expires_at": "..." }` and sets cookie.
- `POST /api/auth/logout`: Revoke active session token.
- `GET /api/auth/verify`: Check if current session is authenticated.

### Bonbons
- `GET /api/bonbons`: List flavors. Query parameters:
  - `active_only=true` (filter only active flavors)
  - `category=signature|seasonal`
- `GET /api/bonbons/{id_or_slug}`: Retrieve single flavor.
- `POST /api/bonbons`: Create a flavor *(Requires Auth)*.
- `PATCH /api/bonbons/{id}`: Update flavor details *(Requires Auth)*.
- `PATCH /api/bonbons/{id}/activate`: Toggle `{"is_active": true|false}` *(Requires Auth)*.
- `DELETE /api/bonbons/{id}`: Delete flavor and its images *(Requires Auth)*.

### Images & Processing
- `POST /api/bonbons/{id}/images`: Upload raw photo (`multipart/form-data`). Runs through background removal and automatically sets as primary image *(Requires Auth)*.
- `GET /api/bonbons/{id}/images`: List image versions for this bonbon.
- `POST /api/bonbons/{id}/images/{image_id}/set-primary`: Revert to or select an older image as primary.
- `DELETE /api/bonbons/{id}/images/{image_id}`: Delete image from disk and DB.

### Media Serving
- `GET /media/images/processed/{filename}`: Serve processed `.webp` with caching headers.
- `GET /media/images/raw/{filename}`: Serve raw uploaded file.

---

## Railway Deployment Guide

### 1. Create a New Railway Project
1. Log in to [Railway](https://railway.app/).
2. Click **New Project** → **Provision PostgreSQL**.

### 2. Add Persistent Storage Volume
1. In the Railway dashboard for this service:
2. Go to **Settings** → **Volumes** → **Add Volume**.
3. Set the **Mount Path** to `/data`.

### 3. Configure Environment Variables
Add the following in your Railway service settings:

```env
DATABASE_URL=${{Postgres.DATABASE_URL}}
ADMIN_PASSWORD=your-secure-admin-password
STORAGE_DIR=/data
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
CORS_ORIGINS=https://your-nextjs-app.com,https://your-admin-app.com
PUBLIC_READ_ACCESS=false
```

### 4. Deploy via GitHub / Railway CLI
Deploy this repository. Railway will detect the `Dockerfile`, install dependencies, cache the ONNX model, run migrations (`alembic upgrade head`), and boot Uvicorn.

---

## Next.js Integration Example

### 1. Authenticated Login Screen (Server Action or Route Handler)
```ts
// app/actions/auth.ts
"use server";

import { cookies } from "next/headers";

export async function loginToAdmin(password: string) {
  const res = await fetch(`${process.env.API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });

  if (!res.ok) {
    return { success: false, error: "Invalid password" };
  }

  const data = await res.json();
  const cookieStore = await cookies();
  cookieStore.set("bonbon_session", data.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    expires: new Date(data.expires_at),
  });

  return { success: true };
}
```

### 2. Next.js Route Guard Middleware (`middleware.ts`)
```ts
// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/request";

export function middleware(request: NextRequest) {
  const sessionToken = request.cookies.get("bonbon_session")?.value;

  if (request.nextUrl.pathname.startsWith("/admin") && !sessionToken) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*"],
};
```

### 3. Fetching Active Flavors
```ts
export async function getActiveFlavors() {
  const res = await fetch(`${process.env.API_BASE_URL}/api/bonbons?active_only=true`, {
    headers: {
      // Pass bearer token or cookie
      Authorization: `Bearer ${process.env.ADMIN_API_TOKEN}`,
    },
    next: { revalidate: 60 },
  });
  return res.json();
}
```

---

## Local Development

```bash
# 1. Create Python virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env
cp .env.example .env

# 4. Start local development server
uvicorn app.main:app --reload --port 8000
```

Access Swagger UI interactive docs at: `http://localhost:8000/docs`
