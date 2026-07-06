"""defect_review_config.py — print the defect_review config (defaults merged) as JSON.

Exists so headless runs can allowlist per-script commands: the inline
`python -c` equivalent would force allowing arbitrary code execution.
Run from inside a wiki checkout (config is located from the working dir).
"""

import json

import config

if __name__ == "__main__":
    print(json.dumps(config.defect_review_config()))
