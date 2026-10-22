import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional

import aiosqlite
from fastmcp import FastMCP

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("EXPENSES_DB_PATH", str(BASE_DIR / "expenses.db")))
CATEGORIES_PATH = BASE_DIR / "categories.json"

mcp = FastMCP("ExpenseTracker")


def init_db() -> None:
    """Create the SQLite database and required schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO expenses(date, amount, category) VALUES (?, ?, ?)",
            ("2000-01-01", 0.0, "test"),
        )
        conn.execute("DELETE FROM expenses WHERE category = 'test'")


@mcp.tool()
async def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Add a new expense entry to the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                "INSERT INTO expenses(date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
                (date, amount, category, subcategory, note),
            )
            expense_id = cursor.lastrowid
            await conn.commit()
            return {
                "status": "success",
                "id": expense_id,
                "message": "Expense added successfully",
            }
    except Exception as exc:  # pragma: no cover - runtime safety
        if "readonly" in str(exc).lower():
            return {
                "status": "error",
                "message": "Database is in read-only mode. Check file permissions.",
            }
        return {"status": "error", "message": f"Database error: {str(exc)}"}


@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """List expense entries within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date),
            )
            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as exc:
        return [{"status": "error", "message": f"Error listing expenses: {str(exc)}"}]


@mcp.tool()
async def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Summarize expenses by category within an inclusive date range."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            query = """
                SELECT category, SUM(amount) AS total_amount, COUNT(*) as count
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            params: list[Any] = [start_date, end_date]

            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total_amount DESC"

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row)) for row in rows]
    except Exception as exc:
        return [{"status": "error", "message": f"Error summarizing expenses: {str(exc)}"}]


@mcp.resource("expense:///categories", mime_type="application/json")
def categories() -> str:
    """Return the configured expense categories as JSON."""
    default_categories = {
        "categories": [
            "Food & Dining",
            "Transportation",
            "Shopping",
            "Entertainment",
            "Bills & Utilities",
            "Healthcare",
            "Travel",
            "Education",
            "Business",
            "Other",
        ]
    }

    if CATEGORIES_PATH.exists():
        try:
            return CATEGORIES_PATH.read_text(encoding="utf-8")
        except OSError:
            pass

    return json.dumps(default_categories, indent=2)


def main() -> None:
    """Initialize storage and start the FastMCP HTTP server."""
    init_db()
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
