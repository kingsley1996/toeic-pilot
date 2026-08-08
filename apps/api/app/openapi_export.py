"""Print the app's OpenAPI schema to stdout.

Used by scripts/generate-api-types.sh so packages/shared derives its types from
the real contract instead of a hand-maintained copy. sort_keys keeps the output
byte-stable so CI can diff it.
"""

import json

from app.main import app


def main() -> None:
    print(json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
