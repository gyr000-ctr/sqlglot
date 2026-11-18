from __future__ import annotations

from sqlglot import exp
from sqlglot.dialects.dialect import date_delta_sql, rename_func
from sqlglot.generators.postgres import PostgresGenerator


class VerticaGenerator(PostgresGenerator):
    # Vertica supports DECODE natively
    SUPPORTS_DECODE_CASE = True

    TYPE_MAPPING = {
        **PostgresGenerator.TYPE_MAPPING,
        exp.DType.BINARY: "BINARY",
        exp.DType.VARBINARY: "VARBINARY",
        exp.DType.ROWVERSION: "VARBINARY",
        exp.DType.BLOB: "LONG VARBINARY",
        exp.DType.LONGBLOB: "LONG VARBINARY",
        exp.DType.TEXT: "VARCHAR",
        exp.DType.LONGTEXT: "LONG VARCHAR",
    }

    TRANSFORMS = {
        **PostgresGenerator.TRANSFORMS,
        exp.ApproxDistinct: rename_func("APPROXIMATE_COUNT_DISTINCT"),
        exp.DateAdd: date_delta_sql("DATEADD"),
        exp.DateDiff: date_delta_sql("DATEDIFF"),
        exp.GroupConcat: rename_func("LISTAGG"),
        exp.TsOrDsAdd: date_delta_sql("DATEADD"),
        exp.TsOrDsDiff: date_delta_sql("DATEDIFF"),
        # Vertica's safe cast is the ::! operator, e.g. x::!INT
        exp.TryCast: lambda self, e: f"{self.sql(e, 'this')}::!{self.sql(e, 'to')}",
    }

    PROPERTIES_LOCATION = {
        **PostgresGenerator.PROPERTIES_LOCATION,
        exp.SegmentedByProperty: exp.Properties.Location.POST_EXPRESSION,
        exp.UnsegmentedProperty: exp.Properties.Location.POST_EXPRESSION,
    }

    def segmentedbyproperty_sql(self, expression: exp.SegmentedByProperty) -> str:
        this = self.sql(expression, "this")
        all_nodes = " ALL NODES" if expression.args.get("all_nodes") else ""
        ksafe = self.sql(expression, "ksafe")
        ksafe = f" KSAFE {ksafe}" if ksafe else ""
        return f"SEGMENTED BY {this}{all_nodes}{ksafe}"

    def unsegmentedproperty_sql(self, expression: exp.UnsegmentedProperty) -> str:
        return f"UNSEGMENTED{' ALL NODES' if expression.args.get('all_nodes') else ''}"
