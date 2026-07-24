"""
Rule Config Loader
-------------------
Lets you define validation rules in a YAML file instead of clicking
through the UI every time. This mirrors how real-world tools like
Great Expectations / dbt tests separate "what to check" (config) from
"how to check it" (engine code).

Example rules.yaml:
--------------------
email_column: email
phone_column: phone
date_column: signup_date
primary_key: customer_id
range_checks:
  - column: age
    min: 0
    max: 120
negative_check_columns:
  - salary
consistency_checks:
  - id_column: customer_id
    value_column: name
fuzzy_name_column: name
fuzzy_threshold: 85
"""

import yaml


DEFAULT_RULES = {
    "email_column": None,
    "phone_column": None,
    "date_column": None,
    "primary_key": None,
    "range_checks": [],
    "negative_check_columns": [],
    "consistency_checks": [],
    "fuzzy_name_column": None,       # kept for backward compatibility (single column)
    "fuzzy_name_columns": [],        # preferred: list of columns to fuzzy-check
    "fuzzy_threshold": 85,
}


def load_rules(path):
    with open(path, "r") as f:
        loaded = yaml.safe_load(f) or {}
    rules = DEFAULT_RULES.copy()
    rules.update(loaded)
    return rules


def save_rules(rules, path):
    with open(path, "w") as f:
        yaml.dump(rules, f, sort_keys=False)


def run_checks_from_rules(checker, rules):
    """Applies a DataQualityChecker instance against a loaded rules dict."""
    checker.check_missing_values()
    checker.check_duplicates()

    if rules.get("email_column"):
        checker.check_email_format(rules["email_column"])
    if rules.get("phone_column"):
        checker.check_phone_format(rules["phone_column"])
    if rules.get("date_column"):
        checker.check_date_format(rules["date_column"])
    if rules.get("primary_key"):
        checker.check_uniqueness(rules["primary_key"])

    for rc in rules.get("range_checks", []):
        checker.check_range(rc["column"], rc["min"], rc["max"])

    for col in rules.get("negative_check_columns", []):
        checker.check_negative_values(col)

    for cc in rules.get("consistency_checks", []):
        checker.check_consistency(cc["id_column"], cc["value_column"])

    fuzzy_cols = list(rules.get("fuzzy_name_columns") or [])
    if rules.get("fuzzy_name_column"):  # legacy single-column key
        fuzzy_cols.append(rules["fuzzy_name_column"])
    for col in dict.fromkeys(fuzzy_cols):  # dedupe, preserve order
        checker.check_fuzzy_duplicates(col, rules.get("fuzzy_threshold", 85))

    return checker
