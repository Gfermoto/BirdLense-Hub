---
name: "🔴 Feature: Centralized Config with Pydantic"
about: Replace scattered .env usage with validated Pydantic Settings
labels: ["enhancement", "backend", "config"]
---

## Problem
Configuration is scattered across multiple `.env` files without validation.

## Goals
- [ ] Create unified `settings.py` using `pydantic-settings`.
- [ ] Validate all environment variables on startup.
- [ ] Remove direct `os.getenv` calls.
