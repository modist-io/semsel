# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains unit tests for the SemselParser."""

from unittest import mock

import pytest
from lark import Lark, Tree
from hypothesis import given
from lark.exceptions import VisitError
from hypothesis.strategies import text, sampled_from

from semsel.parser import GRAMMAR, SemselParser, SemselTransformer
from semsel.selector import VersionSelector
from semsel.exceptions import ParseFailure, InvalidExpression

from .strategies import version_selector


def test_defaults_to_included_grammar():
    parser = SemselParser()
    assert parser.grammar == GRAMMAR
    assert isinstance(parser.parser, Lark)


def test_default_transfomer_visits_tokens():
    parser = SemselParser()
    assert isinstance(parser.transformer, SemselTransformer)
    assert parser.transformer.__visit_tokens__


@given(version_selector())
def test_tokenize_strips_surrounding_whitespace(version_selector: VersionSelector):
    with mock.patch.object(Lark, "parse") as mocked_parse:
        parser = SemselParser().tokenize(f" {version_selector!s}\t")
        mocked_parse.assert_called_once_with(str(version_selector))


@given(version_selector())
def test_tokenize_produces_version_selector_tree(version_selector: VersionSelector):
    parser = SemselParser()
    selector_tree = parser.tokenize(str(version_selector))
    assert isinstance(selector_tree, Tree)
    assert selector_tree.data == "selector"


@given(version_selector())
def test_parse_produces_VersionSelector(version_selector: VersionSelector):
    parser = SemselParser()
    parsed = parser.parse(str(version_selector), validate=False)
    assert parsed == version_selector


@given(version_selector(), sampled_from([ParseFailure, InvalidExpression]))
def test_parse_VisitError_raises_original_exception(
    version_selector: VersionSelector, handled_exception
):
    with mock.patch.object(SemselTransformer, "transform") as mocked_transform:
        mocked_transform.side_effect = VisitError(
            "test", Tree("test", []), handled_exception("test")
        )

        with pytest.raises(handled_exception) as exc:
            SemselParser().parse(str(version_selector), validate=False)

        assert "test" in str(exc.value)


@given(version_selector())
def test_parse_VisitError_raises_VisitError(version_selector: VersionSelector):
    with mock.patch.object(SemselTransformer, "transform") as mocked_transform:
        mocked_transform.side_effect = VisitError(
            "test", Tree("test", []), ValueError("test")
        )

        with pytest.raises(VisitError) as exc:
            SemselParser().parse(str(version_selector), validate=False)
