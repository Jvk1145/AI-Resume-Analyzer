"""Tests for LLM JSON cleanup and repair."""
import pytest

from ai.json_helper import clean_and_parse_json


def test_plain_json() -> None:
    assert clean_and_parse_json('{"a": 1}') == {"a": 1}


def test_strips_markdown_fences_and_prose() -> None:
    raw = 'Sure! Here you go:\n```json\n{"name": "A", "skills": ["x"]}\n```\nHope this helps.'
    assert clean_and_parse_json(raw) == {"name": "A", "skills": ["x"]}


def test_repairs_trailing_commas() -> None:
    assert clean_and_parse_json('{"a": [1, 2,], "b": {"c": 3,},}') == {"a": [1, 2], "b": {"c": 3}}


@pytest.mark.parametrize("raw", ["", "no json here", '{"a": [1, 2}'])
def test_unrecoverable_input_raises(raw: str) -> None:
    with pytest.raises(ValueError):
        clean_and_parse_json(raw)
