#!/usr/bin/env python3
"""Rewrite legacy ./UPPERCASE.md links in docs/ for MkDocs --strict.

  python3 scripts/public/rewrite_docs_internal_links.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
SUBDIRS = ("user", "contributor", "ru")

REPO_MAIN = "https://github.com/Gfermoto/BirdLense-Hub/blob/main"

PROJECT_URL = {
    "project/openapi.md": f"{REPO_MAIN}/app/web/openapi.yaml",
    "project/changelog.md": f"{REPO_MAIN}/CHANGELOG.md",
    "project/root-readme.md": f"{REPO_MAIN}/README.md",
    "project/contributing.md": f"{REPO_MAIN}/CONTRIBUTING.md",
    "project/security-policy.md": f"{REPO_MAIN}/SECURITY.md",
    "README.md": f"{REPO_MAIN}/README.md",
}

USER_TO_CONTRIBUTOR: dict[str, str] = {
    "ARCHITECTURE.MD": "contributor/architecture.md",
    "TESTING.MD": "contributor/testing.md",
    "CI_AND_QUALITY.MD": "contributor/ci-and-quality.md",
    "LOCAL_DEV.MD": "contributor/local-dev.md",
    "MCP_SETUP.MD": "contributor/mcp-setup.md",
    "SECURITY.MD": "contributor/security.md",
    "ACCESS_CONTROL.MD": "contributor/access-control.md",
    "API.MD": "contributor/api.md",
    "API-ERRORS.MD": "contributor/api-errors.md",
    "DATASETS.MD": "contributor/datasets.md",
    "REPOSITORY_LAYOUT.MD": "contributor/repository-layout.md",
    "ROADMAP.MD": "contributor/roadmap.md",
}

CONTRIBUTOR_TO_USER: dict[str, str] = {
    "CONFIGURATION.MD": "user/configuration.md",
    "INSTALL.MD": "user/install.md",
    "OVERVIEW.MD": "user/overview.md",
    "QUICKSTART.MD": "user/quickstart.md",
    "DEPLOY_SERVER.MD": "user/deploy-server.md",
    "PROCESSOR_PERFORMANCE.MD": "user/processor-performance.md",
    "TROUBLESHOOTING.MD": "user/troubleshooting.md",
    "RUNBOOKS.MD": "user/runbooks.md",
    "PUBLIC_RECORDINGS.MD": "user/public-recordings.md",
    "RECOVERY_CONFIG.MD": "user/recovery-config.md",
    "FEATURES.MD": "user/features.md",
    "SCENARIOS.MD": "user/scenarios.md",
    "GLOSSARY.MD": "user/glossary.md",
}

RU_TO_EN_DOC: dict[str, str] = {
    "OVERVIEW.MD": "user/overview.md",
    "QUICKSTART.MD": "user/quickstart.md",
    "PUBLIC_RECORDINGS.MD": "user/public-recordings.md",
    "RECOVERY_CONFIG.MD": "user/recovery-config.md",
    "SCENARIOS.MD": "user/scenarios.md",
    "ROADMAP.MD": "contributor/roadmap.md",
    "CONFIGURATION.MD": "user/configuration.md",
    "TROUBLESHOOTING.MD": "user/troubleshooting.md",
    "RUNBOOKS.MD": "user/runbooks.md",
    "PROCESSOR_PERFORMANCE.MD": "user/processor-performance.md",
    "DEPLOY_SERVER.MD": "user/deploy-server.md",
    "INSTALL.MD": "user/install.md",
    "ACCESS_CONTROL.MD": "contributor/access-control.md",
    "API.MD": "contributor/api.md",
    "GLOSSARY.MD": "user/glossary.md",
    "SECURITY.MD": "contributor/security.md",
    "ARCHITECTURE.MD": "contributor/architecture.md",
    "LOCAL_DEV.MD": "contributor/local-dev.md",
    "MCP_SETUP.MD": "contributor/mcp-setup.md",
    "TESTING.MD": "contributor/testing.md",
}

LINK_RE = re.compile(r"\]\((\./[^)]+)\)")
REF_RE = re.compile(r"\]\((reference/[^)]+)\)")
DOCS_RESOLVED = DOCS.resolve()


def _kebab_file(name: str) -> str:
    """Legacy UPPER_SNAKE.md -> lower-kebab.md for on-disk names."""
    p = Path(name)
    return p.stem.replace("_", "-").lower() + p.suffix.lower()


def _under_docs(p: Path) -> bool:
    try:
        rp = p.resolve()
    except OSError:
        return False
    return rp == DOCS_RESOLVED or DOCS_RESOLVED in rp.parents


def _split_anchor(href: str) -> tuple[str, str]:
    if "#" in href:
        base, frag = href.split("#", 1)
        return base, "#" + frag
    return href, ""


def _relpath(from_file: Path, target: Path) -> str:
    rel = os.path.relpath(target, from_file.parent).replace(os.sep, "/")
    if not rel.startswith("."):
        rel = "./" + rel
    return rel


def _resolve(from_file: Path, path_part: str) -> Path | None:
    d = from_file.parent
    name = Path(path_part).name
    sub = Path(path_part).parent
    candidates: list[Path] = []

    if str(sub) != ".":
        candidates.append(d / path_part)
        candidates.append(d / sub / name.lower())
        candidates.append(d / sub / _kebab_file(name))
    else:
        candidates.append(d / path_part)
        candidates.append(d / name.lower())
        candidates.append(d / _kebab_file(name))

    if d.name == "user" and name.lower().endswith(".ru.md"):
        candidates.append(DOCS / "ru" / _kebab_file(name))
        candidates.append(DOCS / "ru" / name.lower())

    key = name.upper()
    if d.name == "user" and key in USER_TO_CONTRIBUTOR:
        candidates.append(DOCS / USER_TO_CONTRIBUTOR[key])

    if d.name == "contributor" and key in CONTRIBUTOR_TO_USER:
        candidates.append(DOCS / CONTRIBUTOR_TO_USER[key])

    if d.name == "contributor" and name.lower().endswith(".ru.md"):
        candidates.append(DOCS / "ru" / _kebab_file(name))
        candidates.append(DOCS / "ru" / name.lower())

    if d.name == "ru":
        if key in RU_TO_EN_DOC:
            candidates.append(DOCS / RU_TO_EN_DOC[key])
        if name.lower().endswith(".ru.md"):
            candidates.append(d / name.lower())
            candidates.append(d / _kebab_file(name))

    for c in candidates:
        if c.is_file() and _under_docs(c):
            return c.resolve()
    return None


def _rewrite_href(from_file: Path, href: str) -> str:
    if "://" in href:
        return href

    if href.startswith("reference/"):
        base, anchor = _split_anchor(href)
        if base == "reference/openapi.md":
            return f"{REPO_MAIN}/app/web/openapi.yaml" + anchor
        return href

    if not href.startswith("./"):
        return href

    path_part, anchor = _split_anchor(href[2:])

    if path_part in PROJECT_URL:
        return PROJECT_URL[path_part] + anchor

    hit = _resolve(from_file, path_part)
    if hit is not None:
        return _relpath(from_file, hit) + anchor

    return href


def process_file(md: Path) -> bool:
    text = md.read_text(encoding="utf-8")
    orig = text

    def repl(m: re.Match[str]) -> str:
        return "](" + _rewrite_href(md, m.group(1)) + ")"

    def repl_ref(m: re.Match[str]) -> str:
        return "](" + _rewrite_href(md, m.group(1)) + ")"

    text = LINK_RE.sub(repl, text)
    text = REF_RE.sub(repl_ref, text)
    if text != orig:
        md.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    for sub in SUBDIRS:
        d = DOCS / sub
        if not d.is_dir():
            continue
        for md in sorted(d.rglob("*.md")):
            if process_file(md):
                changed += 1
                print("updated", md.relative_to(ROOT))
    for name in ("index.md",):
        p = DOCS / name
        if p.is_file() and process_file(p):
            changed += 1
            print("updated", p.relative_to(ROOT))
    print(f"done, files touched: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
