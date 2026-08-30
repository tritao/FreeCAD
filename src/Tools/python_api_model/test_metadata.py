# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import ast
import textwrap
import unittest

from python_api_model.metadata import (
    ExtensionEffect,
    ExtensionMetadataError,
    ExtensionRepresentation,
    TransactionPolicy,
    parse_api_metadata,
)


class ExtensionMetadataTests(unittest.TestCase):
    def parse(self, source: str):
        node = ast.parse(textwrap.dedent(source).lstrip()).body[0]
        if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            self.fail("expected a decorated declaration")
        return parse_api_metadata(node.decorator_list, subject=node.name)

    def test_parses_typed_callable_metadata(self) -> None:
        metadata = self.parse(
            """
            @extension_api(
                id='is_saved',
                permission='document.read',
                effect='read',
                since='1.1',
            )
            def isSaved(self) -> bool: ...
            """
        )
        assert metadata.extension_api is not None
        self.assertEqual(metadata.extension_api.local_id, "is_saved")
        self.assertEqual(metadata.extension_api.permission, "document.read")
        self.assertIs(metadata.extension_api.effect, ExtensionEffect.READ)
        self.assertIs(metadata.extension_api.transaction, TransactionPolicy.NONE)

    def test_parses_type_representation(self) -> None:
        metadata = self.parse(
            """
            @extension_interface(name='document', version=1)
            @extension_type(representation='value')
            class Vector: ...
            """
        )
        assert metadata.extension_type is not None
        self.assertIs(metadata.extension_type.representation, ExtensionRepresentation.VALUE)
        assert metadata.extension_interface is not None
        self.assertEqual(metadata.extension_interface.name, "document")
        self.assertEqual(metadata.extension_interface.version, 1)

    def test_parses_callable_metadata_from_annotated_attribute(self) -> None:
        node = ast.parse(
            "Length: Final[Annotated[float, "
            "extension_property(read=extension_api(id='shape_length', effect='read'), "
            "write=extension_api(id='shape_length_set', effect='modify', "
            "transaction='required'))]] = 0.0"
        ).body[0]
        assert isinstance(node, ast.AnnAssign)
        metadata = parse_api_metadata(
            (),
            subject="Part.TopoShape.Length",
            annotation=node.annotation,
        )
        assert metadata.extension_property is not None
        assert metadata.extension_property.read is not None
        assert metadata.extension_property.write is not None
        self.assertEqual(metadata.extension_property.read.local_id, "shape_length")
        self.assertIs(metadata.extension_property.read.effect, ExtensionEffect.READ)
        self.assertEqual(metadata.extension_property.write.local_id, "shape_length_set")
        self.assertEqual(
            metadata.extension_property.write.transaction.value,
            "required",
        )

    def test_rejects_invalid_property_metadata(self) -> None:
        cases = (
            "Annotated[str, extension_property()]",
            "Annotated[str, extension_property(read=extension_api(id='same'), "
            "write=extension_api(id='same'))]",
            "Annotated[str, extension_property(read='not_an_operation')]",
        )
        for annotation in cases:
            node = ast.parse(f"value: {annotation} = ...").body[0]
            assert isinstance(node, ast.AnnAssign)
            with self.subTest(annotation=annotation), self.assertRaises(ExtensionMetadataError):
                parse_api_metadata(
                    (),
                    subject="Demo.value",
                    annotation=node.annotation,
                )

    def test_rejects_invalid_metadata(self) -> None:
        cases = (
            "@extension_api(id='')\ndef f(): ...",
            "@extension_api(id='f', effect='write')\ndef f(): ...",
            "@extension_api(id='f', effect='read', transaction='required')\ndef f(): ...",
            "@extension_api(id='f', unexpected=True)\ndef f(): ...",
            "@extension_api(id='f')\n@extension_api(id='g')\ndef f(): ...",
            "@extension_api(id='f', effect=[])\ndef f(): ...",
            "@extension_interface(name='Document', version=1)\nclass Demo: ...",
        )
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ExtensionMetadataError):
                self.parse(source)


if __name__ == "__main__":
    unittest.main()
