"""Shared utilities for eBird-related services (export, region comparison)."""
import re



def common_name_from_species(name: str) -> str:
    """Extract common name from 'Scientific (Common)' or return as-is."""
    if not name or not isinstance(name, str):
        return ""
    name = name.strip()
    match = re.search(r"\(([^)]+)\)\s*$", name)
    if match:
        return match.group(1).strip()
    return name
