# Stackey Database Schema Reference

Complete database schema documentation for StackeyBackend.

## Tables

### users

Extends Supabase `auth.users` with application-specific profile data.

```sql
CREATE TABLE public.users (
  id uuid REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email text NOT NULL,
  display_name text,
  avatar_url text,
  role text NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PK, FK to auth.users | User identifier |
| email | text | NOT NULL | User email |
| display_name | text | | Display name from OAuth |
| avatar_url | text | | Profile picture URL |
| role | text | NOT NULL, CHECK | 'user' or 'admin' |
| created_at | timestamptz | DEFAULT now() | Creation timestamp |
| updated_at | timestamptz | DEFAULT now() | Last update timestamp |

### blocks

Video generation presets (camera movements, angles, styles).

```sql
CREATE TABLE public.blocks (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  subtitle text,
  prompt_text text,
  gradient_id integer DEFAULT 1,
  icon text,
  tags text[] DEFAULT '{}',
  is_public boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES public.users(id),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX blocks_tags_idx ON public.blocks USING gin(tags);
CREATE INDEX blocks_is_public_idx ON public.blocks(is_public);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PK | Block identifier |
| title | text | NOT NULL | Block title |
| description | text | | Block description |
| subtitle | text | | Block subtitle |
| prompt_text | text | | Prompt text for video generation |
| gradient_id | integer | DEFAULT 1 | Gradient theme ID |
| icon | text | | Icon identifier |
| tags | text[] | DEFAULT '{}' | Filterable tags |
| is_public | boolean | NOT NULL, DEFAULT false | Visibility flag |
| created_by | uuid | FK to users | Creator user ID |
| created_at | timestamptz | DEFAULT now() | Creation timestamp |
| updated_at | timestamptz | DEFAULT now() | Last update timestamp |

### block_media

Images and videos associated with blocks.

```sql
CREATE TABLE public.block_media (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  block_id uuid REFERENCES public.blocks(id) ON DELETE CASCADE NOT NULL,
  type text NOT NULL CHECK (type IN ('image', 'video')),
  url text NOT NULL,
  filename text,
  mime_type text,
  size_bytes bigint,
  sort_order int DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX block_media_block_id_idx ON public.block_media(block_id);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PK | Media identifier |
| block_id | uuid | FK, NOT NULL, CASCADE | Parent block |
| type | text | NOT NULL, CHECK | 'image' or 'video' |
| url | text | NOT NULL | Public storage URL |
| filename | text | | Original filename |
| mime_type | text | | MIME type |
| size_bytes | bigint | | File size in bytes |
| sort_order | int | DEFAULT 0 | Display order |
| created_at | timestamptz | DEFAULT now() | Upload timestamp |

### favorites

Junction table for user favorites (many-to-many).

```sql
CREATE TABLE public.favorites (
  user_id uuid REFERENCES public.users(id) ON DELETE CASCADE,
  block_id uuid REFERENCES public.blocks(id) ON DELETE CASCADE,
  created_at timestamptz DEFAULT now(),
  PRIMARY KEY (user_id, block_id)
);
```

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| user_id | uuid | PK, FK, CASCADE | User who favorited |
| block_id | uuid | PK, FK, CASCADE | Favorited block |
| created_at | timestamptz | DEFAULT now() | When favorited |

## Row Level Security (RLS)

RLS is enabled on all tables as defense-in-depth. Edge Functions use the service role key to bypass RLS.

### users

```sql
-- Users can only read their own profile
CREATE POLICY "Users can read own profile"
  ON public.users FOR SELECT
  USING (auth.uid() = id);
```

### blocks

```sql
-- Public blocks visible to everyone
CREATE POLICY "Public blocks visible to all"
  ON public.blocks FOR SELECT
  USING (is_public = true);

-- Private blocks visible to authenticated users only
CREATE POLICY "Private blocks visible to authenticated"
  ON public.blocks FOR SELECT
  USING (is_public = false AND auth.uid() IS NOT NULL);
```

### block_media

```sql
-- Anyone can read block media
CREATE POLICY "Anyone can read block media"
  ON public.block_media FOR SELECT
  USING (true);
```

### favorites

```sql
-- Users manage their own favorites
CREATE POLICY "Users can read own favorites"
  ON public.favorites FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own favorites"
  ON public.favorites FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own favorites"
  ON public.favorites FOR DELETE
  USING (auth.uid() = user_id);
```

## Storage

### block-media bucket

```sql
INSERT INTO storage.buckets (id, name, public)
VALUES ('block-media', 'block-media', true);

-- Public read access
CREATE POLICY "Public read access for block media"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'block-media');
```

**Path Pattern:** `{block_id}/{uuid}.{ext}`

Example: `abc123-uuid/def456-uuid.mp4`

## Triggers

### updated_at trigger

Automatically updates `updated_at` on row modification.

```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS trigger AS $$
BEGIN
  new.updated_at = now();
  RETURN new;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
  BEFORE UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER blocks_updated_at
  BEFORE UPDATE ON public.blocks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
```

### New user trigger

Automatically creates a user profile when a new auth user is created.

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (id, email, display_name, avatar_url)
  VALUES (
    new.id,
    new.email,
    COALESCE(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url'
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

## Migrations

Migrations are in `supabase/migrations/`:

| File | Description |
|------|-------------|
| `001_initial_schema.sql` | Base schema with all tables |
| `002_add_is_public_to_blocks.sql` | Adds `is_public` column |
| `003_add_video_block_fields.sql` | Adds `subtitle`, `prompt_text`, `gradient_id`, `icon` columns |
| `004_seed_video_blocks.sql` | Seeds sample video blocks data |

Apply migrations locally:

```bash
supabase db reset  # Resets and applies all migrations
```

Push to production:

```bash
supabase db push
```
