-- ===============================================================
-- SR UNIVERSITY PAPERHUB - SUPABASE DATABASE & STORAGE SETUP
-- ===============================================================
-- Follow these steps in your Supabase Dashboard:
-- 1. Go to: SQL Editor (in the left sidebar)
-- 2. Click "New Query"
-- 3. Paste this entire script
-- 4. Click "Run" (green button)

-- 1. CREATE PAPERS TABLE
CREATE TABLE IF NOT EXISTS public.papers (
    id TEXT PRIMARY KEY,
    subject_code TEXT NOT NULL,
    subject_name TEXT NOT NULL,
    branch TEXT NOT NULL,
    semester INTEGER NOT NULL,
    exam_type TEXT NOT NULL,
    exam_type_label TEXT,
    regulation TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    duration TEXT DEFAULT '90 Mins',
    max_marks INTEGER DEFAULT 30,
    school TEXT,
    uploader_name TEXT,
    uploader_roll TEXT,
    image_url TEXT NOT NULL,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. CREATE ANNOUNCEMENTS TABLE
CREATE TABLE IF NOT EXISTS public.announcements (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Insert default announcement
INSERT INTO public.announcements (id, text)
VALUES (1, 'Welcome to SR University PaperHub! Browse past exam papers or upload new question papers to help your classmates.')
ON CONFLICT (id) DO NOTHING;

-- 3. ENABLE ROW LEVEL SECURITY (RLS)
ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.announcements ENABLE ROW LEVEL SECURITY;

-- 4. CREATE POLICIES FOR PAPERS (Allow students to view, upload & delete)
DROP POLICY IF EXISTS "Allow public read access to papers" ON public.papers;
CREATE POLICY "Allow public read access to papers"
ON public.papers FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow public insert to papers" ON public.papers;
CREATE POLICY "Allow public insert to papers"
ON public.papers FOR INSERT
WITH CHECK (true);

DROP POLICY IF EXISTS "Allow public update to papers" ON public.papers;
CREATE POLICY "Allow public update to papers"
ON public.papers FOR UPDATE
USING (true);

DROP POLICY IF EXISTS "Allow public delete to papers" ON public.papers;
CREATE POLICY "Allow public delete to papers"
ON public.papers FOR DELETE
USING (true);

-- POLICIES FOR ANNOUNCEMENTS
DROP POLICY IF EXISTS "Allow public read announcements" ON public.announcements;
CREATE POLICY "Allow public read announcements"
ON public.announcements FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow public update announcements" ON public.announcements;
CREATE POLICY "Allow public update announcements"
ON public.announcements FOR UPDATE
USING (true);

-- 5. CREATE STORAGE BUCKET FOR QUESTION PAPER IMAGES
INSERT INTO storage.buckets (id, name, public)
VALUES ('paper-images', 'paper-images', true)
ON CONFLICT (id) DO UPDATE SET public = true;

-- Storage Policies for paper-images bucket
DROP POLICY IF EXISTS "Public paper images access" ON storage.objects;
CREATE POLICY "Public paper images access"
ON storage.objects FOR SELECT
USING (bucket_id = 'paper-images');

DROP POLICY IF EXISTS "Public paper images upload" ON storage.objects;
CREATE POLICY "Public paper images upload"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'paper-images');

DROP POLICY IF EXISTS "Public paper images delete" ON storage.objects;
CREATE POLICY "Public paper images delete"
ON storage.objects FOR DELETE
USING (bucket_id = 'paper-images');
