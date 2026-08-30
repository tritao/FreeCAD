# pyright: strict

"""Neutral type representations shared by API output projections."""

from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from enum import Enum


class ApiTypeKind(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    VALUE = "value"
    HANDLE = "handle"
    LIST = "list"
    TUPLE = "tuple"
    DICT = "dict"
    OPTIONAL = "optional"
    UNION = "union"
    LITERAL = "literal"
    NONE = "none"


@dataclass(frozen=True)
class ApiType:
    """A recursive, runtime-neutral representation of one annotation."""

    kind: ApiTypeKind
    annotation: str
    handle: str | None = None
    item: ApiType | None = None
    items: tuple[ApiType, ...] = ()
    key: ApiType | None = None
    value: ApiType | None = None
    variadic: bool = False
    literal_values: tuple[object, ...] = ()


def _value(annotation: str) -> ApiType:
    return ApiType(kind=ApiTypeKind.VALUE, annotation=annotation)


def _name(node: ast.AST) -> str:
    return ast.unparse(node)


def _generic_name(node: ast.AST) -> str:
    return _name(node).rsplit(".", 1)[-1]


def _subscript_args(node: ast.Subscript) -> tuple[ast.AST, ...]:
    if isinstance(node.slice, ast.Tuple):
        return tuple(node.slice.elts)
    return (node.slice,)


def _handle_name(name: str, module_name: str | None) -> str:
    if "." in name or module_name is None:
        return name
    return f"{module_name}.{name}"


def _with_annotation(value: ApiType, annotation: str) -> ApiType:
    return replace(value, annotation=annotation)


def _union(members: list[ApiType], annotation: str) -> ApiType:
    non_none = [member for member in members if member.kind is not ApiTypeKind.NONE]
    if len(non_none) == 1 and len(non_none) != len(members):
        return ApiType(kind=ApiTypeKind.OPTIONAL, annotation=annotation, item=non_none[0])
    return ApiType(kind=ApiTypeKind.UNION, annotation=annotation, items=tuple(members))


def _parse_node(node: ast.AST, module_name: str | None, annotation: str) -> ApiType:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return ApiType(kind=ApiTypeKind.NONE, annotation=annotation)
        if isinstance(node.value, str):
            try:
                nested = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return _value(annotation)
            return _with_annotation(_parse_node(nested, module_name, node.value), annotation)
        return _value(annotation)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union(
            [
                _parse_node(node.left, module_name, _name(node.left)),
                _parse_node(node.right, module_name, _name(node.right)),
            ],
            annotation,
        )

    if isinstance(node, ast.Name):
        primitive = {
            "str": ApiTypeKind.STRING,
            "int": ApiTypeKind.INTEGER,
            "float": ApiTypeKind.FLOAT,
            "bool": ApiTypeKind.BOOLEAN,
            "Any": ApiTypeKind.VALUE,
            "object": ApiTypeKind.VALUE,
            "bytes": ApiTypeKind.VALUE,
            "None": ApiTypeKind.NONE,
        }
        if node.id in primitive:
            return ApiType(kind=primitive[node.id], annotation=annotation)
        if node.id in {"List", "list", "Sequence", "Iterable"}:
            return ApiType(kind=ApiTypeKind.LIST, annotation=annotation, item=_value("object"))
        if node.id in {"Tuple", "tuple"}:
            return ApiType(
                kind=ApiTypeKind.TUPLE,
                annotation=annotation,
                item=_value("object"),
                variadic=True,
            )
        if node.id in {"Dict", "dict", "Mapping"}:
            return ApiType(
                kind=ApiTypeKind.DICT,
                annotation=annotation,
                key=_value("object"),
                value=_value("object"),
            )
        return ApiType(
            kind=ApiTypeKind.HANDLE,
            annotation=annotation,
            handle=_handle_name(node.id, module_name),
        )

    if isinstance(node, ast.Attribute):
        name = _name(node)
        if node.attr == "Any":
            return _value(annotation)
        if node.attr in {"List", "list", "Sequence", "Iterable"}:
            return ApiType(kind=ApiTypeKind.LIST, annotation=annotation, item=_value("object"))
        if node.attr in {"Tuple", "tuple"}:
            return ApiType(
                kind=ApiTypeKind.TUPLE,
                annotation=annotation,
                item=_value("object"),
                variadic=True,
            )
        if node.attr in {"Dict", "dict", "Mapping"}:
            return ApiType(
                kind=ApiTypeKind.DICT,
                annotation=annotation,
                key=_value("object"),
                value=_value("object"),
            )
        return ApiType(kind=ApiTypeKind.HANDLE, annotation=annotation, handle=name)

    if isinstance(node, ast.Subscript):
        base = _generic_name(node.value)
        args = _subscript_args(node)
        if base == "Final":
            if not args:
                return _value(annotation)
            return _parse_node(args[0], module_name, _name(args[0]))
        if base in {"list", "List", "Sequence", "Iterable"}:
            item = _parse_node(args[0], module_name, _name(args[0])) if args else _value("object")
            return ApiType(kind=ApiTypeKind.LIST, annotation=annotation, item=item)
        if base in {"tuple", "Tuple"}:
            if len(args) == 2 and isinstance(args[1], ast.Constant) and args[1].value is Ellipsis:
                return ApiType(
                    kind=ApiTypeKind.TUPLE,
                    annotation=annotation,
                    item=_parse_node(args[0], module_name, _name(args[0])),
                    variadic=True,
                )
            return ApiType(
                kind=ApiTypeKind.TUPLE,
                annotation=annotation,
                items=tuple(_parse_node(arg, module_name, _name(arg)) for arg in args),
                variadic=False,
            )
        if base in {"dict", "Dict", "Mapping"}:
            key = _parse_node(args[0], module_name, _name(args[0])) if args else _value("object")
            value = _parse_node(args[1], module_name, _name(args[1])) if len(args) > 1 else _value("object")
            return ApiType(kind=ApiTypeKind.DICT, annotation=annotation, key=key, value=value)
        if base == "Optional":
            item = _parse_node(args[0], module_name, _name(args[0])) if args else _value("object")
            return ApiType(kind=ApiTypeKind.OPTIONAL, annotation=annotation, item=item)
        if base == "Union":
            return _union(
                [_parse_node(arg, module_name, _name(arg)) for arg in args],
                annotation,
            )
        if base == "Literal":
            values: list[object] = []
            for arg in args:
                try:
                    values.append(ast.literal_eval(arg))
                except (ValueError, SyntaxError):
                    values.append(_name(arg))
            return ApiType(
                kind=ApiTypeKind.LITERAL,
                annotation=annotation,
                literal_values=tuple(values),
            )
        if base == "Annotated" and args:
            return _parse_node(args[0], module_name, _name(args[0]))

    return _value(annotation)


def parse_annotation(annotation: str | None, module_name: str | None = None) -> ApiType | None:
    """Parse one Python annotation into the neutral API type grammar."""

    if annotation is None:
        return None
    text = annotation.strip()
    if not text:
        return _value(annotation)
    try:
        node = ast.parse(text, mode="eval").body
    except SyntaxError:
        return _value(annotation)
    return _parse_node(node, module_name, text)
