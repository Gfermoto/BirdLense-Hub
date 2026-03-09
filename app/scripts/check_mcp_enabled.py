#!/usr/bin/env python3
"""Check if MCP is enabled in config. Exit 0 if enabled, 1 otherwise.
Paths are for container; on host use APP_CONFIG_DIR or fallback to ./app_config."""
import os
import yaml

def main():
    base = os.environ.get('APP_CONFIG_DIR', '/app/app_config')
    if not os.path.isdir(base):
        base = os.path.join(os.path.dirname(__file__), '..', 'app_config')
    for name in ('user_config.yaml', 'default_config.yaml'):
        path = os.path.join(base, name)
        try:
            with open(path) as f:
                c = yaml.safe_load(f) or {}
            mcp = c.get('mcp') or {}
            if mcp.get('enabled'):
                return 0
        except (FileNotFoundError, OSError, yaml.YAMLError):
            pass
    return 1

if __name__ == '__main__':
    exit(main())
