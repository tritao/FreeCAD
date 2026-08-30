# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import unittest

from python_api_model.types import ApiTypeKind, parse_annotation


class ApiTypeTests(unittest.TestCase):
    def test_primitive_and_handle_types(self) -> None:
        self.assertEqual(parse_annotation("str").kind, ApiTypeKind.STRING)
        self.assertEqual(parse_annotation("int").kind, ApiTypeKind.INTEGER)
        self.assertEqual(parse_annotation("Part.TopoShape").handle, "Part.TopoShape")
        self.assertEqual(parse_annotation("TopoShape", "Part").handle, "Part.TopoShape")

    def test_collections_and_variadic_tuples(self) -> None:
        list_type = parse_annotation("List", "Part")
        self.assertIsNotNone(list_type)
        assert list_type is not None
        self.assertEqual(list_type.kind, ApiTypeKind.LIST)
        self.assertEqual(list_type.item.kind, ApiTypeKind.VALUE)

        tuple_type = parse_annotation("Tuple[TopoShape, ...]", "Part")
        self.assertIsNotNone(tuple_type)
        assert tuple_type is not None
        self.assertEqual(tuple_type.kind, ApiTypeKind.TUPLE)
        self.assertTrue(tuple_type.variadic)
        self.assertEqual(tuple_type.item.handle, "Part.TopoShape")

    def test_unions_optionals_and_literals(self) -> None:
        optional = parse_annotation("str | None")
        self.assertIsNotNone(optional)
        assert optional is not None
        self.assertEqual(optional.kind, ApiTypeKind.OPTIONAL)

        literal = parse_annotation("Literal['read', 'write']")
        self.assertIsNotNone(literal)
        assert literal is not None
        self.assertEqual(literal.kind, ApiTypeKind.LITERAL)
        self.assertEqual(literal.literal_values, ("read", "write"))

    def test_metadata_wrappers_do_not_change_the_semantic_annotation(self) -> None:
        value = parse_annotation("Final[Annotated[float, object]]")
        self.assertIsNotNone(value)
        assert value is not None
        self.assertEqual(value.kind, ApiTypeKind.FLOAT)
        self.assertEqual(value.annotation, "float")


if __name__ == "__main__":
    unittest.main()
