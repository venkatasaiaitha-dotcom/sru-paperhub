# Security Architecture & Hardening Guide: SRU PaperHub

This document outlines the security controls, authentication architecture, access control policies, and hardening measures implemented for **SR University PaperHub**.

---

## 1. Threat Model & Security Posture

SRU PaperHub is a university exam paper archive and sharing portal with two primary classes of users:
1. **Students**: Authenticated users who can search, view, download approved past exam papers, and upload new question papers.
2. **Admins / Faculty**: Privileged users who can approve, edit, delete papers, manage announcements, and oversee content.
3. **Guests / Anonymous**: Read-only browsing access to approved exam papers.

### Key Threat Mitigations
- **Hardcoded Secret Elimination**: Zero administrative passwords or service-role keys are exposed in client-side code, HTML, or JavaScript bundles.
- **Student Impersonation Prevention**: Form inputs (`uploaderRollNo`, `uploaderName`, `user_id`) are never trusted blindly. Database triggers enforce that every paper record is strictly linked to `auth.uid()` and matches the verified profile.
- **SQL / NoSQL / ORM Injections**: All database interactions leverage parameterized queries via Supabase PostgREST client and Row-Level Security (RLS).
- **Stored XSS (Cross-Site Scripting)**: Strict DOM escaping (`escapeHTML`), URL validation preventing `javascript:` pseudo-protocols, and Content Security Policy (CSP) blocking unauthorized script execution.
- **Malicious File Uploads**: SVGs and executables are rejected. Allowed file formats are restricted to JPG, PNG, WEBP, and PDF. Storage paths are scoped strictly by authenticated user ID (`{auth.uid()}/{uuid}.ext`).

---

## 2. Authentication & Authorization Architecture

### A. Authentication
- **Provider**: Supabase Authentication (PostgreSQL Auth).
- **Registration**: Email & Password with automatic profile creation via the `handle_new_user()` trigger.
- **Session Management**: JWT access tokens stored and refreshed automatically by the Supabase client SDK.

### B. Authorization & Role Verification
- Administrative status is determined **exclusively on the server/database side** using the `public.admin_roles` table and the `public.is_admin(user_id)` function.
- Client-side code cannot grant itself administrative privileges. Any attempt to update announcements or delete papers without an admin session is rejected by PostgreSQL RLS.

```sql
-- Security Definer function to check admin role
CREATE OR REPLACE FUNCTION public.is_admin(user_id UUID DEFAULT auth.uid())
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.admin_roles
    WHERE user_id = COALESCE(user_id, auth.uid())
  );
$$;
```

---

## 3. Database Row Level Security (RLS) Policies

All database tables have `ROW LEVEL SECURITY` enabled. Overly permissive policies (such as `USING (true)` for DELETE/UPDATE) have been removed.

### Summary of Table Policies

| Table | Operation | Target Role | Policy Condition |
| :--- | :--- | :--- | :--- |
| `public.papers` | `SELECT` | `anon`, `authenticated` | `is_approved = true OR auth.uid() = user_id OR is_admin()` |
| `public.papers` | `INSERT` | `authenticated` | `auth.uid() IS NOT NULL AND auth.uid() = user_id` |
| `public.papers` | `UPDATE` | `authenticated` | `auth.uid() = user_id OR is_admin()` |
| `public.papers` | `DELETE` | `authenticated` | `auth.uid() = user_id OR is_admin()` |
| `public.announcements` | `SELECT` | `anon`, `authenticated` | `is_active = true OR is_admin()` |
| `public.announcements` | `INSERT / UPDATE / DELETE` | `authenticated` | `is_admin()` only |
| `public.profiles` | `SELECT` | `anon`, `authenticated` | `true` (Read profile info) |
| `public.profiles` | `UPDATE` | `authenticated` | `auth.uid() = id` (Users update own profile only) |
| `public.admin_roles` | `SELECT` | `authenticated` | `auth.uid() = user_id OR is_admin()` |
| `public.admin_roles` | `ALL` (Write) | `authenticated` | Super-admin / service_role only |

---

## 4. Storage Security (`paper-images` Bucket)

The storage bucket stores question paper scans and PDF files.

1. **Storage Path Isolation**:
   Files must be uploaded under the path format:
   ```
   paper-images/{auth.uid()}/{uuid}.{ext}
   ```
2. **Storage RLS Policies**:
   - **SELECT**: Public read for approved papers.
   - **INSERT**: Authenticated users can only insert into their own folder: `(storage.foldername(name))[1] = auth.uid()::text`.
   - **UPDATE / DELETE**: Users can only update or delete files in their own folder (`(storage.foldername(name))[1] = auth.uid()::text`) or if `is_admin()` is true.
3. **MIME & Extension Whitelist**:
   - `image/jpeg` (`.jpg`, `.jpeg`)
   - `image/png` (`.png`)
   - `image/webp` (`.webp`)
   - `application/pdf` (`.pdf`)
   - **SVG files are strictly disallowed** to prevent embedded script attacks.
4. **Size Restriction**: Maximum 10MB per file.

---

## 5. HTTP Security Headers (Netlify Deployment)

Configured via `netlify.toml`:

```toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    X-XSS-Protection = "1; mode=block"
    Referrer-Policy = "strict-origin-when-cross-origin"
    Strict-Transport-Security = "max-age=31536000; includeSubDomains; preload"
    Permissions-Policy = "camera=(), microphone=(), geolocation=(), payment=()"
    Cross-Origin-Opener-Policy = "same-origin"
    Content-Security-Policy = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com data:; img-src 'self' data: blob: https://*.supabase.co; connect-src 'self' https://*.supabase.co wss://*.supabase.co; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self';"
```

---

## 6. Safe Administrative Setup

To assign an administrator, execute the following SQL in your Supabase SQL Editor:

```sql
-- 1. Get the user's UUID from auth.users:
SELECT id, email FROM auth.users WHERE email = 'your-admin-email@sru.edu.in';

-- 2. Grant admin privileges:
INSERT INTO public.admin_roles (user_id, role)
VALUES ('<PASTE-USER-UUID-HERE>', 'admin')
ON CONFLICT (user_id) DO NOTHING;
```

---

## 7. Vulnerability Disclosure & Maintenance

If you discover a security vulnerability in SRU PaperHub, please report it to the SR University development team. Regular maintenance includes:
- Periodic review of `admin_roles` entries.
- Routine audit of storage bucket file counts and orphaned files.
- Maintaining updated dependency CDN hashes and CSP rules.
