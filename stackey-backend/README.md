# Stackey Backend Plugin

Claude Code plugin providing skills and agents for working with the StackeyBackend Supabase API.

## Overview

This plugin helps developers understand and integrate with the Stackey video generation backend, which provides APIs for managing blocks (camera movements, angles, styles), media attachments, user favorites, and authentication.

## Components

### Skills

| Skill | Trigger Keywords | Purpose |
|-------|------------------|---------|
| **stackey-api** | "Stackey API", "blocks endpoint", "favorites endpoint" | API endpoint documentation |
| **stackey-auth** | "Stackey authentication", "JWT token", "admin access" | Authentication patterns |
| **stackey-database** | "Stackey database", "blocks table", "RLS policies" | Database schema reference |

### Agents

| Agent | Trigger | Purpose |
|-------|---------|---------|
| **stackey-integration** | "integrate with Stackey", "create Stackey client" | Generates TypeScript/Swift API client code |

## API Quick Reference

| Endpoint | Methods | Auth | Purpose |
|----------|---------|------|---------|
| `/blocks` | GET, POST | Public/Admin | List/create blocks |
| `/blocks/:id` | GET, PATCH, DELETE | Public/Admin | Single block operations |
| `/users/me` | GET, PATCH | User | Profile management |
| `/favorites` | GET, POST, DELETE | User | Favorites management |
| `/block-media` | POST, DELETE | Admin | Media upload/delete |

## Usage Examples

### Ask about the API

> "How do I list blocks with tag filtering?"

The `stackey-api` skill will activate and provide endpoint documentation with curl examples.

### Ask about authentication

> "What authentication does Stackey use?"

The `stackey-auth` skill will explain JWT tokens, user/admin roles, and OAuth flows.

### Generate integration code

> "Help me integrate with the Stackey API in Swift"

The `stackey-integration` agent will generate a type-safe Swift client with models and API methods.

## Structure

```
stackey-backend/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── skills/
│   ├── stackey-api/         # API documentation skill
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── endpoints.md
│   ├── stackey-auth/        # Authentication skill
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── auth-patterns.md
│   └── stackey-database/    # Database schema skill
│       ├── SKILL.md
│       └── references/
│           └── schema.md
├── agents/
│   └── stackey-integration.md  # Code generation agent
└── README.md
```

## Related Resources

- StackeyBackend source: `/Users/neo/Projects/Stackey/StackeyBackend`
- Local Supabase Studio: `http://127.0.0.1:54323`
- Bruno API tests: `StackeyBackend/bruno/`
