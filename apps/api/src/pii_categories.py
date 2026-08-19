"""Extensible list of PII categories the detection agent looks for.

Deliberately a plain `list[str]`, NOT an enum: new categories can be added
here without touching the detection prompt, the tool-use JSON schema, or any
validation code -- everything downstream (agents/detection_agent.py,
agents/detection_validation.py) derives its allowed-values check from this
list at call/validation time.
"""

PII_CATEGORIES: list[str] = [
    "name",
    "email",
    "phone",
    "address",
    "ssn",
    "date_of_birth",
    "credit_card",
    "bank_account",
    "ip_address",
    "drivers_license",
    "passport",
]
