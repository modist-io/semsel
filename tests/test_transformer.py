# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""
"""

from lark import Tree, Token
from hypothesis import given
from hypothesis.strategies import just, lists, from_regex, sampled_from

from semsel.parser import SemselTransformer
from semsel.version import PartialVersion
from semsel.selector import ConditionOperator

from .strategies import lark_tree, lark_token, lark_version_tree


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
