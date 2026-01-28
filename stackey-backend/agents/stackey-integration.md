---
description: Generates API integration code for Stackey backend. Use when user asks to "integrate with Stackey", "call Stackey API", "create Stackey client", or needs TypeScript/Swift code for blocks, favorites, or media endpoints.
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion
model: sonnet
---

# Stackey Integration Agent

Generate type-safe API client code for integrating with the StackeyBackend Supabase Edge Functions.

## Input

The prompt will specify:
- **Target platform**: TypeScript (web) or Swift (iOS)
- **Endpoints needed**: Which API operations to implement
- **Authentication context**: Whether the app needs user/admin auth

## Workflow

### Step 1: Gather Requirements

If not specified in the prompt, use AskUserQuestion to clarify:
1. Target platform (TypeScript or Swift)
2. Which endpoints are needed (blocks, favorites, users, media)
3. Authentication approach (anonymous, user auth, or admin)

### Step 2: Generate Code

Based on requirements, generate appropriate client code.

---

## TypeScript Templates

### Base Client

```typescript
const API_BASE = process.env.NEXT_PUBLIC_SUPABASE_URL + '/functions/v1';

interface ApiError {
  error: string;
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error((data as ApiError).error || 'Request failed');
  }

  return data as T;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}
```

### Blocks API

```typescript
interface Block {
  id: string;
  title: string;
  description: string | null;
  subtitle: string | null;
  prompt_text: string | null;
  gradient_id: number;
  icon: string | null;
  tags: string[];
  is_public: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
  block_media: BlockMedia[];
}

interface BlockMedia {
  id: string;
  type: 'image' | 'video';
  url: string;
  filename: string | null;
  sort_order: number;
}

interface PageInfo {
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  startCursor: string | null;
  endCursor: string | null;
  totalCount: number;
}

interface BlocksResponse {
  data: Block[];
  pageInfo: PageInfo;
}

// List public blocks with cursor-based pagination
async function getBlocks(params?: {
  tags?: string[];
  search?: string;
  limit?: number;
  after?: string;
  before?: string;
}): Promise<BlocksResponse> {
  const searchParams = new URLSearchParams();
  if (params?.tags?.length) searchParams.set('tags', params.tags.join(','));
  if (params?.search) searchParams.set('search', params.search);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.after) searchParams.set('after', params.after);
  if (params?.before) searchParams.set('before', params.before);

  const query = searchParams.toString();
  return fetchApi(`/blocks${query ? `?${query}` : ''}`);
}

// Get single block
async function getBlock(id: string): Promise<Block> {
  return fetchApi(`/blocks/${id}`);
}
```

### Favorites API (requires auth)

```typescript
interface Favorite {
  user_id: string;
  block_id: string;
  created_at: string;
}

interface FavoritesResponse {
  data: Block[];
  pageInfo: PageInfo;
}

// List user's favorites with cursor-based pagination
async function getFavorites(token: string, params?: {
  limit?: number;
  after?: string;
  before?: string;
}): Promise<FavoritesResponse> {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', String(params.limit));
  if (params?.after) searchParams.set('after', params.after);
  if (params?.before) searchParams.set('before', params.before);

  const query = searchParams.toString();
  return fetchApi(`/favorites${query ? `?${query}` : ''}`, { headers: authHeaders(token) });
}

// Add favorite
async function addFavorite(token: string, blockId: string): Promise<Favorite> {
  return fetchApi('/favorites', {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ block_id: blockId }),
  });
}

// Remove favorite
async function removeFavorite(token: string, blockId: string): Promise<void> {
  await fetchApi(`/favorites/${blockId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
}
```

### User Profile API

```typescript
interface User {
  id: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: 'user' | 'admin';
  created_at: string;
  updated_at: string;
}

// Get current user
async function getCurrentUser(token: string): Promise<User> {
  return fetchApi('/users/me', { headers: authHeaders(token) });
}

