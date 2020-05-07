# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""
"""

import pytest
from lark import Tree, Token
from hypothesis import given
from lark.exceptions import VisitError
from hypothesis.strategies import (
    just,
    lists,
    nothing,
    integers,
    from_regex,
    sampled_from,
)

from semsel.parser import SemselTransformer
from semsel.version import PartialVersion
from semsel.selector import VersionCondition, ConditionOperator
from semsel.exceptions import ParseFailure

from .strategies import (
    lark_tree,
    lark_token,
    partial_version,
    lark_version_tree,
    condition_operator,
)


@given(
    lark_tree(
        children_strategy=lists(
            lark_token(
                type_strategy=sampled_from(["MAJOR", "MINOR", "PATCH"]),
                value_strategy=from_regex(r"\A[0-9]+\Z"),
            ),
            min_size=1,
        )
    )
)
def test_casts_version_fragment_tokens(tree: Tree):
    assert all(isinstance(_.value, str) for _ in tree.children)

    transformed: Tree = SemselTransformer(visit_tokens=True).transform(tree)
    assert all(isinstance(_.value, int) for _ in transformed.children)


@given(
    lark_tree(
        children_strategy=lists(
            lark_token(
                type_strategy=just("OPERATOR"),
                value_strategy=sampled_from([_.value for _ in ConditionOperator]),
            ),
            min_size=1,
        )
    )
)
def test_transforms_operator_to_ConditionOperator(tree: Tree):
    assert all(isinstance(_.value, str) for _ in tree.children)

    transformed: Tree = SemselTransformer(visit_tokens=True).transform(tree)
    assert all(isinstance(_, ConditionOperator) for _ in transformed.children)


@given(lark_version_tree())
def test_transforms_version_to_PartialVersion(version_tree: Tree):
    assert isinstance(version_tree, Tree)
    transformed: PartialVersion = SemselTransformer(visit_tokens=True).transform(
        version_tree
    )
    assert isinstance(transformed, PartialVersion)


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(nothing(), min_size=0, max_size=0),
    ),
    condition_operator(),
    partial_version(),
    integers(min_value=0),
)
def test_transforms_version_condition_to_VersionCondition(
    tree: Tree,
    operator: ConditionOperator,
    version: PartialVersion,
    optional_minor: int,
):
    if operator == ConditionOperator.MINOR and version.minor is None:
        version.minor = optional_minor
    tree.children = [operator, version]
    transformed: VersionCondition = SemselTransformer(visit_tokens=True).transform(tree)
    assert isinstance(transformed, VersionCondition)
    assert transformed.operator == operator
    assert transformed.version == version


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(partial_version(), min_size=1, max_size=1),
    )
)
def test_transforms_partial_version_condition_to_VersionCondition(tree: Tree):
    transformed: VersionCondition = SemselTransformer(visit_tokens=True).transform(tree)
    assert isinstance(transformed, VersionCondition)
    assert transformed.operator == ConditionOperator.EQ
    assert isinstance(transformed.version, PartialVersion)


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(lark_token(), min_size=1, max_size=1),
    )
)
def test_fails_to_parse_partial_version_condition_with_invalid_partial_version(
    tree: Tree,
):
    with pytest.raises(VisitError) as exc:
        SemselTransformer(visit_tokens=True).transform(tree)

    assert "failed to extract expected version" in str(exc.value)
    _, err, _ = exc._excinfo
    assert isinstance(err, VisitError)
    assert isinstance(err.orig_exc, ParseFailure)


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(nothing(), min_size=0, max_size=0),
    ),
    lark_token(),
    partial_version(),
)
def test_fails_to_parse_version_condition_with_invalid_operator(
    tree: Tree, invalid_operator: Token, version: PartialVersion
):
    tree.children = [invalid_operator, version]
    with pytest.raises(VisitError) as exc:
        SemselTransformer(visit_tokens=True).transform(tree)

    assert "failed to extract expected operator" in str(exc.value)
    _, err, _ = exc._excinfo
    assert isinstance(err, VisitError)
    assert isinstance(err.orig_exc, ParseFailure)


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(nothing(), min_size=0, max_size=0),
    ),
    condition_operator(),
    lark_token(),
)
def test_fails_to_parse_version_condition_with_invalid_partial_version(
    tree: Tree, operator: ConditionOperator, invalid_version: Token
):
    tree.children = [operator, invalid_version]
    with pytest.raises(VisitError) as exc:
        SemselTransformer(visit_tokens=True).transform(tree)

    assert "failed to extract expected version" in str(exc.value)
    _, err, _ = exc._excinfo
    assert isinstance(err, VisitError)
    assert isinstance(err.orig_exc, ParseFailure)


@given(
    lark_tree(
        data_strategy=just("version_condition"),
        children_strategy=lists(lark_token(), min_size=3),
    )
)
def test_fails_to_parse_version_condition_with_too_many_tokens(tree: Tree):
    with pytest.raises(VisitError) as exc:
        SemselTransformer(visit_tokens=True).transform(tree)

    assert "failed to extract expected operator and version" in str(exc.value)
    _, err, _ = exc._excinfo
    assert isinstance(err, VisitError)
    assert isinstance(err.orig_exc, ParseFailure)
