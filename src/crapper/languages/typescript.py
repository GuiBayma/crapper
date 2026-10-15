"""TypeScript, TSX, and JavaScript functions, methods, and complexity.

Decision points follow the same structural rule as crap4java: `if`, loops,
`catch`, `?:`, each `switch` case (including `default`), `&&` / `||`, and the
nullish operators `??` and `?.`. Top-level functions and class methods are
entries. A named function inside one of those (`function f`, or `const f =
() => ...`) is its own entry too, namespaced under its encloser
(`module.outer`, `module.Class.method`), so a factory that returns closures
is scored closure by closure. An inline Express route callback
(`app.get("/users", handler)` and the same methods on a router, including
`use` and `route().get`) is its own entry, named `GET /users`. Other nested
callbacks, and anything declared inside them, stay inside the enclosing
function. A class method's namespace is `module.Class`, which is the
uml-viewer class key. `.js`, `.mjs`, `.cjs`, and `.jsx` use the JavaScript
grammar and these same rules.
"""

from crapper.languages.treesitter import (
    binary_logic,
    child_of_type,
    complexity,
    descendants,
    end_line,
    node_text,
    parse,
    start_line,
)
from crapper.model import Function

_DECISIONS = {
    "if_statement",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "catch_clause",
    "ternary_expression",
    "switch_case",
    "switch_default",
}
_SKIP = {
    "class_declaration",
    "abstract_class_declaration",
    "interface_declaration",
}
_FUNCTION_TYPES = {
    "function_declaration",
    "method_definition",
    "arrow_function",
    "function_expression",
}
_ROUTE_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "all",
    "use",
}
_CALLBACKS = {"arrow_function", "function_expression"}
_JS_SUFFIXES = (".jsx", ".mjs", ".cjs", ".js")


def _is_decision(node) -> bool:
    if node.type in _DECISIONS or binary_logic(node):
        return True
    if node.type == "binary_expression" and any(child.type == "??" for child in node.children):
        return True
    # `a?.b` and `a?.[0]` wrap `?.` in optional_chain. `a?.()` is a bare `?.`
    # in TypeScript and an optional_chain in JavaScript. Count the wrapper
    # once, and a bare token only when nothing wraps it.
    if node.type == "optional_chain":
        return True
    return node.type == "?." and (node.parent is None or node.parent.type != "optional_chain")


def _skip(node) -> bool:
    return node.type in _SKIP


def _grammar(path: str) -> str:
    if path.endswith(".tsx"):
        return "tsx"
    if path.endswith(_JS_SUFFIXES):
        return "javascript"
    return "typescript"


def _strip_root_prefix(relative: str, source_root: str | None) -> str:
    root = (source_root or "").replace("\\", "/").rstrip("/")
    if root and root != "." and relative.startswith(root + "/"):
        return relative[len(root) + 1 :]
    if relative.startswith("./"):
        return relative[2:]
    return relative


def _strip_src_dir(relative: str) -> str:
    if relative.startswith("src/"):
        return relative[4:]
    if "/src/" in relative:
        return relative.split("/src/", 1)[1]
    return relative


def _strip_script_suffix(relative: str) -> str:
    for suffix in (".tsx", ".mts", ".cts", ".jsx", ".mjs", ".cjs", ".ts", ".js"):
        if relative.endswith(suffix):
            return relative[: -len(suffix)]
    return relative


def _module_namespace(path: str, source_root: str | None) -> str:
    relative = path.replace("\\", "/")
    relative = _strip_root_prefix(relative, source_root)
    relative = _strip_src_dir(relative)
    return _strip_script_suffix(relative).replace("/", ".")


def _enclosing_function(node):
    current = node.parent
    while current is not None:
        if current.type in _FUNCTION_TYPES:
            return current
        current = current.parent
    return None


def _declared_name(data: bytes, node) -> str | None:
    """Name of a function node that is declared by name, or None."""

    if node.type in {"function_declaration", "method_definition"}:
        if not _has_body(node):
            return None
        ident = child_of_type(node, "identifier", "property_identifier")
    elif node.type in _CALLBACKS:
        declarator = node.parent
        if (
            declarator is None
            or declarator.type != "variable_declarator"
            or declarator.parent is None
            or declarator.parent.type != "lexical_declaration"
        ):
            return None
        ident = child_of_type(declarator, "identifier")
    else:
        return None
    if ident is None:
        return None
    return node_text(data, ident)


def _class_names(data: bytes, node) -> list[str]:
    names: list[str] = []
    current = node.parent
    while current is not None:
        if current.type in {"class_declaration", "abstract_class_declaration"}:
            ident = child_of_type(current, "type_identifier", "identifier")
            if ident is not None:
                names.append(node_text(data, ident))
        current = current.parent
    names.reverse()
    return names


def _has_body(node) -> bool:
    return child_of_type(node, "statement_block") is not None


def _expression(node):
    current = node
    while current is not None and current.type == "parenthesized_expression":
        current = next(
            (child for child in current.children if child.type not in {"(", ")"}),
            None,
        )
    return current


def _call_callee(call):
    for child in call.children:
        if child.type != "arguments":
            return child
    return None


def _property_name(data: bytes, node) -> str | None:
    if node is None or node.type != "member_expression":
        return None
    ident = child_of_type(node, "property_identifier")
    if ident is None:
        return None
    return node_text(data, ident)


def _route_method(data: bytes, call) -> str | None:
    name = _property_name(data, _call_callee(call))
    if name is None:
        return None
    lowered = name.lower()
    if lowered in _ROUTE_METHODS:
        return lowered
    return None


