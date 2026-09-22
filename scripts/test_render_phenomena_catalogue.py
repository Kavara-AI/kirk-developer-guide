"""Regression checks for catalogue cardinality and existing validation."""

import copy
import json
import unittest

from render_phenomena_catalogue import SOURCE, render, validate


class CatalogueValidationTests(unittest.TestCase):
    def setUp(self):
        self.catalogue = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_documented_catalogue_is_valid(self):
        validate(self.catalogue)
        self.assertIn("256 candidate phenomena across 32 domains", render(self.catalogue))

    def test_removing_a_domain_cannot_be_hidden_by_regeneration(self):
        self.catalogue["domains"].pop()
        with self.assertRaisesRegex(ValueError, "Expected exactly 32 domains; got 31"):
            render(self.catalogue)

    def test_removing_a_prompt_cannot_be_hidden_by_regeneration(self):
        self.catalogue["domains"][0]["phenomena"].pop()
        with self.assertRaisesRegex(ValueError, "Expected exactly 256 exploration prompts; got 255"):
            render(self.catalogue)

    def test_extra_domain_requires_updating_the_documented_contract(self):
        extra = copy.deepcopy(self.catalogue["domains"][0])
        extra["id"] = "extra-domain"
        for index, prompt in enumerate(extra["phenomena"]):
            prompt["id"] = f"extra-prompt-{index}"
        self.catalogue["domains"].append(extra)
        with self.assertRaisesRegex(ValueError, "Expected exactly 32 domains; got 33"):
            validate(self.catalogue)

    def test_extra_prompt_requires_updating_the_documented_contract(self):
        self.catalogue["domains"][0]["phenomena"].append(
            {"id": "extra-prompt", "description": "An additional exploration hypothesis."}
        )
        with self.assertRaisesRegex(ValueError, "Expected exactly 256 exploration prompts; got 257"):
            validate(self.catalogue)

    def test_invalid_or_empty_top_level_collections_keep_their_error(self):
        for key, value in [("data_shapes", []), ("data_shapes", {}),
                           ("domains", {}), ("domains", [])]:
            with self.subTest(key=key, value=value):
                catalogue = copy.deepcopy(self.catalogue)
                catalogue[key] = value
                with self.assertRaisesRegex(ValueError, "Nonempty data_shapes and domains are required"):
                    validate(catalogue)

    def test_invalid_or_empty_prompt_collections_keep_their_error(self):
        for value in [None, {}, []]:
            with self.subTest(value=value):
                catalogue = copy.deepcopy(self.catalogue)
                catalogue["domains"][0]["phenomena"] = value
                with self.assertRaisesRegex(ValueError, "No exploration prompts"):
                    validate(catalogue)


if __name__ == "__main__":
    unittest.main()
