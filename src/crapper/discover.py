"""Find source files and decide which language each one is written in."""

import os
from pathlib import Path

EXTENSIONS = {
    ".clj": "clojure",
    ".cljc": "clojure",
    ".cljs": "clojure",
    ".bb": "clojure",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".mjs": "typescript",
    ".cjs": "typescript",
    ".rs": "rust",
    ".py": "python",
}

# Directories whose name starts with a dot are skipped too: they hold VCS data,
# editor settings, and framework output such as .svelte-kit, .next, and .nuxt.
SKIP_DIRS = {
    "venv",
    "node_modules",
    "vendor",
    "target",
    "dist",
    "build",
    "out",
    "coverage",
    "testdata",
    "__pycache__",
}

TEST_DIRS = {"test", "tests", "spec", "specs", "__tests__"}

GO_TEST_SUFFIX = "_test.go"
CLOJURE_TEST_SUFFIXES = ("_test.clj", "_test.cljc", "_test.cljs", "_test.bb")
JS_TEST_SUFFIXES = (
    ".test.ts",
    ".spec.ts",
    ".test.tsx",
    ".spec.tsx",
    ".test.mts",
    ".spec.mts",
    ".test.cts",
    ".spec.cts",
    ".test.js",
    ".spec.js",
    ".test.jsx",
    ".spec.jsx",
    ".test.mjs",
    ".spec.mjs",
    ".test.cjs",
    ".spec.cjs",
)


def language_of(path: str | Path) -> str | None:
    file_path = Path(path)
    name = file_path.name
    if name.endswith(".d.ts"):
        return None
    return EXTENSIONS.get(file_path.suffix)


def is_test_file(path: str | Path) -> bool:
    file_path = Path(path)
    name = file_path.name
    if name.endswith(GO_TEST_SUFFIX):
        return True
    if name.endswith(CLOJURE_TEST_SUFFIXES):
        return True
    if name.endswith(JS_TEST_SUFFIXES):
        return True
    if name == "conftest.py":
        return True
    if name.endswith("_test.py") or (name.startswith("test_") and name.endswith(".py")):
        return True
    return any(part in TEST_DIRS for part in file_path.parts)


def is_skipped_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRS


def in_skipped_dir(path: Path, root: Path) -> bool:
    """Whether a directory between `root` and `path` is one a walk skips."""

    return any(is_skipped_dir(name) for name in path.relative_to(root).parent.parts)


def _walk(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root]
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name for name in dirnames if not is_skipped_dir(name) and name not in TEST_DIRS
        ]
        for name in filenames:
            path = Path(dirpath) / name
            if language_of(path) is None or is_test_file(path):
                continue
            found.append(path)
    return found


def iter_source_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        for path in _walk(root):
            files.add(path.resolve())
    return sorted(files, key=lambda path: path.as_posix())
