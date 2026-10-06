-- ===============================================================
-- SR UNIVERSITY PAPERHUB - PRODUCTION SECURITY & ANALYTICS SCHEMA
-- ===============================================================
-- Run this entire script in your Supabase Dashboard:
-- SQL Editor -> Click "New Query" -> Paste this script -> Click "Run"

-- 1. CREATE USER PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    roll_no TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    branch TEXT NOT NULL DEFAULT 'CSE',
    semester INTEGER NOT NULL DEFAULT 1,
    login_count INTEGER NOT NULL DEFAULT 1,
    last_login_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT chk_roll_no_len CHECK (length(roll_no) BETWEEN 1 AND 50),
    CONSTRAINT chk_branch_val CHECK (branch IN ('CSE', 'AIML', 'AIDS', 'ECE', 'EEE', 'MECH', 'CIVIL', 'ALL')),
    CONSTRAINT chk_sem_range CHECK (semester BETWEEN 1 AND 8)
);

-- Safely add login tracking columns if upgrading existing table
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'login_count'
    ) THEN 
        ALTER TABLE public.profiles ADD COLUMN login_count INTEGER NOT NULL DEFAULT 1;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'profiles' AND column_name = 'last_login_at'
    ) THEN 
        ALTER TABLE public.profiles ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL;
    END IF;
END $$;

-- 2. CREATE ADMIN ROLES TABLE
CREATE TABLE IF NOT EXISTS public.admin_roles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. CREATE PAPERS TABLE WITH SECURITY & AI OCR CONSTRAINTS
CREATE TABLE IF NOT EXISTS public.papers (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
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
    extracted_text TEXT,
    ocr_confidence NUMERIC DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT chk_paper_code CHECK (length(subject_code) BETWEEN 2 AND 25),
    CONSTRAINT chk_paper_name CHECK (length(subject_name) BETWEEN 2 AND 150),
    CONSTRAINT chk_paper_branch CHECK (branch IN ('CSE', 'AIML', 'AIDS', 'ECE', 'EEE', 'MECH', 'CIVIL')),
    CONSTRAINT chk_paper_sem CHECK (semester BETWEEN 1 AND 8),
    CONSTRAINT chk_paper_exam CHECK (exam_type IN ('MID_1', 'MID_2', 'SEM_END', 'SUPPLY')),
    CONSTRAINT chk_paper_reg CHECK (regulation IN ('R18', 'R19', 'R20', 'R21', 'R22', 'R24')),
    CONSTRAINT chk_paper_year CHECK (academic_year ~ '^[0-9]{4}-[0-9]{4}$'),
    CONSTRAINT chk_paper_img CHECK (length(image_url) > 5)
);

-- Safely add extracted_text and ocr_confidence if upgrading existing table
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'papers' AND column_name = 'user_id'
    ) THEN 
        ALTER TABLE public.papers ADD COLUMN user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'papers' AND column_name = 'extracted_text'
    ) THEN 
        ALTER TABLE public.papers ADD COLUMN extracted_text TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = 'papers' AND column_name = 'ocr_confidence'
    ) THEN 
        ALTER TABLE public.papers ADD COLUMN ocr_confidence NUMERIC DEFAULT 0;
    END IF;
END $$;

-- 4. CREATE ANNOUNCEMENTS TABLE
CREATE TABLE IF NOT EXISTS public.announcements (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT chk_notice_len CHECK (length(text) BETWEEN 2 AND 500)
);

INSERT INTO public.announcements (id, text)
VALUES (1, 'Welcome to SR University PaperHub! Browse past exam papers or upload new question papers to help your classmates.')
ON CONFLICT (id) DO NOTHING;

-- 5. HELPER SECURITY FUNCTIONS & TRIGGERS
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.admin_roles
    WHERE user_id = auth.uid()
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- Function to record and track user logins
CREATE OR REPLACE FUNCTION public.record_user_login(target_user_id UUID DEFAULT auth.uid())
RETURNS json AS $$
DECLARE
  v_count INTEGER;
  v_time TIMESTAMP WITH TIME ZONE;
