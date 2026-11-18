from __future__ import annotations

import typing as t

from sqlglot import exp
from sqlglot.helper import seq_get
from sqlglot.parsers.postgres import PostgresParser
from sqlglot.tokens import Token, TokenType
from sqlglot.dialects.dialect import map_date_part
from builtins import type as Type

if t.TYPE_CHECKING:
    from sqlglot._typing import E


def _build_date_delta(expr_type: Type[E]) -> t.Callable[[list], E]:
    # Vertica's DATEADD/TIMESTAMPADD/DATEDIFF/TIMESTAMPDIFF all take
    # (date_part, start|interval, end|date) like their Redshift counterparts
    def _builder(args: list) -> E:
        expr = expr_type(
            this=seq_get(args, 2),
            expression=seq_get(args, 1),
            unit=map_date_part(seq_get(args, 0)),
        )
        if expr_type is exp.TsOrDsAdd:
            expr.set("return_type", exp.DType.TIMESTAMP.into_expr())

        return expr

    return _builder


class VerticaParser(PostgresParser):
    # SEGMENTED/UNSEGMENTED are only keywords in the CREATE PROJECTION context, so they
    # remain valid identifiers elsewhere; they're excluded from TABLE_ALIAS_TOKENS (inherited)
    # so the segmentation clause isn't mistaken for a table alias
    ID_VAR_TOKENS = {
        *PostgresParser.ID_VAR_TOKENS,
        TokenType.SEGMENTED,
        TokenType.UNSEGMENTED,
    }
    ALIAS_TOKENS = ID_VAR_TOKENS

    # Enables DROP PROJECTION; CREATE PROJECTION is handled by _parse_create_projection
    CREATABLES = {*PostgresParser.CREATABLES, TokenType.PROJECTION}

    FUNCTIONS = {
        **PostgresParser.FUNCTIONS,
        "APPROXIMATE_COUNT_DISTINCT": exp.ApproxDistinct.from_arg_list,
        "DATEADD": _build_date_delta(exp.TsOrDsAdd),
        "DATEDIFF": _build_date_delta(exp.TsOrDsDiff),
        "LISTAGG": exp.GroupConcat.from_arg_list,
        "NULLIFZERO": lambda args: exp.Nullif(
            this=seq_get(args, 0), expression=exp.Literal.number(0)
        ),
        "TIMESTAMPADD": _build_date_delta(exp.TsOrDsAdd),
        "TIMESTAMPDIFF": _build_date_delta(exp.TsOrDsDiff),
        "ZEROIFNULL": lambda args: exp.Coalesce(
            this=seq_get(args, 0), expressions=[exp.Literal.number(0)]
        ),
    }

    COLUMN_OPERATORS = {
        **PostgresParser.COLUMN_OPERATORS,
        # Vertica's ::! is a "safe" cast that returns NULL instead of erroring
        TokenType.QDCOLON: lambda self, this, to: self.build_cast(False, this=this, to=to),
    }

    CAST_COLUMN_OPERATORS = {
        *PostgresParser.CAST_COLUMN_OPERATORS,
        TokenType.QDCOLON,
    }

    def _parse_command(self) -> exp.Command:
        self.raise_error(f"Unsupported statement: {self._prev.text.upper()}")
        return super()._parse_command()

    def _parse_as_command(self, start: Token) -> exp.Command:
        self.raise_error(f"Unsupported statement: {start.text.upper()}")
        return super()._parse_as_command(start)

    def _parse_create(self) -> exp.Create | exp.Command:
        index = self._index
        replace = self._match_pair(TokenType.OR, TokenType.REPLACE)

        if self._match(TokenType.PROJECTION):
            return self._parse_create_projection(replace=replace)

        self._retreat(index)
        return super()._parse_create()

    def _parse_create_projection(self, replace: bool) -> exp.Create:
        # https://docs.vertica.com/latest/en/sql-reference/statements/create-statements/create-projection/
        exists = self._parse_exists(not_=True)
        this = self._parse_schema(this=self._parse_table_parts(schema=True))

        if not self._match(TokenType.ALIAS):
            self.raise_error("Expecting AS in CREATE PROJECTION")

        expression = self._parse_ddl_select()

        properties: list[exp.Expr] = []
        if self._match(TokenType.SEGMENTED):
            if not self._match_text_seq("BY"):
                self.raise_error("Expecting BY after SEGMENTED")

            segmented_by = self._parse_bitwise()
            if segmented_by is None:
                self.raise_error("Expecting segmentation expression")

            all_nodes = self._match_text_seq("ALL", "NODES")
            ksafe = self._match_text_seq("KSAFE") and self._parse_number()
            properties.append(
                exp.SegmentedByProperty(
                    this=segmented_by, all_nodes=all_nodes or None, ksafe=ksafe or None
                )
            )
        elif self._match(TokenType.UNSEGMENTED):
            all_nodes = self._match_text_seq("ALL", "NODES")
            properties.append(exp.UnsegmentedProperty(all_nodes=all_nodes or None))

        return self.expression(
            exp.Create(
                this=this,
                kind="PROJECTION",
                replace=replace,
                expression=expression,
                exists=exists,
                properties=exp.Properties(expressions=properties) if properties else None,
            )
        )
