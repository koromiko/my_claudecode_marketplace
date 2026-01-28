#!/bin/bash
# list-scripts.sh - List available scripts from package manager
# Usage: list-scripts.sh <project-path>
# Output format:
#   SCRIPTS:<name1>:<command1>,<name2>:<command2>,...
#   or SCRIPTS:none if no scripts found

set -euo pipefail

PROJECT_PATH="${1:-.}"

# Normalize path
PROJECT_PATH=$(cd "$PROJECT_PATH" 2>/dev/null && pwd) || {
    echo "SCRIPTS:none"
    exit 0
}

# For Node.js projects
if [ -f "$PROJECT_PATH/package.json" ]; then
    # Extract scripts section using grep/sed (no jq dependency)
    # First check if scripts section exists
    if grep -q '"scripts"' "$PROJECT_PATH/package.json" 2>/dev/null; then
        # Extract scripts block and parse name:command pairs
        SCRIPTS=$(sed -n '/"scripts"/,/^  }/p' "$PROJECT_PATH/package.json" 2>/dev/null | \
            grep -E '^\s*"[^"]+"\s*:\s*"[^"]*"' | \
            head -20 | \
            sed 's/^\s*"\([^"]*\)"\s*:\s*"\([^"]*\)".*/\1:\2/' | \
            tr '\n' ',' | \
            sed 's/,$//')

        if [ -n "$SCRIPTS" ]; then
            echo "SCRIPTS:$SCRIPTS"
            exit 0
        fi
    fi
    echo "SCRIPTS:none"
    exit 0
fi

# For Cargo projects
if [ -f "$PROJECT_PATH/Cargo.toml" ]; then
    # Cargo uses standard commands
    SCRIPTS="run:cargo run,build:cargo build,test:cargo test,check:cargo check"
    # Check if cargo-watch might be available
    if grep -q 'cargo-watch' "$PROJECT_PATH/Cargo.toml" 2>/dev/null; then
        SCRIPTS="$SCRIPTS,watch:cargo watch -x run"
    fi
    echo "SCRIPTS:$SCRIPTS"
    exit 0
fi

# For Go projects
if [ -f "$PROJECT_PATH/go.mod" ]; then
    SCRIPTS="run:go run .,build:go build,test:go test ./..."
    # Check for air (hot reload)
    if [ -f "$PROJECT_PATH/.air.toml" ]; then
        SCRIPTS="$SCRIPTS,dev:air"
    fi
    echo "SCRIPTS:$SCRIPTS"
    exit 0
fi

# For Python projects
if [ -f "$PROJECT_PATH/pyproject.toml" ] || [ -f "$PROJECT_PATH/requirements.txt" ]; then
    if [ -f "$PROJECT_PATH/manage.py" ]; then
        # Django project
        echo "SCRIPTS:runserver:python manage.py runserver,migrate:python manage.py migrate,test:python manage.py test,shell:python manage.py shell"
    elif [ -f "$PROJECT_PATH/pyproject.toml" ] && grep -q "uvicorn" "$PROJECT_PATH/pyproject.toml" 2>/dev/null; then
        # FastAPI project
        echo "SCRIPTS:dev:uvicorn main:app --reload,test:pytest"
    elif [ -f "$PROJECT_PATH/pyproject.toml" ] && grep -q "flask" "$PROJECT_PATH/pyproject.toml" 2>/dev/null; then
        # Flask project
        echo "SCRIPTS:dev:flask run --debug,test:pytest"
    else
        echo "SCRIPTS:run:python main.py,test:pytest"
    fi
    exit 0
fi

# For Ruby projects
if [ -f "$PROJECT_PATH/Gemfile" ]; then
    if [ -f "$PROJECT_PATH/config.ru" ] || [ -d "$PROJECT_PATH/app" ]; then
        # Rails-like project
        echo "SCRIPTS:server:bundle exec rails server,console:bundle exec rails console,test:bundle exec rspec"
    else
        echo "SCRIPTS:run:bundle exec ruby main.rb"
    fi
    exit 0
fi

echo "SCRIPTS:none"