BEGIN
  IF target_user_id IS NULL THEN
    target_user_id := auth.uid();
  END IF;

  IF target_user_id IS NOT NULL THEN
    UPDATE public.profiles
    SET 
      login_count = COALESCE(login_count, 0) + 1,
      last_login_at = timezone('utc'::text, now())
    WHERE id = target_user_id
    RETURNING login_count, last_login_at INTO v_count, v_time;

    RETURN json_build_object('success', true, 'login_count', v_count, 'last_login_at', v_time);
  END IF;

  RETURN json_build_object('success', false, 'error', 'No user ID provided');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger: Automatically create Profile upon signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, roll_no, name, email, branch, semester, login_count, last_login_at)
  VALUES (
    NEW.id,
    COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'roll_no'), ''), 'SRU' || SUBSTRING(NEW.id::text, 1, 6)),
    COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'name'), ''), SPLIT_PART(COALESCE(NEW.email, 'Student'), '@', 1)),
    COALESCE(NEW.email, 'user@sru.edu.in'),
    COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'branch'), ''), 'CSE'),
    COALESCE(NULLIF(NEW.raw_user_meta_data->>'semester', '')::integer, 1),
    1,
    timezone('utc'::text, now())
  )
  ON CONFLICT (id) DO UPDATE SET
    roll_no = COALESCE(NULLIF(TRIM(EXCLUDED.roll_no), ''), public.profiles.roll_no),
    name = COALESCE(NULLIF(TRIM(EXCLUDED.name), ''), public.profiles.name),
    email = COALESCE(EXCLUDED.email, public.profiles.email),
    branch = COALESCE(EXCLUDED.branch, public.profiles.branch),
    semester = COALESCE(EXCLUDED.semester, public.profiles.semester),
    login_count = COALESCE(public.profiles.login_count, 0) + 1,
    last_login_at = timezone('utc'::text, now()),
    updated_at = timezone('utc'::text, now());

  -- If admin email or admin metadata, register as admin
  IF NEW.email = 'admin@sru.edu.in' OR NEW.raw_user_meta_data->>'role' = 'admin' THEN
    INSERT INTO public.admin_roles (user_id, email, role)
    VALUES (NEW.id, NEW.email, 'admin')
    ON CONFLICT (user_id) DO UPDATE SET role = 'admin';
  END IF;

  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Recreate trigger on auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Trigger: Bind owner UID and verified profile to prevent student impersonation
CREATE OR REPLACE FUNCTION public.set_paper_owner()
RETURNS trigger AS $$
DECLARE
  v_roll TEXT;
  v_name TEXT;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    NEW.user_id := auth.uid();
    SELECT roll_no, name INTO v_roll, v_name FROM public.profiles WHERE id = auth.uid();
    IF v_roll IS NOT NULL THEN
      NEW.uploader_roll := v_roll;
    END IF;
    IF v_name IS NOT NULL THEN
      NEW.uploader_name := v_name;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_paper_inserted ON public.papers;
CREATE TRIGGER on_paper_inserted
  BEFORE INSERT ON public.papers
  FOR EACH ROW EXECUTE FUNCTION public.set_paper_owner();

-- Atomic download counter function
CREATE OR REPLACE FUNCTION public.increment_download(paper_id TEXT)
RETURNS void AS $$
BEGIN
  UPDATE public.papers
  SET download_count = COALESCE(download_count, 0) + 1
  WHERE id = paper_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to grant admin role by email
CREATE OR REPLACE FUNCTION public.grant_admin_by_email(admin_email TEXT)
RETURNS text AS $$
DECLARE
  target_user_id UUID;
