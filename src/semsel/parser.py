# -*- encoding: utf-8 -*-
# Copyright (c) 2019 Stephen Bunn <stephen@bunn.io>
# ISC License <https://choosealicense.com/licenses/isc>

"""Contains Semver selector parsers, transformers, and grammars."""

from typing import Any, List, Tuple, Union

import attr
from lark import Lark, Tree, Token, Transformer
from cached_property import cached_property
from lark.exceptions import VisitError

from .version import PartialVersion
from .selector import VersionRange, VersionSelector, VersionCondition, ConditionOperator
from .exceptions import ParseFailure, InvalidExpression

GRAMMAR = """
WS: (" " | /\t/)

OP_EQ: "="
OP_GT: ">"
OP_LT: "<"
OP_GE: OP_GT OP_EQ
OP_LE: OP_LT OP_EQ
OP_MAJOR: "^"
OP_MINOR: "~"
OPERATOR: OP_EQ | OP_GE | OP_LE | OP_GT | OP_LT | OP_MAJOR | OP_MINOR

DOT: "."
HYPHEN: "-"
DIGIT: "0".."9"
CHARACTER: "a".."z" | "A".."Z"

VERSION_DIGIT: ("0" | "1".."9") DIGIT*
VERSION_ALPHA: CHARACTER | HYPHEN
VERSION_ALPHANUMERIC: DIGIT | CHARACTER | HYPHEN

MAJOR: VERSION_DIGIT
MINOR: VERSION_DIGIT
PATCH: VERSION_DIGIT
PRERELEASE: ((DIGIT* VERSION_ALPHA VERSION_ALPHANUMERIC*) | VERSION_DIGIT) \
    (DOT ((DIGIT* VERSION_ALPHA VERSION_ALPHANUMERIC*) | VERSION_DIGIT))*
BUILD: VERSION_ALPHANUMERIC+ (DOT VERSION_ALPHANUMERIC+)*

version: MAJOR ("." MINOR ("." PATCH ("-" PRERELEASE)? ("+" BUILD)?)?)?
version_range: version " - " version
version_condition: OPERATOR? " "? version
version_clause: (version_condition | version_range) \
    (" " (version_condition | version_range))*

selector: version_clause (" "? "||" " "? version_clause)*
?start: selector
"""


