#!/usr/bin/env python3

"""
FCUI compiler prototype.

Parses a restricted "FCUI-Py" subset described in `src/Gui/FCUI/FCUI.md` using
CPython's parser (`ast.parse`) and emits the bootstrap `.fcuim.json` format
consumed by `FCUIQtRuntime`.

Important: this tool does NOT execute the input file (no imports/eval/exec).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CompileError(Exception):
    message: str
    filename: str
    lineno: int = 1
    col: int = 0

    def __str__(self) -> str:
        loc = f"{self.filename}:{self.lineno}:{self.col + 1}"
        return f"{loc}: error: {self.message}"


def _node_loc(node: ast.AST) -> Tuple[int, int]:
    return (getattr(node, "lineno", 1), getattr(node, "col_offset", 0))


def _source_segment(source: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(source, node)
    if seg is not None:
        return seg
    return node.__class__.__name__


def _strip_docstring(body: Sequence[ast.stmt]) -> List[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return list(body[1:])
    return list(body)


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_attr_call(node: ast.AST, root: str, attr: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and _is_name(node.func.value, root)
        and node.func.attr == attr
    )


def _const_eval(node: ast.AST, filename: str, source: str) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_const_eval(e, filename, source) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return [_const_eval(e, filename, source) for e in node.elts]
    if isinstance(node, ast.Dict):
        out: Dict[Any, Any] = {}
        for k, v in zip(node.keys, node.values):
            if k is None:
                lineno, col = _node_loc(node)
                raise CompileError("dict unpacking is not supported in FCUI-Py", filename, lineno, col)
            out[_const_eval(k, filename, source)] = _const_eval(v, filename, source)
        return out
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return +node.operand.value if isinstance(node.op, ast.UAdd) else -node.operand.value
    lineno, col = _node_loc(node)
    raise CompileError(f"expected a constant expression, got: {_source_segment(source, node)}", filename, lineno, col)


def _type_to_string(node: ast.AST, filename: str, source: str) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _type_to_string(node.value, filename, source) + "." + node.attr
    return _source_segment(source, node)


def _prop_kind_and_type(annotation: ast.AST, filename: str, source: str) -> Tuple[str, str]:
    if not isinstance(annotation, ast.Subscript) or not isinstance(annotation.value, ast.Name):
        lineno, col = _node_loc(annotation)
        raise CompileError("expected annotation like prop[T] or state[T]", filename, lineno, col)
    kind = annotation.value.id
    if kind not in ("prop", "state"):
        lineno, col = _node_loc(annotation)
        raise CompileError("expected annotation like prop[T] or state[T]", filename, lineno, col)
    slice_node: ast.AST = annotation.slice
    index_t = getattr(ast, "Index", None)
    if index_t is not None and isinstance(slice_node, index_t):  # py<3.9
        slice_node = slice_node.value  # type: ignore[assignment]
    return kind, _type_to_string(slice_node, filename, source)


class FcuiCompiler:
    def __init__(self, filename: str, source: str) -> None:
        self.filename = filename
        self.source = source

    def err(self, node: ast.AST, message: str) -> CompileError:
        lineno, col = _node_loc(node)
        return CompileError(message, self.filename, lineno, col)

    def compile_module(self) -> Dict[str, Any]:
        try:
            tree = ast.parse(self.source, filename=self.filename)
        except SyntaxError as e:
            raise CompileError(e.msg, self.filename, e.lineno or 1, (e.offset or 1) - 1) from e

        components: List[Dict[str, Any]] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            if isinstance(stmt, ast.ClassDef) and self._is_component_class(stmt):
                components.append(self._compile_component(stmt))
                continue
            raise self.err(stmt, "only @component classes are allowed at top level in FCUI-Py")

        if not components:
            raise CompileError("module has no @component classes", self.filename, 1, 0)

        return {"version": 0, "components": components}

    def _is_component_class(self, cls: ast.ClassDef) -> bool:
        return any(isinstance(d, ast.Name) and d.id == "component" for d in cls.decorator_list)

    def _compile_component(self, cls: ast.ClassDef) -> Dict[str, Any]:
        props: List[Dict[str, Any]] = []
        template: Optional[Dict[str, Any]] = None

        for stmt in cls.body:
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "render":
                if template is not None:
                    raise self.err(stmt, "duplicate render() in component")
                template = self._compile_render(stmt)
                continue

            if isinstance(stmt, ast.AnnAssign):
                if not isinstance(stmt.target, ast.Name):
                    raise self.err(stmt, "only simple 'name: prop[T]' declarations are supported")
                kind, ty = _prop_kind_and_type(stmt.annotation, self.filename, self.source)
                if kind != "prop":
                    continue
                entry: Dict[str, Any] = {"kind": "prop", "name": stmt.target.id, "type": ty}
                if stmt.value is not None:
                    entry["default"] = {"kind": "const", "value": _const_eval(stmt.value, self.filename, self.source)}
                props.append(entry)
                continue

            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue

            raise self.err(stmt, "unsupported statement in @component class body")

        if template is None:
            raise self.err(cls, "component is missing render()")

        return {"name": cls.name, "props": props, "template": template}

    def _compile_render(self, fn: ast.FunctionDef) -> Dict[str, Any]:
        body = _strip_docstring(fn.body)
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            raise self.err(fn, "render() must be a single `return <UI>` statement in this bootstrap")
        return self._compile_node(body[0].value)

    def _compile_node(self, expr: ast.AST) -> Dict[str, Any]:
        if not isinstance(expr, ast.Call):
            raise self.err(expr, "UI nodes must be constructor calls like Column(...), Text(...), Button(...)")
        if not isinstance(expr.func, ast.Name):
            raise self.err(expr, "UI node constructor must be a simple name (e.g. Column)")

        node_type = expr.func.id
        props: Dict[str, Any] = {}
        children: List[Dict[str, Any]] = []

        for a in expr.args:
            children.append(self._compile_node(a))

        for kw in expr.keywords:
            if kw.arg is None:
                raise self.err(kw, "**kwargs is not supported in FCUI-Py")
            props[kw.arg] = self._compile_value(kw.value)

        return {"type": node_type, "props": props, "children": children}

    def _compile_value(self, expr: ast.AST) -> Dict[str, Any]:
        if _is_attr_call(expr, "fc", "command"):
            call = expr  # type: ignore[assignment]
            if len(call.args) != 1 or call.keywords:
                raise self.err(expr, "fc.command expects one string argument")
            if not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
                raise self.err(expr, "fc.command expects a string literal")
            return {"kind": "command", "name": call.args[0].value}

        host_path = self._host_path_from_expr(expr)
        if host_path is not None:
            return {"kind": "host_path", "path": host_path, "source": _source_segment(self.source, expr)}

        try:
            v = _const_eval(expr, self.filename, self.source)
            return {"kind": "const", "value": v}
        except CompileError:
            pass

        ops = self._compile_vm(expr)
        return {"kind": "vm", "source": _source_segment(self.source, expr), "ops": ops}

    def _host_path_from_expr(self, expr: ast.AST) -> Optional[str]:
        if _is_attr_call(expr, "fc", "path") or _is_attr_call(expr, "fc", "host_path"):
            call = expr  # type: ignore[assignment]
            if len(call.args) != 1 or call.keywords:
                raise self.err(expr, "fc.path expects one string argument")
            if not (isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
                raise self.err(expr, "fc.path expects a string literal")
            return call.args[0].value

        attrs: List[str] = []
        cur: ast.AST = expr
        while isinstance(cur, ast.Attribute):
            attrs.append(cur.attr)
            cur = cur.value
        if _is_name(cur, "fc") and attrs:
            return ".".join(reversed(attrs))
        return None

    def _compile_vm(self, expr: ast.AST) -> List[Dict[str, Any]]:
        ops: List[Dict[str, Any]] = []

        def emit(node: ast.AST) -> None:
            if isinstance(node, ast.Constant):
                ops.append({"op": "CONST", "value": node.value})
                return

            if isinstance(node, ast.Attribute) and _is_name(node.value, "self"):
                ops.append({"op": "LOAD_SELF", "name": node.attr})
                return

            hp = self._host_path_from_expr(node)
            if hp is not None:
                ops.append({"op": "LOAD_HOST_PATH", "path": hp})
                return

            if isinstance(node, ast.UnaryOp):
                emit(node.operand)
                if isinstance(node.op, ast.Not):
                    ops.append({"op": "NOT"})
                    return
                if isinstance(node.op, ast.USub):
                    ops.append({"op": "NEG"})
                    return
                if isinstance(node.op, ast.UAdd):
                    ops.append({"op": "POS"})
                    return
                raise self.err(node, "unsupported unary operator")

            if isinstance(node, ast.BinOp):
                emit(node.left)
                emit(node.right)
                if isinstance(node.op, ast.Add):
                    ops.append({"op": "ADD"})
                    return
                if isinstance(node.op, ast.Sub):
                    ops.append({"op": "SUB"})
                    return
                if isinstance(node.op, ast.Mult):
                    ops.append({"op": "MUL"})
                    return
                if isinstance(node.op, ast.Div):
                    ops.append({"op": "DIV"})
                    return
                if isinstance(node.op, ast.Mod):
                    ops.append({"op": "MOD"})
                    return
                raise self.err(node, "unsupported binary operator")

            if isinstance(node, ast.BoolOp):
                if len(node.values) < 2:
                    raise self.err(node, "invalid boolean operator")
                emit(node.values[0])
                for v in node.values[1:]:
                    emit(v)
                    if isinstance(node.op, ast.And):
                        ops.append({"op": "AND"})
                    elif isinstance(node.op, ast.Or):
                        ops.append({"op": "OR"})
                    else:
                        raise self.err(node, "unsupported boolean operator")
                return

            if isinstance(node, ast.Compare):
                if len(node.ops) != 1 or len(node.comparators) != 1:
                    raise self.err(node, "chained comparisons are not supported in this bootstrap")
                emit(node.left)
                emit(node.comparators[0])
                op = node.ops[0]
                if isinstance(op, ast.Eq):
                    ops.append({"op": "EQ"})
                    return
                if isinstance(op, ast.NotEq):
                    ops.append({"op": "NE"})
                    return
                if isinstance(op, ast.Lt):
                    ops.append({"op": "LT"})
                    return
                if isinstance(op, ast.LtE):
                    ops.append({"op": "LE"})
                    return
                if isinstance(op, ast.Gt):
                    ops.append({"op": "GT"})
                    return
                if isinstance(op, ast.GtE):
                    ops.append({"op": "GE"})
                    return
                raise self.err(node, "unsupported comparison operator")

            if isinstance(node, ast.IfExp):
                emit(node.test)
                emit(node.body)
                emit(node.orelse)
                ops.append({"op": "SELECT"})
                return

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                name = node.func.id
                if name not in ("str", "len", "min", "max", "format"):
                    raise self.err(node, f"unsupported call in binding VM: {name}()")
                if node.keywords:
                    raise self.err(node, "keyword arguments are not supported in binding VM calls")
                for a in node.args:
                    emit(a)
                ops.append({"op": "CALL_BUILTIN", "name": name, "argc": len(node.args)})
                return

            raise self.err(node, f"unsupported expression in binding VM: {_source_segment(self.source, node)}")

        emit(expr)
        return ops


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input FCUI-Py file (.fcui.py)")
    ap.add_argument("--out", dest="out_path", required=True, help="Output module JSON file (.fcuim.json)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = ap.parse_args()

    in_path = os.path.abspath(args.in_path)
    out_path = os.path.abspath(args.out_path)

    with open(in_path, "r", encoding="utf-8") as f:
        source = f.read()

    data = FcuiCompiler(in_path, source).compile_module()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
    os.replace(tmp_path, out_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompileError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2)
