"""Generates the Cast-screen art: hero scene (laptop -> signal -> TV), Start glyph, Streaming nav icon.
Run from the repo root:  python design-system/tools/gen_ui_art.py
Uses the existing 3D device icons so the style stays consistent; shading is drawn here (supersampled)."""
import math
import os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WEB = os.path.join(ROOT, "sender", "airscreen_sender", "webui")
ICONS = os.path.join(WEB, "icons")
SS = 2  # supersample


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def metal(size, top=(250, 250, 253), mid=(178, 180, 190), bot=(70, 72, 82)):
    """Vertical chrome gradient with a bright band near the top (1-px column stretched: fast)."""
    w, h = size
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = lerp(top, mid, t / 0.45) if t < 0.45 else lerp(mid, bot, (t - 0.45) / 0.55)
    return col.resize((w, h))


def erode(mask, px):
    """Round erosion (a square MinFilter leaves notches on rounded corners)."""
    return mask.filter(ImageFilter.GaussianBlur(px * 0.55)).point(lambda v: 255 if v >= 253 else 0)


def shaded(mask, rim=True):
    """Chrome-fill a mask, add an inner highlight, a dark rim and a soft drop shadow. Returns RGBA."""
    orig = mask.size
    pad = max(8, orig[0] // 12)                     # work on a padded canvas so edge filters see real background
    padded = Image.new("L", (orig[0] + 2 * pad, orig[1] + 2 * pad), 0)
    padded.paste(mask, (pad, pad))
    mask = padded
    size = mask.size
    body = metal((orig[0], orig[1])).convert("RGBA")
    pb = Image.new("RGBA", size, (0, 0, 0, 0)); pb.paste(body, (pad, pad)); body = pb
    body.putalpha(mask)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    sh = Image.new("RGBA", size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 150), (0, int(size[1] * 0.025)), mask)
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(size[0] * 0.02)))
    out.alpha_composite(body)
    if rim:
        edge = ImageChops.subtract(mask, erode(mask, max(2, size[0] // 90)))
        dark = Image.new("RGBA", size, (30, 30, 36, 200))
        dark.putalpha(edge)
        out.alpha_composite(dark)
        hi = erode(mask, max(2, size[0] // 60))
        hi = ImageChops.subtract(hi, erode(hi, max(2, size[0] // 120)))
        glint = Image.new("RGBA", size, (255, 255, 255, 120))
        glint.putalpha(hi.point(lambda v: v // 2))
        out.alpha_composite(glint)
    return out.crop((pad, pad, pad + orig[0], pad + orig[1]))


def rounded_polygon(size, pts, radius):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    d.polygon(pts, fill=255)
    m = m.filter(ImageFilter.MaxFilter(radius * 2 + 1)).filter(ImageFilter.MinFilter(radius * 2 + 1))
    return m.filter(ImageFilter.GaussianBlur(radius / 3)).point(lambda v: 255 if v > 127 else 0)


def play_glyph(n=256):
    s = n * SS
    pts = [(s * .30, s * .20), (s * .30, s * .80), (s * .80, s * .50)]
    img = shaded(rounded_polygon((s, s), pts, int(s * .06)))
    return img.resize((n, n), Image.LANCZOS)


def stream_icon(n=256):
    s = n * SS
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    heights = [.34, .62, .86, .56, .30]
    bw, gap = s * .11, s * .055
    x0 = (s - (5 * bw + 4 * gap)) / 2
    for i, h in enumerate(heights):
        x = x0 + i * (bw + gap)
        d.rounded_rectangle((x, s * .5 - s * h / 2, x + bw, s * .5 + s * h / 2), radius=bw / 2, fill=255)
    return shaded(m).resize((n, n), Image.LANCZOS)


def arcs(size, cx, cy, radii, width, start=-38, end=38):
    s = size
    m = Image.new("L", s, 0)
    d = ImageDraw.Draw(m)
    for r in radii:
        d.arc((cx - r, cy - r, cx + r, cy + r), start, end, fill=255, width=width)
    # round the arc ends
    return m.filter(ImageFilter.GaussianBlur(width * .12)).point(lambda v: 255 if v > 110 else 0)


def chrome(w, h, draw_fn, rim=True):
    """Chrome-shade whatever draw_fn paints (white on black mask) on its own tight canvas, so the gradient spans the shape."""
    m = Image.new("L", (w * SS, h * SS), 0)
    draw_fn(ImageDraw.Draw(m), w * SS, h * SS)
    return shaded(m, rim).resize((w, h), Image.LANCZOS)


def hero():
    W, H = 1400, 820
    scene = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((260, 640, W - 260, 790), fill=(255, 255, 255, 46))
    scene.alpha_composite(glow.filter(ImageFilter.GaussianBlur(46)))

    mw, mh = 760, 470
    mx, my = 300, 120
    # --- stand
    neck = chrome(120, 120, lambda d, w, h: d.rounded_rectangle((w * .18, 0, w * .82, h), radius=w * .06, fill=255))
    base = chrome(420, 60, lambda d, w, h: d.rounded_rectangle((0, h * .15, w, h * .85), radius=h * .4, fill=255))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((mx + 40, 712, mx + mw - 40, 760), fill=(0, 0, 0, 190))
    scene.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    scene.alpha_composite(neck, (mx + mw // 2 - 60, my + mh - 24))
    scene.alpha_composite(base, (mx + mw // 2 - 210, my + mh + 78))
    # --- monitor bezel
    bezel = chrome(mw, mh, lambda d, w, h: d.rounded_rectangle((0, 0, w, h), radius=w * .045, fill=255))
    scene.alpha_composite(bezel, (mx, my))
    # --- screen: dark glass with a mirrored-desktop wireframe and a soft sweep
    pad = 26
    sw, sh_ = mw - pad * 2, mh - pad * 2
    scr = Image.new("RGBA", (sw * 2, sh_ * 2), (0, 0, 0, 0))
    col = Image.new("RGB", (1, sh_ * 2))
    cp = col.load()
    for y in range(sh_ * 2):
        cp[0, y] = lerp((16, 17, 22), (46, 48, 58), y / (sh_ * 2))
    gd = col.resize((sw * 2, sh_ * 2))
    scr = gd.convert("RGBA")
    ui = Image.new("RGBA", scr.size, (0, 0, 0, 0))           # wireframe drawn on its own layer so translucent fills blend
    d = ImageDraw.Draw(ui)
    S2 = 2
    def rr(x0, y0, x1, y1, r, fill, outline=None):
        d.rounded_rectangle((x0 * S2, y0 * S2, x1 * S2, y1 * S2), radius=r * S2, fill=fill, outline=outline, width=2 * S2 // 2)
    rr(34, 30, sw - 34, 64, 12, (255, 255, 255, 34))                       # title bar
    for i in range(3):
        d.ellipse(((52 + i * 26) * S2, 41 * S2, (66 + i * 26) * S2, 55 * S2), fill=(235, 235, 240, 190))
    rr(34, 84, 250, sh_ - 34, 14, (255, 255, 255, 26))                      # side panel
    rr(270, 84, sw - 34, 230, 14, (255, 255, 255, 40))                      # main window
    rr(270, 250, sw // 2 + 120, sh_ - 34, 14, (255, 255, 255, 26))
    rr(sw // 2 + 140, 250, sw - 34, sh_ - 34, 14, (255, 255, 255, 34))
    scr.alpha_composite(ui)
    sweep = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    ImageDraw.Draw(sweep).polygon([(sw * 2 * .55, 0), (sw * 2, 0), (sw * 2, sh_ * 2 * .55), (sw * 2 * .25, sh_ * 2)], fill=(255, 255, 255, 22))
    scr.alpha_composite(sweep)
    scr = scr.resize((sw, sh_), Image.LANCZOS)
    mask = Image.new("L", (sw * SS, sh_ * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw * SS, sh_ * SS), radius=int(sw * SS * .03), fill=255)
    scr.putalpha(mask.resize((sw, sh_), Image.LANCZOS))
    scene.alpha_composite(scr, (mx + pad, my + pad))
    # --- chrome signal arcs from the top-right corner of the monitor
    for i in range(3):
        r = 90 + i * 62
        wd = 30 - i * 3
        side = (r + wd) * 2
        def arc(dr, w, h, r=r, wd=wd):
            cx, cy = w * .5, h * .5
            rr_ = r * SS
            dr.arc((cx - rr_, cy - rr_, cx + rr_, cy + rr_), -62, 8, fill=255, width=wd * SS)
        piece = chrome(side, side, arc)
        scene.alpha_composite(piece, (mx + mw - 90 + 0 - side // 2 + 70, my + 50 - side // 2 + 70))
    return scene


def main():
    for n in (64, 128, 256):
        stream_icon(256).resize((n, n), Image.LANCZOS).save(os.path.join(ICONS, f"icon-nav-streaming@{n}.png"))
    play_glyph(256).save(os.path.join(WEB, "start-play.png"))
    img = hero()
    # crop to the visible art and centre the MONITOR (the signal arcs hang off one side, so pad the other side equally)
    bbox = img.split()[3].point(lambda v: 255 if v > 10 else 0).getbbox()
    cx = 300 + 760 // 2                                   # monitor centre inside the scene (mx + mw/2)
    left, top, right, bottom = bbox
    half = max(cx - left, right - cx)
    img = img.crop((cx - half, top, cx + half, bottom))
    img.save(os.path.join(WEB, "hero-scene.png"))
    print("hero size", img.size)
    print("ok")


if __name__ == "__main__":
    main()
