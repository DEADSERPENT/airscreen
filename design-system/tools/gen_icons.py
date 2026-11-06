"""Generates the AirScreen pilot 3D icon family as SVG sources (design-system/assets/icons-3d/source).

One construction language for every icon (spec 3.2-3.5):
  - soft extrusion (two darker offset layers) for physical depth
  - one key light from the upper-left: face gradient light->dark along that axis, rim highlight on the lit edges
  - graphite/indigo bodies; violet/cyan emissive accent; semantic accent only as a small detail
  - soft contact shadow underneath; transparent background; no text inside artwork
"""
import math
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "icons-3d" / "source"
OUT.mkdir(parents=True, exist_ok=True)

DEFS = """
<defs>
  <linearGradient id="graphite" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4A5478"/><stop offset=".55" stop-color="#262D4B"/><stop offset="1" stop-color="#151A33"/></linearGradient>
  <linearGradient id="indigo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7A66F2"/><stop offset=".55" stop-color="#4B3BC4"/><stop offset="1" stop-color="#2B2087"/></linearGradient>
  <linearGradient id="violet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B49CFF"/><stop offset=".5" stop-color="#8057FF"/><stop offset="1" stop-color="#5B34D8"/></linearGradient>
  <linearGradient id="cyan" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8BEBFF"/><stop offset=".5" stop-color="#22D3EE"/><stop offset="1" stop-color="#2A8FD6"/></linearGradient>
  <linearGradient id="emerald" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8DF2C9"/><stop offset="1" stop-color="#1FA774"/></linearGradient>
  <linearGradient id="amber" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE08A"/><stop offset="1" stop-color="#E29B13"/></linearGradient>
  <linearGradient id="coral" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFA3A3"/><stop offset="1" stop-color="#E0505A"/></linearGradient>
  <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6A5BFF"/><stop offset=".6" stop-color="#3B2FB8"/><stop offset="1" stop-color="#1B1A5E"/></linearGradient>
  <radialGradient id="orbV" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#D9CCFF"/><stop offset=".35" stop-color="#8057FF"/><stop offset="1" stop-color="#2E1B8F"/></radialGradient>
  <radialGradient id="orbC" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#CFF8FF"/><stop offset=".38" stop-color="#22D3EE"/><stop offset="1" stop-color="#14508F"/></radialGradient>
  <radialGradient id="orbG" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#6A7399"/><stop offset=".4" stop-color="#2C3556"/><stop offset="1" stop-color="#0F1328"/></radialGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset=".45" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>
  <filter id="contact" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur stdDeviation="7"/></filter>
  <filter id="soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation=".6"/></filter>
</defs>"""


def svg(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">{DEFS}{body}</svg>'


def contact(cx=128, cy=222, rx=78, ry=11, o=.42):
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#02030A" opacity="{o}" filter="url(#contact)"/>'


def solid(shape: str, grad="graphite", depth=9, side="#0C1024"):
    """shape contains {A} where attributes go. Draws extrusion, face, shade and rim light."""
    layers = []
    for k, col in ((1.0, side), (.55, "#1B2142")):
        layers.append(shape.replace("{A}", f'fill="{col}" transform="translate({depth * k * .55:.1f} {depth * k:.1f})"'))
    layers.append(shape.replace("{A}", f'fill="url(#{grad})"'))
    layers.append(shape.replace("{A}", 'fill="url(#shade)"'))
    layers.append(shape.replace("{A}", 'fill="none" stroke="url(#rim)" stroke-width="3"'))
    return "".join(layers)


def tube(d: str, grad="violet", w=18, depth=7):
    """Rounded emissive tube (strokes)."""
    base = f'<path d="{d}" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    return (base + f' stroke="#0C1024" stroke-width="{w}" transform="translate({depth * .5:.1f} {depth})"/>'
            + base + f' stroke="url(#{grad})" stroke-width="{w}"/>'
            + base + f' stroke="#fff" stroke-opacity=".55" stroke-width="{w * .22:.1f}" transform="translate(-{w * .18:.1f} -{w * .22:.1f})" filter="url(#soft)"/>')


def dot(cx, cy, r, grad="violet", depth=6):
    return (f'<circle cx="{cx + depth * .5}" cy="{cy + depth}" r="{r}" fill="#0C1024"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{grad})"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#rim)" stroke-width="2"/>'
            f'<ellipse cx="{cx - r * .3}" cy="{cy - r * .35}" rx="{r * .35}" ry="{r * .22}" fill="#fff" opacity=".6"/>')