BEGIN
  SELECT id INTO target_user_id FROM auth.users WHERE email = admin_email;
  IF target_user_id IS NOT NULL THEN
    INSERT INTO public.admin_roles (user_id, email, role)
    VALUES (target_user_id, admin_email, 'admin')
    ON CONFLICT (user_id) DO UPDATE SET role = 'admin';
    RETURN 'Admin role successfully granted to ' || admin_email;
  ELSE
    RETURN 'User with email ' || admin_email || ' not found in auth.users. Please sign up or create the user first in Supabase Auth.';
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. ENABLE ROW LEVEL SECURITY (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admin_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.papers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.announcements ENABLE ROW LEVEL SECURITY;

-- 7. DEFINE RLS POLICIES

-- PROFILES POLICIES
DROP POLICY IF EXISTS "Allow authenticated users to read profiles" ON public.profiles;
DROP POLICY IF EXISTS "Allow public read profiles" ON public.profiles;
CREATE POLICY "Allow public read profiles"
ON public.profiles FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow users to update own profile" ON public.profiles;
CREATE POLICY "Allow users to update own profile"
ON public.profiles FOR UPDATE
TO authenticated
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- ADMIN ROLES POLICIES
DROP POLICY IF EXISTS "Allow users to check own admin status" ON public.admin_roles;
CREATE POLICY "Allow users to check own admin status"
ON public.admin_roles FOR SELECT
TO authenticated
USING (auth.uid() = user_id OR public.is_admin());

-- PAPERS POLICIES
DROP POLICY IF EXISTS "Allow public read access to papers" ON public.papers;
CREATE POLICY "Allow public read access to papers"
ON public.papers FOR SELECT
USING (true);

-- Allow students and visitors to upload papers
DROP POLICY IF EXISTS "Allow authenticated insert to papers" ON public.papers;
DROP POLICY IF EXISTS "Allow public insert to papers" ON public.papers;
CREATE POLICY "Allow public insert to papers"
ON public.papers FOR INSERT
WITH CHECK (true);

-- Only paper owner or admin can update papers
DROP POLICY IF EXISTS "Allow owners and admin to update papers" ON public.papers;
CREATE POLICY "Allow owners and admin to update papers"
ON public.papers FOR UPDATE
TO authenticated
USING (public.is_admin() OR auth.uid() = user_id)
WITH CHECK (public.is_admin() OR auth.uid() = user_id);

-- Only paper owner or admin can delete papers
DROP POLICY IF EXISTS "Allow owners and admin to delete papers" ON public.papers;
CREATE POLICY "Allow owners and admin to delete papers"
ON public.papers FOR DELETE
TO authenticated
USING (public.is_admin() OR auth.uid() = user_id);

-- ANNOUNCEMENTS POLICIES
DROP POLICY IF EXISTS "Allow public read announcements" ON public.announcements;
CREATE POLICY "Allow public read announcements"
ON public.announcements FOR SELECT
USING (true);

DROP POLICY IF EXISTS "Allow admin update announcements" ON public.announcements;
CREATE POLICY "Allow admin update announcements"
ON public.announcements FOR UPDATE
TO authenticated
USING (public.is_admin())
WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Allow admin insert announcements" ON public.announcements;
CREATE POLICY "Allow admin insert announcements"
ON public.announcements FOR INSERT
TO authenticated
WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Allow admin delete announcements" ON public.announcements;
CREATE POLICY "Allow admin delete announcements"
ON public.announcements FOR DELETE
TO authenticated
USING (public.is_admin());

-- 8. STORAGE POLICIES (paper-images bucket)
INSERT INTO storage.buckets (id, name, public)
VALUES ('paper-images', 'paper-images', true)
ON CONFLICT (id) DO UPDATE SET public = true;

DROP POLICY IF EXISTS "Public paper images access" ON storage.objects;
CREATE POLICY "Public paper images access"
ON storage.objects FOR SELECT
USING (bucket_id = 'paper-images');

DROP POLICY IF EXISTS "Allow upload to paper-images" ON storage.objects;
CREATE POLICY "Allow upload to paper-images"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'paper-images');

DROP POLICY IF EXISTS "Allow update own images or admin" ON storage.objects;
CREATE POLICY "Allow update own images or admin"
ON storage.objects FOR UPDATE
TO authenticated
USING (
  bucket_id = 'paper-images' AND
  ((storage.foldername(name))[1] = auth.uid()::text OR public.is_admin())
);

DROP POLICY IF EXISTS "Allow delete own images or admin" ON storage.objects;
CREATE POLICY "Allow delete own images or admin"
ON storage.objects FOR DELETE
TO authenticated
USING (
  bucket_id = 'paper-images' AND
  ((storage.foldername(name))[1] = auth.uid()::text OR public.is_admin())
);
