"""Demo vendor identity used by the internal (vendor-side) reports.

The vendor is fictional; override with the VENDOR_NAME env var.
"""

from __future__ import annotations

import os

VENDOR_NAME = os.environ.get("VENDOR_NAME", "Corbel Analytics")
