"""Add a line to the translators' credit in the ending staff roll.

The staff roll lines of CHR_VS7.MF are 16-pixel high 4bpp sprites in a
proportional outlined font (stroke colour 4, outline colour 2). The new
line is drawn in the same style as the last line of the translators'
credit.
"""
import struct

import vsmerge

HELP_LINE = 223          # "with help from"
LAST_LINE = 224          # "Katrin & Danthrax", end of the translators' credit
LINE = 'Ported by Zanac'

# glyph strokes (X), (first row, rows); the outline (2) is added around
STROKES = {
    'P': (1, ['XXXXX ', 'X    X', 'X    X', 'X    X', 'XXXXX ', 'X     ', 'X     ', 'X     ',
              'X     ', 'X     ', 'X     ']),
    'Z': (1, ['XXXXXX', '     X', '    X ', '    X ', '   X  ', '   X  ', '  X   ', '  X   ',
              ' X    ', 'X     ', 'XXXXXX']),
    'o': (5, [' XXXX ', 'X    X', 'X    X', 'X    X', 'X    X', 'X    X', ' XXXX ']),
    'a': (5, [' XXXX ', '     X', ' XXXXX', 'X    X', 'X    X', 'X    X', ' XXXXX']),
    'n': (5, ['X XXX ', 'XX   X', 'X    X', 'X    X', 'X    X', 'X    X', 'X    X']),
    'c': (5, [' XXXX ', 'X     ', 'X     ', 'X     ', 'X     ', 'X     ', ' XXXX ']),
    'e': (5, [' XXXX ', 'X    X', 'XXXXXX', 'X     ', 'X     ', 'X    X', ' XXXX ']),
    'r': (5, ['X XXX', 'XX   ', 'X    ', 'X    ', 'X    ', 'X    ', 'X    ']),
    't': (2, [' X  ', ' X  ', ' X  ', 'XXXX', ' X  ', ' X  ', ' X  ', ' X  ', ' X  ', '  XX']),
    'd': (1, ['     X', '     X', '     X', '     X', ' XXXXX', 'X    X', 'X    X', 'X    X',
              'X    X', 'X    X', ' XXXXX']),
    'b': (1, ['X     ', 'X     ', 'X     ', 'X     ', 'XXXXX ', 'X    X', 'X    X', 'X    X',
              'X    X', 'X    X', 'XXXXX ']),
    'y': (5, ['X    X', 'X    X', 'X    X', 'X    X', 'X    X', 'X    X', ' XXXXX', '     X',
              '     X', ' XXXX ']),
}


def render(text, h=16):
    """pixel rows (values 0, 2 outline, 4 stroke) of text in the staff font"""
    width = 1
    for c in text:
        width += 4 if c == ' ' else len(STROKES[c][1][0]) + 2
    img = [[0] * (width + 1) for _ in range(h)]
    x = 1
    for c in text:
        if c == ' ':
            x += 4
            continue
        y0, rows = STROKES[c]
        for dy, row in enumerate(rows):
            for dx, ch in enumerate(row):
                if ch == 'X':
                    img[y0 + dy][x + dx] = 4
        x += len(rows[0]) + 2
    out = [r[:] for r in img]
    for y in range(h):
        for x in range(width + 1):
            if img[y][x]:
                continue
            if any(0 <= y + dy < h and 0 <= x + dx <= width and img[y + dy][x + dx] == 4
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                out[y][x] = 2
    return out


def pixels(mf, k):
    s = mf.frame_sprite(k)
    w, h = struct.unpack('>HH', s[0][4:8])
    p = []
    for b in s[1][:w * h // 2]:
        p += [b >> 4, b & 15]
    return w, h, [p[y * w:(y + 1) * w] for y in range(h)]


def trim(rows):
    """drop empty columns at both ends"""
    w = len(rows[0])
    used = [x for x in range(w) if any(r[x] for r in rows)]
    return [r[used[0]:used[-1] + 1] for r in rows]


def sprite(M, k, rows):
    """frame k's sprite replaced by the pixel rows (width padded to 8)"""
    h = len(rows)
    w = len(rows[0])
    W = (w + 2 + 7) // 8 * 8
    x0 = (W - w) // 2
    img = [[0] * x0 + r + [0] * (W - w - x0) for r in rows]
    data = bytes((img[y][x] << 4) | img[y][x + 1] for y in range(h) for x in range(0, W, 2))
    head = bytearray(M.frame_sprite(k)[0])
    head[4:12] = struct.pack('>HHI', W, h, len(data))
    return bytes(head), data


def add_line(Ed):
    """CHR_VS7.MF (arcade layout, English) with the extra credit line.

    The staff roll lines are drawn one row each, so the two helpers' lines
    become one ("with help from Katrin & Danthrax") and the freed line
    carries the new credit."""
    M = vsmerge.VSMF(Ed)
    w1, h, a = pixels(M, HELP_LINE)
    w2, h2, b = pixels(M, LAST_LINE)
    a, b = trim(a), trim(b)
    joined = [ra + [0] * 5 + rb for ra, rb in zip(a, b)]
    fs = {k: M.frame_sprite(k) for k in range(len(M.frames))}
    fs[HELP_LINE] = sprite(M, HELP_LINE, joined)
    fs[LAST_LINE] = sprite(M, LAST_LINE, trim(render(LINE, h)))
    if not hasattr(M, 'orig_sif'):
        M.orig_sif = M.sub('.SIF')
    return vsmerge.build(M, M.frames, fs, keep_unused=False)