def _literal_text(data: bytes, node) -> str | None:
    if node.type == "string":
        return "".join(
            node_text(data, child) for child in node.children if child.type == "string_fragment"
        )
    if node.type == "template_string":
        text = node_text(data, node)
        if len(text) >= 2 and text[0] == "`" and text[-1] == "`":
            return text[1:-1]
    return None


def _string_argument(data: bytes, call) -> str | None:
    arguments = child_of_type(call, "arguments")
    if arguments is None:
        return None
    for child in arguments.children:
        expr = _expression(child)
        if expr is None:
            continue
        text = _literal_text(data, expr)
        if text is not None:
            return text
    return None


def _path_from_route(data: bytes, node) -> str | None:
    """Path from a preceding `.route("/path")` in a chained call."""

    current = node
    while current is not None:
        if current.type == "member_expression":
            current = current.children[0] if current.children else None
            continue
        if current.type != "call_expression":
            return None
        callee = _call_callee(current)
        if _property_name(data, callee) == "route":
            return _string_argument(data, current)
        current = callee
    return None


def _callbacks(call) -> list:
    arguments = child_of_type(call, "arguments")
    if arguments is None:
        return []
    found = []
    for child in arguments.children:
        expr = _expression(child)
        if expr is not None and expr.type in _CALLBACKS:
            found.append(expr)
    return found


def _is_route_callback(data: bytes, node) -> bool:
    if node.type not in _CALLBACKS:
        return False
    current = node.parent
    while current is not None and current.type == "parenthesized_expression":
        current = current.parent
    if current is None or current.type != "arguments":
        return False
    call = current.parent
    if call is None or call.type != "call_expression":
        return False
    return _route_method(data, call) is not None


def _namespace(data: bytes, node, module: str) -> str | None:
    """Namespace of a named function's entry, or None when it has no entry.

    A method is keyed by its classes. Any other function is keyed by the
    chain of named functions around it, and has no entry when one link of
    that chain is anonymous.
    """

    if node.type == "method_definition":
        classes = _class_names(data, node)
        if not classes:
            return None
        return f"{module}.{'.'.join(classes)}"
    parent = _enclosing_function(node)
    if parent is None:
        return module
    name = _declared_name(data, parent)
    if name is None:
        return None
    outer = _namespace(data, parent, module)
    if outer is None:
        return None
    return f"{outer}.{name}"


def _is_entry(data: bytes, node) -> bool:
    return _declared_name(data, node) is not None and _namespace(data, node, "") is not None


def _complexity(data: bytes, node) -> int:
    root_id = node.id

    def skip(current) -> bool:
        if current.id == root_id:
            return False
        return _skip(current) or _is_route_callback(data, current) or _is_entry(data, current)

    return complexity(node, _is_decision, skip)


def _append(found: list, node, **kwargs) -> None:
    found.append(
        (
            node.start_byte,
            Function(start_byte=node.start_byte, end_byte=node.end_byte, **kwargs),
        )
    )


def _append_named(found, data, node, span, module, path) -> None:
    """Append `node` as an entry over `span` when it has one."""

    name = _declared_name(data, node)
    if name is None:
        return
    namespace = _namespace(data, node, module)
    if namespace is None:
        return
    _append(
        found,
        span,
        name=name,
        namespace=namespace,
        complexity=_complexity(data, node),
        start_line=start_line(span),
        end_line=end_line(span),
        path=path,
        language="typescript",
    )


def _append_arrows(found, data, node, module, path) -> None:
    for declarator in node.children:
        if declarator.type != "variable_declarator":
            continue
        value = child_of_type(declarator, "arrow_function", "function_expression")
        if value is not None:
            _append_named(found, data, value, declarator, module, path)


def _route_label(method: str, path: str | None) -> str:
    label = method.upper()
    if path:
        return f"{label} {path}"
    return label


def _claim(used: set[str], name: str) -> str:
    if name not in used:
        used.add(name)
        return name
    number = 2
    while f"{name}#{number}" in used:
        number += 1
    chosen = f"{name}#{number}"
    used.add(chosen)
    return chosen


def _collect_routes(routes: list, data: bytes, call) -> None:
    method = _route_method(data, call)
    if method is None:
        return
    callbacks = _callbacks(call)
    if not callbacks:
        return
    route = _string_argument(data, call)
    if not route:
        route = _path_from_route(data, _call_callee(call))
    for callback in callbacks:
        routes.append((callback.start_byte, callback, method, route))


def _append_routes(found, routes, data, module, path) -> None:
    used: set[str] = set()
    for _start, callback, method, route in sorted(routes, key=lambda item: item[0]):
        _append(
            found,
            callback,
            name=_claim(used, _route_label(method, route)),
            namespace=module,
            complexity=_complexity(data, callback),
            start_line=start_line(callback),
            end_line=end_line(callback),
            path=path,
            language="typescript",
        )


def functions_in_source(
    source: str, path: str, source_root: str | None = None
) -> list[Function]:
    data, tree = parse(source, _grammar(path))
    module = _module_namespace(path, source_root)
    found: list[tuple[int, Function]] = []
    routes: list[tuple[int, object, str, str | None]] = []
    for node in descendants(tree.root_node):
        if node.type in {"function_declaration", "method_definition"}:
            _append_named(found, data, node, node, module, path)
        elif node.type == "lexical_declaration":
            _append_arrows(found, data, node, module, path)
        elif node.type == "call_expression":
            _collect_routes(routes, data, node)
    _append_routes(found, routes, data, module, path)
    found.sort(key=lambda item: item[0])
    return [function for _, function in found]
