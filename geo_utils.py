def normalize_lat_lng(first, second):
    """Return (lat, lng). Handles swapped coords from legacy rows or mixed clients."""
    a, b = float(first), float(second)
    if abs(a) > 90 and abs(b) <= 90:
        return b, a
    if abs(b) > 90 and abs(a) <= 90:
        return a, b
    if abs(a) > 45 and abs(b) <= 45:
        return b, a
    if abs(b) > 45 and abs(a) <= 45:
        return a, b
    return a, b