def orb(cx, cy, r, g="orbV", depth=7):
    """Glossy sphere: radial light from the upper-left, soft contact shadow, specular kiss."""
    hx, hy = cx - r * .34, cy - r * .4
    return (f'<ellipse cx="{cx + depth * .4:.1f}" cy="{cy + r * .92 + depth * .4:.1f}" rx="{r * .8:.1f}" ry="{r * .16:.1f}" fill="#02030A" opacity=".4" filter="url(#contact)"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{g})"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#rim)" stroke-width="2.5"/>'
            f'<ellipse cx="{hx:.1f}" cy="{hy:.1f}" rx="{r * .3:.1f}" ry="{r * .18:.1f}" fill="#fff" opacity=".65" transform="rotate(-30 {hx:.1f} {hy:.1f})"/>')


def ring(cx, cy, r, w=16, g="violet", depth=6):
    """Torus: thick gradient stroke with lit upper-left edge."""
    base = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none"'
    return (base + f' stroke="#0C1024" stroke-width="{w}" transform="translate({depth * .5} {depth})"/>' + base + f' stroke="url(#{g})" stroke-width="{w}"/>'
            + base + f' stroke="url(#rim)" stroke-width="{w}" opacity=".55"/>')


def rect(x, y, w, h, r):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" {{A}}/>'


def path(d):
    return f'<path d="{d}" stroke-linejoin="round" {{A}}/>'


def screen_block(x, y, w, h, r=18, grad="screen"):
    """A display: graphite bezel + emissive screen face."""
    return (solid(rect(x, y, w, h, r)) +
            f'<rect x="{x + 9}" y="{y + 9}" width="{w - 18}" height="{h - 18}" rx="{r - 8}" fill="url(#{grad})"/>'
            f'<path d="M{x + 9} {y + h * .55} C {x + w * .3} {y + h * .35}, {x + w * .5} {y + h * .8}, {x + w - 9} {y + h * .5} V{y + h - 9 - (r - 8) * .3} H{x + 9}Z" fill="#22D3EE" opacity=".22"/>'
            f'<rect x="{x + 9}" y="{y + 9}" width="{w - 18}" height="{h - 18}" rx="{r - 8}" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>')


def gear(cx, cy, r_out, r_in, teeth=8):
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        for da, rr in ((-.20, r_in), (-.11, r_out), (.11, r_out), (.20, r_in)):
            a = a0 + da * (2 * math.pi / teeth) * 1.6
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"


ICONS = {}
sl = lambda x, y, w, h, r, g="graphite", d=9: solid(rect(x, y, w, h, r), g, d)
SCR = '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#screen)"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="none" stroke="#fff" stroke-opacity=".22" stroke-width="2"/>'

# --- navigation (abstract forms) ----------------------------------------------------------
ICONS["icon-nav-cast"] = svg(contact() + sl(34, 40, 188, 128, 34, "indigo", 11) + sl(60, 62, 136, 84, 22, "graphite", 5)
                             + ring(70, 196, 22, 14, "cyan", 4) + ring(70, 196, 44, 14, "violet", 4) + orb(70, 196, 11, "orbC", 4))
ICONS["icon-nav-devices"] = svg(contact() + sl(24, 56, 148, 112, 30, "graphite", 10) + sl(112, 96, 120, 112, 30, "indigo", 10) + orb(172, 152, 22, "orbC", 5))
ICONS["icon-nav-streaming"] = svg(contact() + tube("M30 196 C 80 196, 82 70, 128 70 S 176 196, 226 196", "violet", 26, 9) + orb(128, 70, 34, "orbC", 8))
ICONS["icon-nav-settings"] = svg(contact() + sl(26, 62, 204, 34, 17, "graphite", 7) + sl(26, 150, 204, 34, 17, "graphite", 7) + orb(88, 79, 30, "orbV", 7) + orb(170, 167, 30, "orbC", 7))
ICONS["icon-nav-logs"] = svg(contact() + sl(70, 24, 140, 150, 30, "graphite", 8) + sl(46, 54, 140, 150, 30, "indigo", 9) +
                             "".join(f'<rect x="76" y="{y}" width="{w}" height="12" rx="6" fill="url(#{g})"/>' for y, w, g in ((92, 82, "cyan"), (122, 62, "violet"), (152, 72, "cyan"))))
ICONS["icon-nav-about"] = svg(contact() + ring(128, 116, 74, 26, "graphite", 9) + orb(128, 116, 40, "orbV", 8) + orb(128, 116, 12, "orbC", 2))