class SemselTransformer(Transformer):
    """Transforms a tokenized Semver selection expression to a standard instance.

    The goal of this transformer is to take a tokenized Semver selector expression and
    produce the corresponding :class:`~.selector.VersionSelector` instance that can
    be used for evaluation.

    This transformer should only really be applied to tokenized trees from the provided
    grammar in order to avoid breakages. This transfomer is automatically included and
    used during calls to :meth:`~.SemselParser.parse`. To use this transformer outside
    of the parser usage, you need to have a tree that needs to be transformed.
    Assuming you have a Lark produced :class:`lark.Tree` structure, you can use this
    transfomer like the following:

    >>> from semsel.parser import SemselTransformer
    >>> version_selector = SemeselTransformer(visit_tokens=True).transform(MY_TREE)
    >>> version_selector
        VersionSelector()

    .. important:: Without the ``visit_tokens`` flag being set to ``True`` during the
        initialization of the transformer, this transformer will fail as we rely on
        the visiting of the version fragments (MAJOR, MINOR, and PATCH) for casting
        before we build the proper :class:`~.version.PartialVersion` instance.
        We also rely on this flag for properly parsing out and constructing the
        :class:`~.selector.ConditionOperator` for conditioned version expressions.

        Please be sure you set this flag to ``True`` if you intend to use this
        transformer outside of a :class:`~.SemselParser` instance.
    """

    def __cast_to_int(self, token: Token) -> int:
        """Cast a given digit token to be an integer instead of a string.

        .. note:: To be safe for future udpates to the lark parser API we are
            mangling this method name to avoid future collisions.

        :param Token token: The token to update from a string to an integer
        :return: The updated token instance
        :rtype: int
        """

        return token.update(value=int(token.value))

    def MAJOR(self, token: Token) -> Token:
        """Ensure that ``MAJOR`` tokens are casted down to an ``int``.

        :param Token token: The MAJOR token instance
        :return: A Token that has had it's value casted to an int
        :rtype: Token
        """

        return self.__cast_to_int(token)

    def MINOR(self, token: Token) -> int:
        """Ensure that ``MINOR`` tokens are casted down to an ``int``.

        :param Token token: The MINOR token instance
        :return: A Token that has had it's value casted to an int
        :rtype: Token
        """

        return self.__cast_to_int(token)

    def PATCH(self, token: Token) -> int:
        """Ensure that ``PATCH`` tokens are casted down to an ``int``.

        :param Token token: The PATCH token instance
        :return: A Token that has had it's value casted to an int
        :rtype: Token
        """

        return self.__cast_to_int(token)

    def OPERATOR(self, token: Token) -> ConditionOperator:
        """Ensure that :class:`~.selector.ConditionOperator` are created.

        :param Token token: A token matching the given operator
        :return: The corresponding ConditionOperator for the passed in token
        :rtype: ConditionOperator
        """

        return ConditionOperator(token.value)

    def version(self, tokens: List[Token]) -> PartialVersion:
        """Ensure that :class:`~.version.PartialVersion` instances are created.

        :param List[Token] tokens: A list of tokens which make up a single version.
        :return: A built version which can be compared and evaluated
        :rtype: PartialVersion
        """

        return PartialVersion.from_dict(
            {fragment.type.lower(): fragment.value for fragment in tokens}
        )

    def version_condition(
        self, tokens: List[Union[ConditionOperator, PartialVersion]]
    ) -> VersionCondition:
        """Ensure that :class:`~.selector.VersionCondition` instances are created.

        .. note:: If no :class:`~.selector.ConditionOperator` is provided in the built
            tokens, the user has not included an operator for the condition. In this
            case we **IMPLICILTY ASSUME** that the user intends the provided version
            to be matched explicilty with an equality operator.

            For example, the version specifier ``1`` will be interepreted as ``=1``
            implicilty. This *feature* is part of the standard Semver selector
            specification.

        :param List[Union[ConditionOperator, PartialVersion]] data: A list \
            **POTENTIALLY** containing an :class:`~.selector.ConditionOperator` and \
            **ALWAYS** containing a :class:`~.version.PartialVersion`
        :raises ParseFailure: If either we fail to extract the operator or version \
            from the provided tokens
        :return: A matching condition statement for a given condition token set
        :rtype: VersionCondition
        """

        condition_tuple: Tuple[ConditionOperator, PartialVersion]
        if len(tokens) == 1:
            if not isinstance(tokens[0], PartialVersion):
                raise ParseFailure(
                    f"failed to extract expected version from {tokens!r}"
                )

            # NOTE: we assume that if NO operator symbol is provided in the condition,
            # then the user intends the version to have an IMPLICIT equals condition
            return VersionCondition(operator=ConditionOperator.EQ, version=tokens[0])

        elif len(tokens) == 2:
            operator, version = tokens
            if not isinstance(operator, ConditionOperator):
                raise ParseFailure(
                    f"failed to extract expected operator from {tokens!r}"
                )
            if not isinstance(version, PartialVersion):
                raise ParseFailure(
                    f"failed to extract expected version from {tokens!r}"
                )

            return VersionCondition(operator=operator, version=version)

        else:
            raise ParseFailure(
                f"failed to extract expected operator and version from {tokens!r}"
            )

    def version_range(self, tokens: List[PartialVersion]) -> VersionRange:
        """Ensure that :class:`~.selector.VersionRange` instances are created.

        :param List[PartialVersion] tokens: A lsit of multiple versions, the first one \
            being the starting version and the last one being the ending version
        :raises ParseFailure: If we fail to find both a starting and ending version
        :return: A matching version range instance for the given range token set
        :rtype: VersionRange
        """

        if len(tokens) != 2:
            raise ParseFailure(
                f"failed to extract expected start and end versions from {tokens!r}"
            )

        version_start, version_end = tokens
        return VersionRange(version_start=version_start, version_end=version_end)

    def version_clause(
        self, tokens: List[Union[VersionCondition, VersionRange]]
    ) -> List[Union[VersionCondition, VersionRange]]:
        """Ensure that clauses are passed back simply as their tokens.

        .. note:: This is a necessary transformation to ensure we are not including
            token instances but instead are resolving clauses to simply be the list of
            parsed and transformed conditions and ranges from the tokenzied statements.

        :param List[Union[VersionCondition, VersionRange]] tokens: A list of tokens \
            making up the parsed version clause
        :return: A list of tokens making up the parsed version clause
        :rtype: List[Union[VersionCondition, VersionRange]]
        """

        return tokens

    def selector(
        self, tokens: List[List[Union[VersionCondition, VersionRange]]]
    ) -> VersionSelector:
        """Ensure that a :class:`~.selector.VersionSelector` instance is created.

        :param List[List[Union[VersionCondition, VersionRange]]] tokens: A list of \
            clause tokens that can be used directly in the \
            :class:`~.selector.VersionSelector` class
        :return: A new version selector instance to use for various comparisons
        :rtype: VersionSelector
        """

        return VersionSelector(clauses=tokens, validate=self.__validate)

    def transform(self, tree: Tree, validate: bool = True) -> Any:
        """Transform the given tree to a :class:`~.selector.VersionSelector`.

        :param Tree tree: The ``selector`` tree to transform
        :param bool validate: Whether validation should be performed on the built
            version selector, optional, defaults to True
        :return: The result of the transformed tree
        :rtype: Any
        """

        self.__validate = validate
        return super().transform(tree)


