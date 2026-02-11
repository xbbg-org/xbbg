"""SQLite query string builders and small convenience helpers."""

import json


def db_value(val) -> str:
    """Database value as in query string."""
    if isinstance(val, str):
        return json.dumps(val.replace('"', "").strip())
    return json.dumps(val, default=str)


def select(table: str, cond="", **kwargs) -> str:
    """Query string of SELECT statement.

    Args:
        table: table name
        cond: conditions
        **kwargs: data as kwargs

    Returns:
        str: Query string.

    Examples:
        >>> q1 = select("daily", ticker="ES1 Index", price=3000)
        >>> q1.splitlines()[-2].strip()
        'ticker="ES1 Index" AND price=3000'
        >>> q2 = select("daily", cond="price > 3000", ticker="ES1 Index")
        >>> q2.splitlines()[-2].strip()
        'price > 3000 AND ticker="ES1 Index"'
        >>> q3 = select("daily", cond="price > 3000")
        >>> q3.splitlines()[-2].strip()
        'price > 3000'
        >>> select("daily")
        'SELECT * FROM `daily`'
    """
    all_cond = [cond] + [f"{key}={db_value(value)}" for key, value in kwargs.items()]
    where = " AND ".join(filter(bool, all_cond))
    s = f"SELECT * FROM `{table}`"
    if where:
        return f"""
            {s}
            WHERE
            {where}
        """
    return s


def replace_into(table: str, **kwargs) -> str:
    """Query string of REPLACE INTO statement.

    Args:
        table: table name
        **kwargs: data as kwargs

    Returns:
        str: Query string.

    Examples:
        >>> query = replace_into("daily", ticker="ES1 Index", price=3000)
        >>> query.splitlines()[1].strip()
        'REPLACE INTO `daily` (ticker, price)'
        >>> query.splitlines()[2].strip()
        'VALUES ("ES1 Index", 3000)'
    """
    return f"""
        REPLACE INTO `{table}` ({", ".join(list(kwargs.keys()))})
        VALUES ({", ".join(map(db_value, list(kwargs.values())))})
    """