# --- devices & connection ------------------------------------------------------------------
ICONS["icon-device-tv"] = svg(contact() + sl(26, 38, 204, 136, 40, "graphite", 11) + SCR.format(x=40, y=52, w=176, h=108, r=30) +
                              '<path d="M40 128 C 90 96, 120 150, 216 108 V130 A30 30 0 0 1 186 160 H70 A30 30 0 0 1 40 130Z" fill="#22D3EE" opacity=".3"/>' + orb(128, 204, 14, "orbG", 4))
ICONS["icon-device-desktop"] = svg(contact() + sl(30, 34, 196, 128, 38, "graphite", 11) + SCR.format(x=44, y=48, w=168, h=100, r=28) + sl(88, 184, 80, 20, 10, "graphite", 5) + orb(128, 170, 12, "orbG", 3))
ICONS["icon-device-laptop"] = svg(contact() + sl(48, 40, 160, 114, 32, "graphite", 10) + SCR.format(x=60, y=52, w=136, h=90, r=22) + sl(22, 168, 212, 30, 15, "indigo", 7))
ICONS["icon-network-wifi"] = svg(contact() + tube("M44 120 A120 120 0 0 1 212 120", "violet", 22, 8) + tube("M72 148 A80 80 0 0 1 184 148", "cyan", 22, 8) + tube("M100 176 A40 40 0 0 1 156 176", "violet", 22, 8) + orb(128, 206, 17, "orbC", 5))
ICONS["icon-security-shield"] = svg(contact() + solid(path("M128 22 C 162 40, 196 44, 212 48 V120 C 212 170, 176 202, 128 226 C 80 202, 44 170, 44 120 V48 C 60 44, 94 40, 128 22 Z"), "indigo", 11, "#1A1260") +
                                    ring(128, 120, 34, 16, "emerald", 4) + orb(128, 120, 10, "orbC", 2))

# --- media ---------------------------------------------------------------------------------
ICONS["icon-audio-volume"] = svg(contact() + orb(76, 130, 42, "orbG", 8) + tube("M130 86 A56 56 0 0 1 130 174", "cyan", 16, 5) + tube("M160 56 A96 96 0 0 1 160 204", "violet", 16, 5))
ICONS["icon-audio-mute"] = svg(contact() + orb(76, 130, 42, "orbG", 8) + tube("M138 98 L206 162", "coral", 18, 6) + tube("M206 98 L138 162", "coral", 18, 6))
ICONS["icon-action-refresh"] = svg(contact() + ring(128, 120, 70, 24, "cyan", 8) + orb(188, 64, 20, "orbV", 6) + orb(128, 120, 16, "orbG", 3))
ICONS["icon-status-warning"] = svg(contact() + solid(path("M128 36 Q140 36 146 46 L222 180 Q230 198 210 198 H46 Q26 198 34 180 L110 46 Q116 36 128 36 Z"), "amber", 11, "#7A4A06") +
                                   '<rect x="118" y="86" width="20" height="62" rx="10" fill="#4A2D05"/><circle cx="128" cy="170" r="11" fill="#4A2D05"/>')

# --- animated state variant (SVG-internal CSS; used only while connecting/scanning) -----------
wifi = ICONS["icon-network-wifi"]
A1 = tube("M100 176 A40 40 0 0 1 156 176", "violet", 22, 8)
A2 = tube("M72 148 A80 80 0 0 1 184 148", "cyan", 22, 8)
A3 = tube("M44 120 A120 120 0 0 1 212 120", "violet", 22, 8)
anim_css = ("<style>@media (prefers-reduced-motion:no-preference){.a1,.a2,.a3{animation:lit 1.2s ease-in-out infinite}"
            ".a2{animation-delay:.2s}.a3{animation-delay:.4s}@keyframes lit{0%,100%{opacity:.35}45%{opacity:1}}}</style>")
body = (wifi.replace(A1, '<g class="a1">' + A1 + '</g>').replace(A2, '<g class="a2">' + A2 + '</g>')
            .replace(A3, '<g class="a3">' + A3 + '</g>').replace("</defs>", "</defs>" + anim_css, 1))
ANIMATED = {"icon-network-wifi-connecting": body}

for name, body in ICONS.items():
    (OUT / f"{name}.svg").write_text(body, encoding="utf-8")
ANIM = OUT.parent / "animated"
ANIM.mkdir(exist_ok=True)
for name, body in ANIMATED.items():
    (ANIM / f"{name}.svg").write_text(body, encoding="utf-8")
print("wrote", len(ICONS), "icons +", len(ANIMATED), "animated variant(s) to", OUT.parent)
