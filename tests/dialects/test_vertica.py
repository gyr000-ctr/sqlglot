from sqlglot import ParseError, exp
from tests.dialects.test_dialect import Validator


class TestVertica(Validator):
    dialect = "vertica"

    def test_types(self):
        self.validate_identity("SELECT CAST(x AS LONG VARCHAR) FROM t")
        self.validate_identity("SELECT CAST(x AS LONG VARBINARY) FROM t")
        self.validate_identity("SELECT x::LONG VARCHAR FROM t", "SELECT CAST(x AS LONG VARCHAR) FROM t")
        self.validate_identity("CREATE TABLE t (a LONG VARCHAR, b LONG VARBINARY, c UUID)")

        # Generic types map to native Vertica types
        self.validate_all(
            "SELECT CAST(x AS VARCHAR) FROM t",
            read={"postgres": "SELECT CAST(x AS TEXT) FROM t"},
        )
        self.validate_all(
            "SELECT CAST(x AS VARBINARY) FROM t",
            read={"postgres": "SELECT CAST(x AS BYTEA) FROM t"},
        )

    def test_casts(self):
        # Vertica's ::! operator is a safe cast that returns NULL on failure
        self.validate_identity("SELECT x::!INT FROM t")
        self.validate_identity("SELECT x::!LONG VARCHAR FROM t")
        self.validate_all(
            "SELECT x::!INT FROM t",
            read={"duckdb": "SELECT TRY_CAST(x AS INT) FROM t"},
        )
        self.assertIsInstance(
            self.parse_one("SELECT x::!INT FROM t").expressions[0], exp.TryCast
        )

    def test_create_projection(self):
        self.validate_identity(
            "CREATE PROJECTION p AS SELECT a, b FROM t SEGMENTED BY HASH(a) ALL NODES"
        )
        self.validate_identity(
            "CREATE PROJECTION p AS SELECT a, b FROM t SEGMENTED BY HASH(a, b) ALL NODES KSAFE 1"
        )
        self.validate_identity("CREATE PROJECTION p AS SELECT a, b FROM t UNSEGMENTED ALL NODES")
        self.validate_identity("CREATE PROJECTION p AS SELECT a, b FROM t UNSEGMENTED")
        self.validate_identity(
            "CREATE OR REPLACE PROJECTION s.p (a, b) AS SELECT a, b FROM t SEGMENTED BY HASH(a)"
        )
        self.validate_identity(
            "CREATE PROJECTION IF NOT EXISTS p AS SELECT a FROM t ORDER BY a SEGMENTED BY HASH(a) ALL NODES"
        )

        create = self.parse_one(
            "CREATE PROJECTION p AS SELECT a, b FROM t SEGMENTED BY HASH(a) ALL NODES"
        )
        self.assertIsInstance(create, exp.Create)
        self.assertEqual(create.kind, "PROJECTION")

    def test_drop_projection(self):
        self.validate_identity("DROP PROJECTION p")
        self.validate_identity("DROP PROJECTION IF EXISTS p")

    def test_functions(self):
        self.validate_identity("SELECT DATEDIFF(day, a, b) FROM t", "SELECT DATEDIFF(DAY, a, b) FROM t")
        self.validate_identity(
            "SELECT TIMESTAMPDIFF(hour, a, b) FROM t", "SELECT DATEDIFF(HOUR, a, b) FROM t"
        )
        self.validate_identity("SELECT DATEADD(day, 1, a) FROM t", "SELECT DATEADD(DAY, 1, a) FROM t")
        self.validate_identity(
            "SELECT TIMESTAMPADD(day, 1, a) FROM t", "SELECT DATEADD(DAY, 1, a) FROM t"
        )
        self.validate_identity("SELECT ZEROIFNULL(a) FROM t", "SELECT COALESCE(a, 0) FROM t")
        self.validate_identity("SELECT NULLIFZERO(a) FROM t", "SELECT NULLIF(a, 0) FROM t")
        self.validate_identity("SELECT APPROXIMATE_COUNT_DISTINCT(x) FROM t")
        self.validate_identity("SELECT LISTAGG(a, ',') FROM t")
        self.validate_identity("SELECT DECODE(a, 1, 'one', 'other') FROM t")

        self.validate_all(
            "SELECT LISTAGG(a, ',') FROM t",
            read={"postgres": "SELECT STRING_AGG(a, ',') FROM t"},
        )
        self.validate_all(
            "SELECT DATEDIFF(DAY, a, b) FROM t",
            read={"redshift": "SELECT DATEDIFF(day, a, b) FROM t"},
        )

    def test_unsupported_syntax_raises(self):
        # Unsupported statements must raise a distinguishable ParseError
        # instead of silently degrading to exp.Command
        for sql in (
            "SHOW ALL",
            "VACUUM t",
            "CREATE FOO bar",
            "CREATE TABLE t (a INT) SEGMENTED BY HASH(a)",
            "CREATE PROJECTION p SELECT a FROM t",
            "CREATE PROJECTION p AS SELECT a FROM t SEGMENTED HASH(a)",
        ):
            with self.subTest(sql=sql), self.assertRaises(ParseError):
                self.parse_one(sql)

    def test_vertica(self):
        self.validate_identity(
            "SELECT a::INT, b::TIMESTAMPTZ FROM t",
            "SELECT CAST(a AS INT), CAST(b AS TIMESTAMPTZ) FROM t",
        )
        # SEGMENTED/UNSEGMENTED remain usable as identifiers outside CREATE PROJECTION
        self.validate_identity("SELECT segmented, unsegmented FROM t")
        self.validate_identity("SELECT a AS segmented FROM t")
        self.validate_identity("SELECT 1 /* comment */")
