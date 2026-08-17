"""
SignSpeak - ASL Alphabet Database (fingerspelling)
==================================================
Static-letter recognition from MediaPipe hand landmarks. Each rule encodes
the ASL handshape for one letter using finger-extension geometry. Covers the
statically-distinguishable subset of the ASL manual alphabet; letters that
need motion (G H J K P Q X Z) or subtle tucks (M N R S T) are excluded on
purpose so recognition stays reliable.

This runs only when the MediaPipe gesture recognizer returns no whole-hand
gesture, so it never interferes with the 7 primary gestures.
"""
import math

# MediaPipe hand landmark indices
WRIST      = 0
THUMB_IP   = 3
THUMB_TIP  = 4
INDEX_MCP  = 5
INDEX_PIP  = 6
INDEX_TIP  = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_MCP   = 13
RING_PIP   = 14
RING_TIP   = 16
PINKY_MCP  = 17
PINKY_PIP  = 18
PINKY_TIP  = 20

# Thresholds in palm-length units (wrist -> middle MCP = 1.0)
_EXT_MARGIN  = 1.15   # fingertip further from wrist than PIP by this ratio = extended
_FOLD_LIMIT  = 0.90   # below this ratio the finger counts as folded
_THUMB_OUT   = 0.90   # thumb tip to pinky MCP distance for "thumb extended"
_PINCH       = 0.35   # thumb-index tip distance for pinched shapes (F)
_O_PINCH     = 0.22   # tighter pinch for O (fingertips meet the thumb)
_V_GAP       = 0.35   # index-middle tip gap separating V (apart) from U (together)

# The alphabet this database currently recognizes
LETTERS = "ABCDEFILORSUVWY"


def _d(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def classify(lms):
    """Classify a hand pose. lms: MediaPipe NormalizedLandmark list (21 pts).
    Returns (letter_or_None, confidence)."""
    scale = _d(lms[WRIST], lms[MIDDLE_MCP]) or 0.001

    def d(i, j):
        return _d(lms[i], lms[j]) / scale

    def ratio(pip, tip):
        return d(WRIST, tip) / max(d(WRIST, pip), 1e-6)

    r_i = ratio(INDEX_PIP, INDEX_TIP)
    r_m = ratio(MIDDLE_PIP, MIDDLE_TIP)
    r_r = ratio(RING_PIP, RING_TIP)
    r_p = ratio(PINKY_PIP, PINKY_TIP)
    idx, mid, rng, pky = r_i > _EXT_MARGIN, r_m > _EXT_MARGIN, r_r > _EXT_MARGIN, r_p > _EXT_MARGIN
    folded   = max(r_i, r_m, r_r, r_p) < _FOLD_LIMIT
    curved   = all(_FOLD_LIMIT <= r <= _EXT_MARGIN for r in (r_i, r_m, r_r, r_p))
    thumb    = d(THUMB_TIP, PINKY_MCP) > _THUMB_OUT
    pinch    = d(THUMB_TIP, INDEX_TIP)
    thumb_mid = d(THUMB_TIP, MIDDLE_TIP)

    if idx and mid and rng and pky:
        return ('B', 0.80)                       # four fingers up
    if idx and mid and rng:
        return ('W', 0.85)                       # three fingers up
    if idx and mid and not rng and not pky:
        # R = index and middle crossed (x-ordering flips between PIP and tip)
        crossed = (lms[INDEX_TIP].x - lms[MIDDLE_TIP].x) * \
                  (lms[INDEX_PIP].x - lms[MIDDLE_PIP].x) < 0
        gap = d(INDEX_TIP, MIDDLE_TIP)
        if crossed and gap < 0.45:
            return ('R', 0.80)
        return ('V' if gap > _V_GAP else 'U', 0.85)
    if idx and not mid and not rng and not pky:
        if thumb and pinch > 0.8:
            return ('L', 0.90)                   # index up + thumb out
        return ('D', 0.80)                       # index up, thumb beside it
    if pky and not idx and not mid and not rng:
        return ('Y' if thumb else 'I', 0.85)
    if mid and rng and pky and not idx and pinch < _PINCH:
        return ('F', 0.85)                       # thumb-index pinch
    if folded:
        if pinch < _O_PINCH and thumb_mid < 0.55:
            return ('O', 0.75)                   # fingertips meet thumb in a circle
        if d(THUMB_TIP, MIDDLE_PIP) < 0.40:
            return ('S', 0.75)                   # thumb crossing over the fingers
        if not thumb and d(THUMB_TIP, INDEX_PIP) < 0.50:
            return ('E', 0.70)                   # fingers down, thumb tucked
        if thumb:
            return ('A', 0.75)                   # fist with thumb at the side
    if curved and 0.35 < pinch < 0.95:
        return ('C', 0.70)                       # curved open hand, thumb opposing
    return (None, 0.0)
