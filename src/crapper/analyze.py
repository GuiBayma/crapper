"""Turn source files and coverage into CRAP entries."""

from pathlib import Path

from crapper.coverage import CoverageBundle
from crapper.crap import make_entry, sort_entries
from crapper.discover import language_of
from crapper.languages import functions_in_file
from crapper.model import Entry, Function


def _entry(bundle: CoverageBundle | None, function: Function) -> Entry:
    """Score unreported functions at 0%, rather than N/A, to sort with scored rows."""

    if bundle is None:
        return make_entry(function, None)
    coverage = bundle.percent_for(function)
    if coverage is None:
        coverage = 0.0
    return make_entry(function, coverage, bundle.uncovered_lines_for(function))


def _source_path(file: Path, root: Path) -> str:
    try:
        return file.relative_to(root).as_posix()
    except ValueError:
        return file.as_posix()


def analyze_files(
    files: list[Path],
    project_root: Path,
    bundle: CoverageBundle | None,
) -> list[Entry]:
    root = project_root.resolve()
    if bundle is not None:
        bundle.bind_sources([_source_path(file.resolve(), root) for file in files])
    entries: list[Entry] = []
    for file in files:
        file = file.resolve()
        language = language_of(file)
        if language is None:
            continue
        source = file.read_text(encoding="utf-8", errors="replace")
        try:
            relative = file.relative_to(root).as_posix()
        except ValueError:
            relative = file.as_posix()
        for function in functions_in_file(language, source, relative, str(root)):
            entries.append(_entry(bundle, function))
    return sort_entries(entries)
