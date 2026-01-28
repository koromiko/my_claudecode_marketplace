#!/bin/bash
# detect-project.sh - Detect project type and structure
# Usage: detect-project.sh <project-path>
# Output format:
#   PROJECT_TYPE:<type>
#   PACKAGE_MANAGER:<npm|yarn|pnpm|cargo|go|python|none>
#   HAS_DOCKER:true|false
#   HAS_MONOREPO:true|false
#   WORKSPACES:<workspace1>,<workspace2>,...
#   FRAMEWORKS:<framework1>,<framework2>,...

set -euo pipefail

PROJECT_PATH="${1:-.}"

# Normalize path
PROJECT_PATH=$(cd "$PROJECT_PATH" 2>/dev/null && pwd) || {
    echo "PROJECT_TYPE:error"
    echo "ERROR:INVALID_PATH"
    exit 1
}

# Initialize variables
PROJECT_TYPE="unknown"
PACKAGE_MANAGER="none"
HAS_DOCKER="false"
HAS_MONOREPO="false"
WORKSPACES=""
FRAMEWORKS=""

# Detect package manager
if [ -f "$PROJECT_PATH/package-lock.json" ]; then
    PACKAGE_MANAGER="npm"
elif [ -f "$PROJECT_PATH/yarn.lock" ]; then
    PACKAGE_MANAGER="yarn"
elif [ -f "$PROJECT_PATH/pnpm-lock.yaml" ]; then
    PACKAGE_MANAGER="pnpm"
elif [ -f "$PROJECT_PATH/bun.lockb" ]; then
    PACKAGE_MANAGER="bun"
elif [ -f "$PROJECT_PATH/Cargo.toml" ]; then
    PACKAGE_MANAGER="cargo"
elif [ -f "$PROJECT_PATH/go.mod" ]; then
    PACKAGE_MANAGER="go"
elif [ -f "$PROJECT_PATH/requirements.txt" ] || [ -f "$PROJECT_PATH/pyproject.toml" ]; then
    PACKAGE_MANAGER="python"
fi

# Detect Docker
if [ -f "$PROJECT_PATH/docker-compose.yml" ] || [ -f "$PROJECT_PATH/docker-compose.yaml" ] || [ -f "$PROJECT_PATH/compose.yml" ] || [ -f "$PROJECT_PATH/compose.yaml" ] || [ -f "$PROJECT_PATH/Dockerfile" ]; then
    HAS_DOCKER="true"
fi

# Detect Node.js project details
if [ -f "$PROJECT_PATH/package.json" ]; then
    # Check for workspaces (mono-repo)
    if grep -q '"workspaces"' "$PROJECT_PATH/package.json" 2>/dev/null; then
        HAS_MONOREPO="true"
        # Extract workspace directory patterns
        WORKSPACES=$(grep -A 20 '"workspaces"' "$PROJECT_PATH/package.json" | grep -oE '"[^"]+/?\*?"' | tr -d '"' | grep -v '^\[' | tr '\n' ',' | sed 's/,$//')
    fi

    # Check for pnpm workspaces
    if [ -f "$PROJECT_PATH/pnpm-workspace.yaml" ]; then
        HAS_MONOREPO="true"
    fi

    # Check for Turborepo
    if [ -f "$PROJECT_PATH/turbo.json" ]; then
        HAS_MONOREPO="true"
    fi

    # Check for Nx
    if [ -f "$PROJECT_PATH/nx.json" ]; then
        HAS_MONOREPO="true"
    fi

    # Detect frameworks from dependencies
    DEPS=$(cat "$PROJECT_PATH/package.json" 2>/dev/null || echo "{}")

    if echo "$DEPS" | grep -qE '"react"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}react,"
    fi
    if echo "$DEPS" | grep -qE '"vue"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}vue,"
    fi
    if echo "$DEPS" | grep -qE '"@angular/core"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}angular,"
    fi
    if echo "$DEPS" | grep -qE '"svelte"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}svelte,"
    fi
    if echo "$DEPS" | grep -qE '"next"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}nextjs,"
    fi
    if echo "$DEPS" | grep -qE '"nuxt"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}nuxt,"
    fi
    if echo "$DEPS" | grep -qE '"vite"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}vite,"
    fi
    if echo "$DEPS" | grep -qE '"express"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}express,"
    fi
    if echo "$DEPS" | grep -qE '"fastify"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}fastify,"
    fi
    if echo "$DEPS" | grep -qE '"@nestjs/core"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}nestjs,"
    fi
    if echo "$DEPS" | grep -qE '"koa"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}koa,"
    fi
    if echo "$DEPS" | grep -qE '"hono"' 2>/dev/null; then
        FRAMEWORKS="${FRAMEWORKS}hono,"
    fi

    FRAMEWORKS=$(echo "$FRAMEWORKS" | sed 's/,$//')
fi

# Determine project type based on detected frameworks
if [ "$HAS_MONOREPO" = "true" ]; then
    PROJECT_TYPE="monorepo"
elif echo "$FRAMEWORKS" | grep -qE "(react|vue|angular|svelte|nextjs|nuxt)" && echo "$FRAMEWORKS" | grep -qE "(express|fastify|nestjs|koa|hono)"; then
    PROJECT_TYPE="fullstack"
elif echo "$FRAMEWORKS" | grep -qE "(react|vue|angular|svelte|nextjs|nuxt|vite)"; then
    PROJECT_TYPE="frontend"
elif echo "$FRAMEWORKS" | grep -qE "(express|fastify|nestjs|koa|hono)"; then
    PROJECT_TYPE="backend"
elif [ "$PACKAGE_MANAGER" = "cargo" ]; then
    PROJECT_TYPE="rust"
elif [ "$PACKAGE_MANAGER" = "go" ]; then
    PROJECT_TYPE="go"
elif [ "$PACKAGE_MANAGER" = "python" ]; then
    PROJECT_TYPE="python"
elif [ "$HAS_DOCKER" = "true" ]; then
    PROJECT_TYPE="docker"
fi

# Output results
echo "PROJECT_TYPE:$PROJECT_TYPE"
echo "PACKAGE_MANAGER:$PACKAGE_MANAGER"
echo "HAS_DOCKER:$HAS_DOCKER"
echo "HAS_MONOREPO:$HAS_MONOREPO"
echo "WORKSPACES:$WORKSPACES"
echo "FRAMEWORKS:$FRAMEWORKS"
