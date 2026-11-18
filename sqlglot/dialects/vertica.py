from __future__ import annotations

from sqlglot.dialects.postgres import Postgres
from sqlglot.generators.vertica import VerticaGenerator
from sqlglot.parsers.vertica import VerticaParser
from sqlglot.tokens import TokenType


class Vertica(Postgres):
    # https://docs.vertica.com/latest/en/sql-reference/language-elements/lexical-structure/
    Parser = VerticaParser

    Generator = VerticaGenerator

    class Tokenizer(Postgres.Tokenizer):
        KEYWORDS = {
            **Postgres.Tokenizer.KEYWORDS,
            "::!": TokenType.QDCOLON,
            "LONG VARCHAR": TokenType.LONGTEXT,
            "LONG VARBINARY": TokenType.LONGBLOB,
            "PROJECTION": TokenType.PROJECTION,
            "SEGMENTED": TokenType.SEGMENTED,
            "UNSEGMENTED": TokenType.UNSEGMENTED,
        }
