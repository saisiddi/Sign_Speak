"""Unit tests for the ASL alphabet classifier using synthetic landmarks.
Geometry approximates real hand shapes; validates rule logic end-to-end."""
from asl_alphabet import classify

W = (0.50, 0.90)     # wrist
MM = (0.50, 0.52)    # middle MCP (defines palm scale = 0.38)

def lm(pts):
    class P:
        pass
    out = []
    for i in range(21):
        p = P()
        p.x, p.y, p.z = pts.get(i, (0.5, 0.5, 0.0))[0:2] + (0.0,)
        out.append(p)
    return out

def finger(base_x, mcp_y, extended):
    """Return mcp/pip/tip for a finger at horizontal offset base_x.
    Extended: straight up. Folded: curled down toward palm."""
    if extended:
        return {(0, 0): None}  # unused helper marker

def hand(idx, mid, rng, pky, thumb_out, thumb_tip=(0.35, 0.55), pinch=False):
    """Build a synthetic hand. idx/mid/rng/pky: bool extended. thumb_out: bool."""
    cols = {6: (0.42, 0.46), 10: (0.50, 0.45), 14: (0.58, 0.46), 18: (0.65, 0.48)}   # PIPs
    mcps = {5: (0.42, 0.55), 9: (0.50, 0.52), 13: (0.58, 0.55), 17: (0.65, 0.58)}   # MCPs
    ext_state = {6: idx, 10: mid, 14: rng, 18: pky}
    tip_state = {6: 8, 10: 12, 14: 16, 18: 20}
    pts = {0: W, 9: MM}
    for pip_i, mcp_i in ((6, 5), (10, 9), (14, 13), (18, 17)):
        px, py = cols[pip_i]
        mx, my = mcps[mcp_i]
        pts[mcp_i] = (mx, my)
        pts[pip_i] = (px, py)
        if ext_state[pip_i]:
            pts[tip_state[pip_i]] = (px, py - 0.26)     # straight up
        else:
            pts[tip_state[pip_i]] = (px + 0.02, my + 0.02)  # curled to palm
    # thumb chain: CMC(1) MCP(2) IP(3) TIP(4)
    if thumb_out:
        pts.update({1: (0.44, 0.80), 2: (0.36, 0.72), 3: (0.30, 0.62)})
        pts[4] = (0.25, 0.52) if not pinch else (0.44, 0.42)
    else:
        pts.update({1: (0.44, 0.80), 2: (0.40, 0.74), 3: (0.40, 0.66)})
        pts[4] = (0.44, 0.46) if pinch else (0.46, 0.62)
    return lm(pts)

def splay(h):
    """V shape: index and middle extended but tips spread apart."""
    h[8].x,  h[8].y  = 0.36, 0.22
    h[12].x, h[12].y = 0.56, 0.22
    return h

def crossed(h):
    """R shape: index and middle extended and crossed over each other."""
    h[8].x,  h[8].y  = 0.54, 0.21
    h[12].x, h[12].y = 0.46, 0.20
    return h

def s_shape(h):
    """S shape: fist with the thumb crossing over the front of the fingers."""
    h[4].x, h[4].y = 0.50, 0.44
    return h

CASES = [
    ('B', hand(True, True, True, True, False)),
    ('W', hand(True, True, True, False, False)),
    ('V', splay(hand(True, True, False, False, False))),
    ('U', hand(True, True, False, False, False)),
    ('R', crossed(hand(True, True, False, False, False))),
    ('I', hand(False, False, False, True, False)),
    ('Y', hand(False, False, False, True, True)),
    ('L', hand(True, False, False, False, True)),
    ('F', hand(False, True, True, True, False, pinch=True)),
    ('A', hand(False, False, False, False, True)),
    ('S', s_shape(hand(False, False, False, False, False))),
]

fails = 0
for expect, h in CASES:
    got, score = classify(h)
    ok = got == expect
    fails += not ok
    print(('PASS' if ok else 'FAIL'), f'expected {expect}, got {got} ({score})')
print('RESULT:', 'ALL PASS' if fails == 0 else f'{fails} FAILURES')
