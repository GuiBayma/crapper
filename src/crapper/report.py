from crapper.model import Entry


def _format_coverage(coverage: float | None) -> str:
    if coverage is None:
        return "  N/A "
    return f"{coverage:5.1f}%"


def _format_crap(score: float | None) -> str:
    if score is None:
        return "     N/A"
    return f"{score:8.1f}"


def _format_line_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def _format_line_ranges(lines: tuple[int, ...]) -> str:
    ranges: list[str] = []
    start = end = lines[0]
    for line in lines[1:]:
        if line == end + 1:
            end = line
            continue
        ranges.append(_format_line_range(start, end))
        start = end = line
    ranges.append(_format_line_range(start, end))
    return ", ".join(ranges)


def format_report(entries: list[Entry]) -> str:
    name_width = 30
    namespace_width = 35
    if entries:
        name_width = max(name_width, min(48, max(len(entry.name) for entry in entries)))
        namespace_width = max(
            namespace_width, min(72, max(len(entry.namespace) for entry in entries))
        )
    header = (
        f"{'Function':<{name_width}} {'Namespace':<{namespace_width}} "
        f"{'CC':>4} {'Cov%':>7} {'CRAP':>8}"
    )
    separator = "-" * len(header)
    languages = ", ".join(sorted({entry.language for entry in entries}))
    lines = ["CRAP Report", "==========="]
    if languages:
        lines.append(f"Languages: {languages}")
        lines.append("")
    lines.extend([header, separator])
    for entry in entries:
        lines.append(
            f"{entry.name:<{name_width}} {entry.namespace:<{namespace_width}} "
            f"{entry.complexity:4d} {_format_coverage(entry.coverage)} "
            f"{_format_crap(entry.crap)}"
        )
        if entry.uncovered_lines:
            lines.append(
                f"  Uncovered lines: {entry.path}:{_format_line_ranges(entry.uncovered_lines)}"
            )
    lines.append("")
    return "\n".join(lines)
