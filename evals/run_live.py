"""Optional live evaluation runner placeholder.

The deterministic test suite does not require live Gemini credentials. Use this
file as the extension point for manual model evaluation after deployment
credentials are configured.
"""

from __future__ import annotations


def main() -> None:
    print("Live evaluation is optional; run deterministic tests with pytest.")


if __name__ == "__main__":
    main()