@attr.s
class SemselParser:
    """Tokenize and parse a Semver selector string for library usage.

    The goal of this parser is to make the construction of
    :class:`~.selector.VersionSelector` instances simple. Since handling the Semver
    selector structure is difficult to do with raw REGEX patterns, this parser
    implements a simple BNF-grammar for parsing / validating a given Semver selector
    expression.

    Through this parser you can do two things (*mainly*). First off you can simply
    use the parser to tokenize a given selector expression using the provieded
    :meth:`~.SemselParser.tokenize` method. This method will produce a
    :class:`lark.Tree` instance for further analysis, parsing, transformation, etc.

    >>> from semsel.parser import SemselParser
    >>> parser = SemselParser()
    >>> token_tree = parser.tokenize(">2.3.4 <2.4 || 2.3.9")
    >>> token_tree
        Tree(selector, [Tree(version_clause, ...<snipped>...


    Most of the time you will want to use the provided :meth:`~.SemselParser.parse`
    method as it produeces a :class:`~.selector.VersionSelector` instance which has most
    of the fancy features and evaulations that you likely needed this library for.

    >>> version_selector = parser.parse(">2.3.4 <2.4 || 2.3.9")
    >>> version_selector
        >2.3.4 <2.4 || 2.3.9
    """

    grammar: str = attr.ib(default=GRAMMAR)
    debug: bool = attr.ib(default=False)

    @cached_property
    def parser(self) -> Lark:
        """:class:`lark.Lark` parser instance for string tokenization."""

        return Lark(self.grammar, debug=self.debug)

    @cached_property
    def transformer(self) -> Transformer:
        """:class:`~.SemselTransformer` transformer instance for tree transformation."""

        return SemselTransformer(visit_tokens=True)

    def tokenize(self, content: str) -> Tree:
        """Tokenize a given Semver selector string according to the provided grammar.

        :param str content: The selector string to tokenize
        :return: A token :class:`lark.Tree`
        :rtype: Tree
        """

        return self.parser.parse(content.strip())

    def parse(self, content: str, validate: bool = True) -> VersionSelector:
        """Parse a given Semver selector string to the matching selector instance.

        :param str content: The selector string to parse
        :param bool validate: Whether to validate the parsed expression
        :return: The matching :class:`~.selector.VresionSelector` instance for the \
            provided selector string
        :rtype: VersionSelector
        """

        try:
            return self.transformer.transform(self.tokenize(content), validate=validate)
        except VisitError as exc:
            if isinstance(exc.orig_exc, (ParseFailure, InvalidExpression,)):
                raise exc.orig_exc

            raise
