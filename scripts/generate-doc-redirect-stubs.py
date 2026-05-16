#!/usr/bin/env python3
"""Generate docs/*.md redirect stubs and mkdocs redirect_maps snippet.

Run from repository root:
  python3 scripts/generate-doc-redirect-stubs.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Old flat name -> new path under docs/
MIGRATED: dict[str, str] = {
    # User guide (EN)
    "README.md": "index.md",
    "OVERVIEW.md": "user/overview.md",
    "QUICKSTART.md": "user/quickstart.md",
    "INSTALL.md": "user/install.md",
    "DEPLOY_SERVER.md": "user/deploy-server.md",
    "PUBLIC_RECORDINGS.md": "user/public-recordings.md",
    "SCENARIOS.md": "user/scenarios.md",
    "CONFIGURATION.md": "user/configuration.md",
    "FEATURES.md": "user/features.md",
    "PROCESSOR_PERFORMANCE.md": "user/processor-performance.md",
    "TROUBLESHOOTING.md": "user/troubleshooting.md",
    "RUNBOOKS.md": "user/runbooks.md",
    "RECOVERY_CONFIG.md": "user/recovery-config.md",
    "GLOSSARY.md": "user/glossary.md",
    # Contributor (EN)
    "ARCHITECTURE.md": "contributor/architecture.md",
    "API.md": "contributor/api.md",
    "API_ERRORS.md": "contributor/api-errors.md",
    "ACCESS_CONTROL.md": "contributor/access-control.md",
    "MCP_SETUP.md": "contributor/mcp-setup.md",
    "LOCAL_DEV.md": "contributor/local-dev.md",
    "TESTING.md": "contributor/testing.md",
    "CI_AND_QUALITY.md": "contributor/ci-and-quality.md",
    "SECURITY.md": "contributor/security.md",
    "REPOSITORY_LAYOUT.md": "contributor/repository-layout.md",
    "ROADMAP.md": "contributor/roadmap.md",
    "DATASETS.md": "contributor/datasets.md",
    "Documentation.md": "contributor/documentation.md",
    # Russian
    "OVERVIEW.ru.md": "ru/overview.ru.md",
    "QUICKSTART.ru.md": "ru/quickstart.ru.md",
    "INSTALL.ru.md": "ru/install.ru.md",
    "DEPLOY_SERVER.ru.md": "ru/deploy-server.ru.md",
    "PUBLIC_RECORDINGS.ru.md": "ru/public-recordings.ru.md",
    "SCENARIOS.ru.md": "ru/scenarios.ru.md",
    "CONFIGURATION.ru.md": "ru/configuration.ru.md",
    "FEATURES.ru.md": "ru/features.ru.md",
    "PROCESSOR_PERFORMANCE.ru.md": "ru/processor-performance.ru.md",
    "TROUBLESHOOTING.ru.md": "ru/troubleshooting.ru.md",
    "RUNBOOKS.ru.md": "ru/runbooks.ru.md",
    "RECOVERY_CONFIG.ru.md": "ru/recovery-config.ru.md",
    "GLOSSARY.ru.md": "ru/glossary.ru.md",
    "ARCHITECTURE.ru.md": "ru/architecture.ru.md",
    "API.ru.md": "ru/api.ru.md",
    "ACCESS_CONTROL.ru.md": "ru/access-control.ru.md",
    "MCP_SETUP.ru.md": "ru/mcp-setup.ru.md",
    "LOCAL_DEV.ru.md": "ru/local-dev.ru.md",
    "TESTING.ru.md": "ru/testing.ru.md",
    "SECURITY.ru.md": "ru/security.ru.md",
}

# Still under archive/internal/docs-legacy/ (repo-only or deep-dive)
ARCHIVE: dict[str, str] = {
    "POSTGRES_MIGRATION.md": "archive/internal/docs-legacy/POSTGRES_MIGRATION.md",
    "POSTGRES_MIGRATION.ru.md": "archive/internal/docs-legacy/POSTGRES_MIGRATION.ru.md",
    "TRAINING.md": "archive/internal/docs-legacy/TRAINING.md",
    "TRAINING.ru.md": "archive/internal/docs-legacy/TRAINING.ru.md",
    "HEIMDALL.md": "archive/internal/docs-legacy/HEIMDALL.md",
    "HEIMDALL.ru.md": "archive/internal/docs-legacy/HEIMDALL.ru.md",
    "DEFINITION_OF_DONE.md": "archive/internal/docs-legacy/DEFINITION_OF_DONE.md",
    "DEFINITION_OF_DONE.ru.md": "archive/internal/docs-legacy/DEFINITION_OF_DONE.ru.md",
    "UI_SETTINGS_MAP.md": "archive/internal/docs-legacy/UI_SETTINGS_MAP.md",
    "UI_SETTINGS_MAP.ru.md": "archive/internal/docs-legacy/UI_SETTINGS_MAP.ru.md",
    "CODEQL.md": "archive/internal/docs-legacy/CODEQL.md",
    "CODEQL.ru.md": "archive/internal/docs-legacy/CODEQL.ru.md",
    "RUNTIME_COUPLING.md": "archive/internal/docs-legacy/RUNTIME_COUPLING.md",
    "RUNTIME_COUPLING.ru.md": "archive/internal/docs-legacy/RUNTIME_COUPLING.ru.md",
    "CV_ML_PREP.md": "archive/internal/docs-legacy/CV_ML_PREP.md",
    "CV_ML_PREP.ru.md": "archive/internal/docs-legacy/CV_ML_PREP.ru.md",
    "CV_ML_ROADMAP_PHASES.md": "archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.md",
    "CV_ML_ROADMAP_PHASES.ru.md": "archive/internal/docs-legacy/CV_ML_ROADMAP_PHASES.ru.md",
    "ML_DETECTOR_COLAB.md": "archive/internal/docs-legacy/ML_DETECTOR_COLAB.md",
    "ML_DETECTOR_COLAB.ru.md": "archive/internal/docs-legacy/ML_DETECTOR_COLAB.ru.md",
    "SECRETS_ROTATION.md": "archive/internal/docs-legacy/SECRETS_ROTATION.md",
    "SECRETS_ROTATION.ru.md": "archive/internal/docs-legacy/SECRETS_ROTATION.ru.md",
    "SITE_MAP.md": "archive/internal/docs-legacy/SITE_MAP.md",
    "SITE_MAP.ru.md": "archive/internal/docs-legacy/SITE_MAP.ru.md",
    "VERIFICATION.md": "archive/internal/docs-legacy/VERIFICATION.md",
    "VERIFICATION.ru.md": "archive/internal/docs-legacy/VERIFICATION.ru.md",
    "PUBLIC_RELEASE_CHECKLIST.md": "archive/internal/docs-legacy/PUBLIC_RELEASE_CHECKLIST.md",
    "PUBLIC_RELEASE_CHECKLIST.ru.md": "archive/internal/docs-legacy/PUBLIC_RELEASE_CHECKLIST.ru.md",
}

ROOT_FILE: dict[str, str] = {
    "RELEASE_READINESS.md": "release-readiness.md",
    "RELEASE_READINESS.ru.md": "release-readiness.md",
}

# Extra flat names (CHANGELOG / legacy only)
EXTRA: dict[str, str] = {
    "README.ru.md": "docs/ru/index.md",
    "REPOSITORY_LAYOUT.ru.md": "archive/internal/docs-legacy/REPOSITORY_LAYOUT.ru.md",
    "GOVERNANCE.md": "GOVERNANCE.md",
    "GOVERNANCE.ru.md": "archive/internal/docs-legacy/GOVERNANCE.ru.md",
    "VERSIONING.md": "archive/internal/docs-legacy/VERSIONING.md",
    "VERSIONING.ru.md": "archive/internal/docs-legacy/VERSIONING.ru.md",
    "A11Y.md": "archive/internal/docs-legacy/A11Y.md",
    "A11Y.ru.md": "archive/internal/docs-legacy/A11Y.ru.md",
    "HUB_EPICS_TRACKER.md": "archive/internal/docs-legacy/HUB_EPICS_TRACKER.md",
    "HUB_EPICS_TRACKER.ru.md": "archive/internal/docs-legacy/HUB_EPICS_TRACKER.ru.md",
    "UX_TOOLTIPS.md": "archive/internal/docs-legacy/UX_TOOLTIPS.md",
    "UX_TOOLTIPS.ru.md": "archive/internal/docs-legacy/UX_TOOLTIPS.ru.md",
    "PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md": "archive/internal/docs-legacy/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.md",
    "PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md": "archive/internal/docs-legacy/PRE_IMPLEMENTATION_UNKNOWN_TIMELINE.ru.md",
    "CONSILIUM_AUDIT.ru.md": "archive/internal/docs-legacy/CONSILIUM_AUDIT.ru.md",
    "DOMAIN_CONTRACT.md": "archive/internal/docs-legacy/DOMAIN_CONTRACT.md",
    "DOMAIN_CONTRACT.ru.md": "archive/internal/docs-legacy/DOMAIN_CONTRACT.ru.md",
    "GITHUB_SETUP_GH.md": "archive/internal/docs-legacy/GITHUB_SETUP_GH.md",
    "GITHUB_SETUP_GH.ru.md": "archive/internal/docs-legacy/GITHUB_SETUP_GH.ru.md",
    "ML_QUALITY_LOOP.ru.md": "archive/internal/docs-legacy/ML_QUALITY_LOOP.ru.md",
    "SECURITY.ru.md": "docs/ru/security.ru.md",
    "project/changelog.md": "CHANGELOG.md",
}


def resolve_doc_href(filename: str) -> str:
    """Map legacy docs/FILENAME to current repo path (for CHANGELOG links)."""
    if filename in MIGRATED:
        return f"docs/{MIGRATED[filename]}"
    if filename in ARCHIVE:
        return ARCHIVE[filename]
    if filename in ROOT_FILE:
        return ROOT_FILE[filename]
    if filename in EXTRA:
        return EXTRA[filename]
    return f"docs/{filename}"


def fix_changelog_links() -> int:
    import re

    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    orig = text
    count = 0

    def repl_docs(m: re.Match[str]) -> str:
        nonlocal count
        old = m.group(0)
        new = resolve_doc_href(m.group(1))
        if new != old:
            count += 1
        return new

    text = re.sub(r"docs/([A-Za-z0-9_./-]+\.md)", repl_docs, text)
    if text != orig:
        path.write_text(text, encoding="utf-8")
    return count


def title_from_name(name: str) -> str:
    base = name.replace(".ru.md", "").replace(".md", "")
    return base.replace("_", " ").title()


def stub_body(name: str, target: str, *, repo_root: bool = False) -> str:
    title = title_from_name(name)
    if repo_root:
        link = f"../../{target}"
        note = "repository root"
    elif target.startswith("archive/"):
        link = f"../../{target}"
        note = "archived documentation (repo-only)"
    else:
        link = target
        note = "current documentation"
    return f"""# {title} (moved)

