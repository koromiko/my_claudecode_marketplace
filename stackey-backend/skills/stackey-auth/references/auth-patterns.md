# Stackey Authentication Patterns

Detailed authentication implementation patterns for StackeyBackend.

## Edge Function Auth Pattern

Every Edge Function follows this pattern:

```typescript
// 1. Handle CORS preflight
const corsResponse = handleCors(req);
if (corsResponse) return corsResponse;

// 2. Get auth context (returns null if no token)
const auth = await getAuthContext(req);

// 3. For user endpoints
const { userId } = requireAuth(auth);

// 4. For admin endpoints
requireAdmin(auth);
```

## Auth Context Structure

The `getAuthContext()` function returns:

```typescript
interface AuthContext {
  userId: string;    // UUID from auth.users
  isAdmin: boolean;  // true if users.role = 'admin'
}
```

Returns `null` if no Authorization header or invalid token.

## Error Responses

| Status | Error Message | When |
|--------|---------------|------|
| 401 | `{"error": "Unauthorized"}` | No/invalid token |
| 403 | `{"error": "Forbidden"}` | User lacks admin role |

## Getting a Token (Local Development)

### Create a test user

```bash
# Using Supabase CLI
supabase auth create-user \
  --email test@example.com \
  --password testpassword123
```

### Sign in to get a token

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123"
  }' \
  "http://127.0.0.1:54321/auth/v1/token?grant_type=password"
```

Response includes:
```json
{
  "access_token": "eyJhbG...",
  "refresh_token": "...",
  "expires_in": 3600,
  "user": { ... }
}
```

### Make authenticated requests

```bash
export TOKEN="eyJhbG..."
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:54321/functions/v1/users/me"
```

## Making a User Admin

Update the user's role in the database:

```sql
UPDATE users SET role = 'admin' WHERE email = 'admin@example.com';
```

Or using Supabase Studio at `http://127.0.0.1:54323`.

## Token Refresh

Tokens expire after 1 hour (configurable). Refresh using:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}' \
  "http://127.0.0.1:54321/auth/v1/token?grant_type=refresh_token"
```

## OAuth Flow

### Supported Providers

1. **Google OAuth**
2. **Apple Sign In**

### OAuth URL Generation

```bash
# Get OAuth URL (provider: google or apple)
curl "http://127.0.0.1:54321/auth/v1/authorize?provider=google&redirect_to=myapp://callback"
```

### OAuth Callback

The `/auth-callback` Edge Function handles OAuth redirects and extracts tokens.

## User Creation Flow

When a new user signs up (via email or OAuth):

1. Supabase creates a row in `auth.users`
2. The `on_auth_user_created` trigger fires
3. A corresponding row is created in `public.users` with:
   - `id` = auth user ID
   - `email` = from auth
   - `display_name` = from OAuth metadata (`full_name` or `name`)
   - `avatar_url` = from OAuth metadata
   - `role` = 'user' (default)

## Testing Auth with Bruno

The Bruno test suite includes auth fixtures. Run:

```bash
./bruno/scripts/setup-fixtures.sh
```

This outputs ready-to-use tokens for both user and admin accounts.

## Security Notes

1. **Service Role Key**: Edge Functions use the service role key to bypass RLS. Never expose this key to clients.

2. **RLS as Defense-in-Depth**: RLS policies exist as a backup, but primary access control is in Edge Functions.

3. **Role Storage**: User roles are stored in the `users` table, not in JWT claims, so role changes take effect immediately.

4. **Private Blocks**: Non-admins get 404 (not 403) for private blocks to prevent information leakage about block existence.
