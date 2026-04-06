from typing import Dict, Any

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "easy_review": {
        "task_description": (
            "This Python module handles leaderboard score processing for a competitive gaming platform. "
            "The get_top_scores function should return exactly the top N scores from a list, sorted descending. "
            "The calculate_average function should return the arithmetic mean of a list of numeric scores. "
            "Both functions are called frequently in production."
        ),
        "code_snippet": """\
# leaderboard.py
# Leaderboard score processing for GameRank platform

def get_top_scores(scores, n):
    \"\"\"Return the top n scores from the list, sorted descending.\"\"\"
    if scores is None:
        return []
    sorted_scores = sorted(scores, reverse=True)
    return sorted_scores[:n + 1]

def calculate_average(scores):
    \"\"\"Calculate the arithmetic mean of a list of numeric scores.\"\"\"
    total = sum(scores)
    return total / len(scores)

def normalize_score(score, max_score):
    \"\"\"Normalize score to 0.0-1.0 range.\"\"\"
    if max_score == 0:
        return 0.0
    return min(score / max_score, 1.0)
""",
        "additional_context": (
            "This module runs in a FastAPI service handling ~10k requests/minute. "
            "get_top_scores is called with n values between 1 and 100. "
            "calculate_average is called with score lists from the database — "
            "the database query does NOT filter out NULL rows, and empty result sets are possible."
        ),
        "planted_bugs": [
            {
                "bug_id": "E1",
                "line_start": 9,
                "line_end": 9,
                "severity": "P2",
                "weight": 0.55,
                "keywords": [
                    "off-by-one",
                    "off by one",
                    "n+1",
                    "extra element",
                    "one too many",
                    "returns n+1",
                    "should be [:n]",
                    "incorrect slice",
                ],
                "description": "Off-by-one error: sorted_scores[:n + 1] returns n+1 elements instead of n.",
            },
            {
                "bug_id": "E2",
                "line_start": 12,
                "line_end": 13,
                "severity": "P2",
                "weight": 0.45,
                "keywords": [
                    "none check",
                    "null check",
                    "empty list",
                    "division by zero",
                    "zerodivisionerror",
                    "empty scores",
                    "no guard",
                    "missing check",
                ],
                "description": "No None check or empty list guard before sum/division. Raises TypeError or ZeroDivisionError.",
            },
        ],
    },
    "medium_review": {
        "task_description": (
            "This Node.js module manages user wallet balance updates for a fintech application. "
            "The updateUserBalance function is called when users make purchases or receive rewards. "
            "It reads the current balance, adds the amount (positive or negative), and saves. "
            "This runs in a multi-user environment with concurrent requests possible."
        ),
        "code_snippet": """\
// wallet.js
// User wallet balance management for FinCore platform

const db = require('./database');
const logger = require('./logger');

async function updateUserBalance(userId, amount) {
    try {
        const user = await db.users.findOne({ id: userId });
        const newBalance = user.balance + amount;
        await db.users.update({ id: userId }, { balance: newBalance });
        return { success: true, balance: newBalance };
    } catch (e) {
        console.log('update failed');
    }

async function getUserBalance(userId) {
    const user = await db.users.findOne({ id: userId });
    return user ? user.balance : 0;
}

module.exports = { updateUserBalance, getUserBalance };
""",
        "additional_context": (
            "FinCore processes up to 500 concurrent balance updates per second during peak hours. "
            "The database is PostgreSQL. db.users.update uses a standard UPDATE WHERE clause — "
            "it is NOT wrapped in a transaction by default. "
            "The updateUserBalance function is called directly from the HTTP request handler with no queuing."
        ),
        "planted_bugs": [
            {
                "bug_id": "M1",
                "line_start": 8,
                "line_end": 10,
                "severity": "P1",
                "weight": 0.55,
                "keywords": [
                    "race condition",
                    "atomic",
                    "non-atomic",
                    "read-then-write",
                    "concurrent",
                    "toctou",
                    "time of check",
                    "transaction",
                    "lost update",
                    "optimistic lock",
                ],
                "description": "Race condition: read-then-write balance update is non-atomic. Concurrent requests cause lost updates.",
            },
            {
                "bug_id": "M2",
                "line_start": 12,
                "line_end": 13,
                "severity": "P2",
                "weight": 0.45,
                "keywords": [
                    "swallowed",
                    "silent failure",
                    "catch",
                    "error handling",
                    "undefined",
                    "re-throw",
                    "rethrow",
                    "return error",
                    "missing return",
                    "no rethrow",
                    "caller gets undefined",
                ],
                "description": "Swallowed exception: catch block does not re-throw or return an error object. Callers receive undefined and cannot detect failures.",
            },
        ],
    },
    "hard_review": {
        "task_description": (
            "This Python Flask API endpoint handles admin retrieval of user reward points for an e-commerce platform. "
            "It queries a SQLite rewards database, sums a user's points, and applies an optional multiplier. "
            "This endpoint is documented as internal/admin-only in the API spec."
        ),
        "code_snippet": """\
# rewards_api.py
# Admin rewards management endpoint for ShopCore platform

from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/api/admin/user-rewards', methods=['GET'])
def get_user_rewards():
    user_id = request.args.get('user_id')
    multiplier = request.args.get('multiplier', 1)

    conn = sqlite3.connect('rewards.db')
    cursor = conn.cursor()

    query = f"SELECT * FROM rewards WHERE user_id = {user_id}"
    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    total_points = sum(row[2] for row in results)
    final_points = total_points * multiplier

    return jsonify({
        'user_id': user_id,
        'total_points': final_points,
        'status': 'ok'
    })

if __name__ == '__main__':
    app.run(debug=True)
""",
        "additional_context": (
            "ShopCore uses Flask with no authentication middleware on this service. "
            "Authentication is supposed to be handled by checking a session token in the request headers "
            "using the require_admin_token decorator — but the developer forgot to add it. "
            "The rewards table schema: id INTEGER, user_id INTEGER, points INTEGER, created_at TEXT. "
            "The multiplier parameter is meant to be a float for promotional campaigns."
        ),
        "planted_bugs": [
            {
                "bug_id": "H1",
                "line_start": 10,
                "line_end": 10,
                "severity": "P0",
                "weight": 0.40,
                "keywords": [
                    "authentication",
                    "auth",
                    "unauthorized",
                    "unauthenticated",
                    "access control",
                    "missing decorator",
                    "no auth",
                    "missing auth",
                    "require_admin",
                    "anyone can access",
                    "broken access",
                ],
                "description": "Missing authentication: admin endpoint has no auth check. Any unauthenticated user can access all user reward data.",
            },
            {
                "bug_id": "H2",
                "line_start": 16,
                "line_end": 16,
                "severity": "P0",
                "weight": 0.35,
                "keywords": [
                    "sql injection",
                    "injection",
                    "f-string",
                    "f string",
                    "parameterized",
                    "sanitize",
                    "escape",
                    "string interpolation",
                    "execute with params",
                    "user input in query",
                ],
                "description": "SQL injection: user_id from request is interpolated directly into SQL query via f-string. Attacker can exfiltrate or destroy the database.",
            },
            {
                "bug_id": "H3",
                "line_start": 21,
                "line_end": 21,
                "severity": "P1",
                "weight": 0.25,
                "keywords": [
                    "type cast",
                    "integer",
                    "multiplier type",
                    "string multiplication",
                    "no int()",
                    "no float()",
                    "wrong type",
                    "unvalidated input",
                    "string not number",
                    "type error",
                ],
                "description": "Missing type cast: multiplier from request.args is a string. Multiplying an int by a string causes TypeError or wrong string-repetition behavior.",
            },
        ],
    },
}
