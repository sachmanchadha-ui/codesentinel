import sys
import os
from typing import List, Dict, Any, Tuple
import re

# Add the parent directory to sys.path to enable imports when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from server.scenarios import SCENARIOS
except ImportError:
    # Fallback for when scenarios isn't available
    SCENARIOS = {}

LINE_TOLERANCE = 2
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def parse_line_range(line_range: str) -> Tuple[int, int]:
    """Parse a string like '12' or '23-27' or 'lines 23 to 27' into a (start, end) int tuple."""
    # Strip whitespace from input
    line_range = line_range.strip()
    # Use re.findall(r'\d+', line_range) to extract all numbers
    numbers = re.findall(r"\d+", line_range)
    # If zero numbers found: return (0, 0)
    if len(numbers) == 0:
        return (0, 0)
    # If one number found: return (n, n)
    if len(numbers) == 1:
        n = int(numbers[0])
        return (n, n)
    # If two or more numbers found: return (first, last)
    first = int(numbers[0])
    last = int(numbers[-1])
    return (first, last)


def location_match(finding_line_range: str, bug_start: int, bug_end: int) -> bool:
    """Return True if the finding's line range overlaps with the bug's location (with LINE_TOLERANCE applied)."""
    # Call parse_line_range on finding_line_range to get (f_start, f_end)
    f_start, f_end = parse_line_range(finding_line_range)
    # If f_start == 0 and f_end == 0: return False
    if f_start == 0 and f_end == 0:
        return False
    # Expand bug range: expanded_start = bug_start - LINE_TOLERANCE, expanded_end = bug_end + LINE_TOLERANCE
    expanded_start = bug_start - LINE_TOLERANCE
    expanded_end = bug_end + LINE_TOLERANCE
    # Return True if ranges overlap: f_start <= expanded_end AND f_end >= expanded_start
    return f_start <= expanded_end and f_end >= expanded_start


def keyword_match(description: str, keywords: List[str]) -> bool:
    """Return True if any keyword appears in the description (case-insensitive)."""
    # Convert description to lowercase
    description_lower = description.lower()
    # Return True if any keyword.lower() is found as a substring in description_lower
    for keyword in keywords:
        if keyword.lower() in description_lower:
            return True
    return False


def severity_score(found: str, actual: str) -> float:
    """Score how close the agent's severity call is to ground truth."""
    # If found == actual: return 1.0
    if found == actual:
        return 1.0
    # Get diff = abs(SEVERITY_ORDER.get(found, 4) - SEVERITY_ORDER.get(actual, 4))
    found_order = SEVERITY_ORDER.get(found, 4)
    actual_order = SEVERITY_ORDER.get(actual, 4)
    diff = abs(found_order - actual_order)
    # If diff == 1: return 0.5
    if diff == 1:
        return 0.5
    # Else: return 0.0
    return 0.0


def grade(task_id: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Main grading function. Returns a result dict with score and breakdown."""
    # Load scenario = SCENARIOS.get(task_id)
    scenario = SCENARIOS.get(task_id)
    # If scenario is None: return {"score": 0.0, "error": f"Unknown task: {task_id}", "breakdown": []}
    if scenario is None:
        return {"score": 0.0, "error": f"Unknown task: {task_id}", "breakdown": []}

    # Load planted_bugs = scenario["planted_bugs"]
    planted_bugs = scenario["planted_bugs"]
    # Initialize: total_score = 0.0, breakdown = [], matched_bug_ids = set()
    total_score = 0.0
    breakdown = []
    matched_bug_ids = set()

    # For each finding in findings (finding is a dict with keys: line_range, description, severity):
    for finding in findings:
        # Extract line_range = finding.get("line_range", "")
        line_range = finding.get("line_range", "")
        # Extract description = finding.get("description", "")
        description = finding.get("description", "")
        # Extract found_severity = finding.get("severity", "P3")
        found_severity = finding.get("severity", "P3")

        # For each bug in planted_bugs:
        for bug in planted_bugs:
            # If bug["bug_id"] already in matched_bug_ids: skip
            if bug["bug_id"] in matched_bug_ids:
                continue
            # Check loc = location_match(line_range, bug["line_start"], bug["line_end"])
            loc = location_match(line_range, bug["line_start"], bug["line_end"])
            # Check kw = keyword_match(description, bug["keywords"])
            kw = keyword_match(description, bug["keywords"])
            # If loc OR kw is True:
            if loc or kw:
                # base_score = bug["weight"] if loc else bug["weight"] * 0.5
                base_score = bug["weight"] if loc else bug["weight"] * 0.5
                # sev = severity_score(found_severity, bug["severity"])
                sev = severity_score(found_severity, bug["severity"])
                # sev_bonus = bug["weight"] * 0.1 * sev if loc else 0.0
                sev_bonus = bug["weight"] * 0.1 * sev if loc else 0.0
                # bug_score = round(min(base_score + sev_bonus, bug["weight"]), 4)
                bug_score = round(min(base_score + sev_bonus, bug["weight"]), 4)
                # total_score += bug_score
                total_score += bug_score
                # matched_bug_ids.add(bug["bug_id"])
                matched_bug_ids.add(bug["bug_id"])
                # Append to breakdown: {"bug_id": bug["bug_id"], "found": True, "location_match": loc, "keyword_match": kw, "severity_score": sev, "score_earned": bug_score, "max_possible": bug["weight"]}
                breakdown.append(
                    {
                        "bug_id": bug["bug_id"],
                        "found": True,
                        "location_match": loc,
                        "keyword_match": kw,
                        "severity_score": sev,
                        "score_earned": bug_score,
                        "max_possible": bug["weight"],
                    }
                )
                # Break out of inner loop (move to next finding)
                break

    # After processing all findings, for each bug whose bug_id is NOT in matched_bug_ids:
    for bug in planted_bugs:
        if bug["bug_id"] not in matched_bug_ids:
            # Append to breakdown: {"bug_id": bug["bug_id"], "found": False, "score_earned": 0.0, "max_possible": bug["weight"]}
            breakdown.append(
                {
                    "bug_id": bug["bug_id"],
                    "found": False,
                    "score_earned": 0.0,
                    "max_possible": bug["weight"],
                }
            )

    # final_score = round(min(total_score, 1.0), 2)
    final_score = round(min(total_score, 1.0), 2)
    # Return: {"score": final_score, "bugs_found": len(matched_bug_ids), "bugs_total": len(planted_bugs), "breakdown": breakdown}
    return {
        "score": final_score,
        "bugs_found": len(matched_bug_ids),
        "bugs_total": len(planted_bugs),
        "breakdown": breakdown,
    }


def grade_from_models(task_id: str, findings_models) -> Dict[str, Any]:
    """Convenience wrapper that accepts a list of Finding Pydantic model instances."""
    # Convert each finding model to dict using finding.model_dump()
    findings_dicts = [finding.model_dump() for finding in findings_models]
    # Call grade(task_id, list_of_dicts)
    return grade(task_id, findings_dicts)


if __name__ == "__main__":
    # Quick smoke test
    test_findings_easy = [
        {
            "line_range": "9",
            "description": "off-by-one error returns n+1 elements",
            "severity": "P2",
        },
        {
            "line_range": "12-13",
            "description": "no empty list check causes ZeroDivisionError",
            "severity": "P2",
        },
    ]
    result = grade("easy_review", test_findings_easy)
    print(
        f"Easy task smoke test: score={result['score']}, bugs_found={result['bugs_found']}/{result['bugs_total']}"
    )
    assert result["score"] > 0.9, f"Smoke test failed: {result}"
    print("Smoke test PASSED")