// Update profile
async function updateProfile(
  token: string,
  data: { display_name?: string; avatar_url?: string }
): Promise<User> {
  return fetchApi('/users/me', {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
}
```

---

## Swift Templates

### Base Client

```swift
import Foundation

enum APIError: Error {
    case invalidURL
    case requestFailed(String)
    case decodingFailed
}

class StackeyClient {
    static let shared = StackeyClient()

    private let baseURL: URL
    private var authToken: String?

    private init() {
        // Configure with your Supabase URL
        self.baseURL = URL(string: "https://YOUR_PROJECT.supabase.co/functions/v1")!
    }

    func setAuthToken(_ token: String?) {
        self.authToken = token
    }

    private func request<T: Decodable>(
        _ endpoint: String,
        method: String = "GET",
        body: Data? = nil,
        requiresAuth: Bool = false
    ) async throws -> T {
        guard let url = URL(string: endpoint, relativeTo: baseURL) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if requiresAuth, let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = body
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.requestFailed("Invalid response")
        }

        if httpResponse.statusCode >= 400 {
            if let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data) {
                throw APIError.requestFailed(errorResponse.error)
            }
            throw APIError.requestFailed("Request failed with status \(httpResponse.statusCode)")
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(T.self, from: data)
    }
}

struct ErrorResponse: Decodable {
    let error: String
}
```

### Models

```swift
struct Block: Codable, Identifiable {
    let id: String
    let title: String
    let description: String?
    let subtitle: String?
    let promptText: String?
    let gradientId: Int
    let icon: String?
    let tags: [String]
    let isPublic: Bool
    let createdBy: String?
    let createdAt: Date
    let updatedAt: Date
    let blockMedia: [BlockMedia]?

    enum CodingKeys: String, CodingKey {
        case id, title, description, subtitle, tags, icon
        case promptText = "prompt_text"
        case gradientId = "gradient_id"
        case isPublic = "is_public"
        case createdBy = "created_by"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case blockMedia = "block_media"
    }
}

struct BlockMedia: Codable, Identifiable {
    let id: String
    let type: MediaType
    let url: String
    let filename: String?
    let sortOrder: Int

    enum MediaType: String, Codable {
        case image, video
    }

    enum CodingKeys: String, CodingKey {
        case id, type, url, filename
        case sortOrder = "sort_order"
    }
}

struct PageInfo: Decodable {
    let hasNextPage: Bool
    let hasPreviousPage: Bool
    let startCursor: String?
    let endCursor: String?
    let totalCount: Int
}

struct BlocksResponse: Decodable {
    let data: [Block]
    let pageInfo: PageInfo
}

struct FavoritesResponse: Decodable {
    let data: [Block]
    let pageInfo: PageInfo
}

struct User: Codable, Identifiable {
    let id: String
    let email: String
    let displayName: String?
    let avatarUrl: String?
    let role: String
    let createdAt: Date
    let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, email, role
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}
```

### Blocks API

```swift
extension StackeyClient {
    func getBlocks(
        tags: [String]? = nil,
        search: String? = nil,
        limit: Int = 20,
        after: String? = nil,
        before: String? = nil
    ) async throws -> BlocksResponse {
        var components = URLComponents(string: "/blocks")!
        var queryItems: [URLQueryItem] = []

        if let tags = tags, !tags.isEmpty {
            queryItems.append(URLQueryItem(name: "tags", value: tags.joined(separator: ",")))
        }
        if let search = search {
            queryItems.append(URLQueryItem(name: "search", value: search))
        }
        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))
        if let after = after {
            queryItems.append(URLQueryItem(name: "after", value: after))
        }
        if let before = before {
            queryItems.append(URLQueryItem(name: "before", value: before))
        }

        components.queryItems = queryItems
        return try await request(components.string!)
    }

    func getBlock(id: String) async throws -> Block {
        return try await request("/blocks/\(id)")
    }
}
```

### Favorites API

```swift
extension StackeyClient {
    func getFavorites(
        limit: Int = 20,
        after: String? = nil,
        before: String? = nil
    ) async throws -> FavoritesResponse {
        var components = URLComponents(string: "/favorites")!
        var queryItems: [URLQueryItem] = []

        queryItems.append(URLQueryItem(name: "limit", value: String(limit)))
        if let after = after {
            queryItems.append(URLQueryItem(name: "after", value: after))
        }
        if let before = before {
            queryItems.append(URLQueryItem(name: "before", value: before))
        }

        components.queryItems = queryItems
        return try await request(components.string!, requiresAuth: true)
    }

    func addFavorite(blockId: String) async throws {
        struct Body: Encodable {
            let block_id: String
        }
        let body = try JSONEncoder().encode(Body(block_id: blockId))
        let _: EmptyResponse = try await request(
            "/favorites",
            method: "POST",
            body: body,
            requiresAuth: true
        )
    }

    func removeFavorite(blockId: String) async throws {
        let _: EmptyResponse = try await request(
            "/favorites/\(blockId)",
            method: "DELETE",
            requiresAuth: true
        )
    }
}

struct EmptyResponse: Decodable {
    let success: Bool?
}
```

---

## Step 3: Write Files

Write the generated code to the appropriate location in the user's project:
- TypeScript: `src/lib/stackey-client.ts` or similar
- Swift: `Sources/StackeyClient.swift` or similar

Ask user for preferred file location if not obvious from project structure.

## Step 4: Provide Usage Examples

After writing the code, provide usage examples specific to the platform:

**TypeScript:**
```typescript
// In a React component or server action
const { data: blocks, pageInfo } = await getBlocks({ tags: ['camera'], limit: 10 });

// Load next page using cursor
if (pageInfo.hasNextPage && pageInfo.endCursor) {
  const nextPage = await getBlocks({ tags: ['camera'], limit: 10, after: pageInfo.endCursor });
}
```

**Swift:**
```swift
// In a SwiftUI view
let response = try await StackeyClient.shared.getBlocks(tags: ["camera"])
let blocks = response.data

// Load next page using cursor
if response.pageInfo.hasNextPage, let cursor = response.pageInfo.endCursor {
    let nextPage = try await StackeyClient.shared.getBlocks(tags: ["camera"], after: cursor)
}
```