> **Do not edit this stub.** It exists for old bookmarks and external links to `docs/{name}`.

This page moved to **{note}**:

**[{target}]({link})**

---

[Documentation index](index.md) · [Contributor guide](contributor/documentation.md)
"""


def write_stub(name: str, target: str, *, repo_root: bool = False) -> None:
    path = DOCS / name
    path.write_text(stub_body(name, target, repo_root=repo_root), encoding="utf-8")


def main() -> None:
    written: list[str] = []
    for name, target in {**MIGRATED, **ARCHIVE}.items():
        write_stub(name, target)
        written.append(name)
    for name, target in ROOT_FILE.items():
        write_stub(name, target, repo_root=True)
        written.append(name)

  # Snippet for mkdocs.yml (manual merge or CI check)
    snippet = ROOT / "docs" / "_meta" / "redirect_maps.yml"
    lines = ["# Generated by scripts/generate-doc-redirect-stubs.py — merge into mkdocs.yml plugins.redirects"]
    for name, target in MIGRATED.items():
        lines.append(f"        '{name}': '{target}'")
    snippet.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {len(written)} redirect stubs under docs/")
    print(f"Wrote redirect map snippet: {snippet.relative_to(ROOT)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix-changelog",
        action="store_true",
        help="Rewrite docs/*.md links in CHANGELOG.md to current paths",
    )
    parser.add_argument(
        "--no-stubs",
        action="store_true",
        help="Skip regenerating redirect stubs under docs/",
    )
    args = parser.parse_args()
    if args.fix_changelog:
        n = fix_changelog_links()
        print(f"CHANGELOG.md: updated {n} doc path(s)")
    if not args.no_stubs:
        main()
