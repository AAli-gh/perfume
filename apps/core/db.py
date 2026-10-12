"""سازگاری با پایگاه داده‌های غیر PostgreSQL (فقط برای اجرای نمایشی، مثل SQLite روی میزبان رایگان).

PostgreSQL پایگاه اصلی و پشتیبانی‌شده است (ADR-0011). روی PostgreSQL هیچ‌کدام از این‌ها رفتار یا schema را
تغییر نمی‌دهند؛ روی پایگاه دیگر:
- ListField: فهرست به‌صورت JSON در یک ستون متنی ذخیره می‌شود (lookupهای آرایه‌ای پشتیبانی نمی‌شوند).
- PostgresOnly: عملیات migration مخصوص PostgreSQL (ایندکس GIN، …) فقط state را به‌روز می‌کند.
- جستجو (catalog.search) به تطبیق متن نرمال‌شده برمی‌گردد.
"""

import json

from django.contrib.postgres.fields import ArrayField
from django.db import connection as default_connection
from django.db.migrations.operations.base import Operation


def is_postgres(connection=None):
    return (connection or default_connection).vendor == "postgresql"


class ListField(ArrayField):
    def db_type(self, connection):
        return super().db_type(connection) if is_postgres(connection) else "text"

    def cast_db_type(self, connection):
        return super().cast_db_type(connection) if is_postgres(connection) else "text"

    def get_placeholder(self, value, compiler, connection):
        return super().get_placeholder(value, compiler, connection) if is_postgres(connection) else "%s"

    def get_db_prep_value(self, value, connection, prepared=False):
        if is_postgres(connection):
            return super().get_db_prep_value(value, connection, prepared)
        return None if value is None else json.dumps(list(value), ensure_ascii=False)

    def from_db_value(self, value, expression, connection):
        if isinstance(value, str) and not is_postgres(connection):
            return json.loads(value)
        return value


class PostgresOnly(Operation):
    """اجرای عملیات درونی فقط روی PostgreSQL؛ state روی همه پایگاه‌ها یکسان می‌ماند."""

    reduces_to_sql = False
    reversible = True

    def __init__(self, operation):
        self.operation = operation

    def deconstruct(self):
        return self.__class__.__qualname__, [self.operation], {}

    def state_forwards(self, app_label, state):
        self.operation.state_forwards(app_label, state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if is_postgres(schema_editor.connection):
            self.operation.database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if is_postgres(schema_editor.connection):
            self.operation.database_backwards(app_label, schema_editor, from_state, to_state)

    def describe(self):
        return f"(PostgreSQL) {self.operation.describe()}"
