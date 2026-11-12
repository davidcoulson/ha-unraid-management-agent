"""Small helpers shared by the platform modules."""

from __future__ import annotations

import functools

from homeassistant.util import slugify

# Entity keys slugify the same device names on every coordinator update, and
# slugify is slow (it transliterates), so reuse the result per input.
cached_slugify = functools.lru_cache(maxsize=4096)(slugify)
