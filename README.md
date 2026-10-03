# SR University PaperHub

A centralized, responsive web portal for **SR University** students and faculty to access, search, and contribute previous semester examination question papers.

---

## Features

- **Collegiate Blue & White Academic Theme**: Designed with clean typography and distraction-free layout.
- **Multi-Regulation Support**: Full filtering and upload coverage for **R24**, **R22**, **R21**, **R20**, **R19**, and **R18** regulations.
- **Academic Years**: Covers academic years up to **2025–2026**.
- **Interactive Question Paper Viewer**: Fullscreen modal with smooth Zoom In, Zoom Out, 90° Rotation, and direct image download.
- **Cloud Database & Storage (Supabase)**: All question paper metadata, photos, and announcements are stored permanently in the cloud and synced across all devices.
- **Fast Filter & Search Bar**: Search by subject code (e.g., `22CS301`), title, branch, semester, regulation, and academic year.
- **Faculty & Admin Moderation Panel**: Admin login to delete outdated papers, clear archives, and broadcast campus announcements.
- **Dual Fallback Engine**: Seamlessly transitions between Supabase cloud storage and local Python HTTP server.

---

## Tech Stack

- **Frontend**: HTML5, Tailwind CSS (CDN), FontAwesome 6, JavaScript (ES6+)
- **Backend / Cloud**: Supabase (PostgreSQL Database & Storage Buckets)
- **Local Fallback Server**: Python 3 standard library (`http.server`, `socketserver`)
- **Deployment Ready**: Vercel (`vercel.json`), Netlify (`netlify.toml`), Render (`render.yaml`, `Procfile`)

---

## Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/venkatasaiaitha/sru-paperhub.git
   cd sru-paperhub
   ```

2. **Start the local server**:
   ```bash
   python server/server.py
   ```
   Open your browser to: `http://localhost:3000`

---

## Cloud Database Setup (Supabase)

1. Open your [Supabase Dashboard](https://supabase.com/dashboard).
2. Go to **SQL Editor** -> **New query**.
3. Run the script in [`supabase_schema.sql`](./supabase_schema.sql) to create the `papers` and `announcements` tables, policies, and the `paper-images` storage bucket.
4. Add your Supabase URL and anon key to [`public/supabase_config.js`](./public/supabase_config.js).

---

## Deployment

### Vercel
```bash
npx vercel
```

### Netlify
Drag and drop the `public` folder onto [app.netlify.com/drop](https://app.netlify.com/drop).

---

## License

MIT License — Created for the student community of SR University, Warangal.
