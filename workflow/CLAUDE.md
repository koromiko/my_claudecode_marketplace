# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

The `workflow` plugin provides workflow utilities for Claude Code sessions.

## Commands

- **`retrospective`** — Analyzes the current session, identifies improvement opportunities, and suggests changes to CLAUDE.md, user instructions, and auto memory. A standalone utility invoked as `/workflow:retrospective`.

## Notes

- `retrospective` reads `~/.claude/CLAUDE.md`, `~/.claude/rules/`, and the project's auto memory directory. It requires only `Read`, `Glob`, and `Grep` — no write permissions.
- The command is referenced by `claude-usage-analyzer/commands/chronicle.md` as the final step after generating the session timeline HTML.
