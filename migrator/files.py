import re
from pathlib import Path


_VERSION_RE = re.compile(r'^(\d{4})_(.+)\.sql$')


class MigrationFileError(Exception):
    """Raised for invalid migration file format or naming."""


def validate_version_format(version: str):
    """Raise ValueError if version is not a 4-digit string."""
    if not re.fullmatch(r'\d{4}', version):
        raise ValueError(f"Invalid migration version '{version}': must be 4 digits (e.g. '0001')")


def parse_migration_file(path: str | Path) -> dict:
    """Parse a migration file into {version, name, up_sql, down_sql}.

    File must be named NNNN_description.sql and contain a -- migrate:up section.
    The -- migrate:down section is optional (empty string if absent).
    """
    path = Path(path)
    match = _VERSION_RE.match(path.name)
    if not match:
        raise MigrationFileError(
            f"Migration filename '{path.name}' must match NNNN_description.sql"
        )
    version = match.group(1)
    name = match.group(2)

    content = path.read_text()

    # Split on -- migrate:down marker (case-insensitive, optional whitespace)
    parts = re.split(r'--\s*migrate:down', content, maxsplit=1, flags=re.IGNORECASE)

    if not re.search(r'--\s*migrate:up', parts[0], re.IGNORECASE):
        raise MigrationFileError(
            f"Migration '{path.name}' missing '-- migrate:up' marker"
        )

    up_part = re.split(r'--\s*migrate:up', parts[0], maxsplit=1, flags=re.IGNORECASE)[1]
    up_sql = up_part.strip()
    down_sql = parts[1].strip() if len(parts) > 1 else ""

    if not up_sql:
        raise MigrationFileError(f"Migration '{path.name}' has empty up_sql")

    return {
        "version": version,
        "name": name,
        "up_sql": up_sql,
        "down_sql": down_sql,
    }


def load_migrations(migrations_dir: str | Path) -> list[dict]:
    """Load and sort all migration files from a directory.

    Returns list of migration dicts sorted by version ascending.
    Raises MigrationFileError if directory doesn't exist or files are malformed.
    """
    migrations_dir = Path(migrations_dir).resolve()
    if not migrations_dir.exists():
        raise MigrationFileError(f"Migrations directory '{migrations_dir}' does not exist")

    sql_files = sorted(migrations_dir.glob("*.sql"))
    migrations = []
    for f in sql_files:
        if _VERSION_RE.match(f.name):
            migrations.append(parse_migration_file(f))

    # Sort by version (already string-sortable for 4-digit zero-padded versions)
    migrations.sort(key=lambda m: m["version"])
    return migrations
