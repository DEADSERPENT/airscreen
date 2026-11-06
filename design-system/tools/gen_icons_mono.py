"""Monochrome variant of the AirScreen 3D icon family (graphite bodies, silver/white emissive accents).

Re-uses gen_icons.py's geometry; only the palette and output folder change.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
src = (HERE / "gen_icons.py").read_text(encoding="utf-8")

# 1) palette
a = src.index("DEFS = \"\"\"")
b = src.index("\"\"\"", a + 10) + 3
MONO_DEFS = '''DEFS = """
<defs>
  <linearGradient id="graphite" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5E5E65"/><stop offset=".55" stop-color="#2C2C31"/><stop offset="1" stop-color="#121215"/></linearGradient>
  <linearGradient id="indigo" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#A3A3AB"/><stop offset=".55" stop-color="#58585F"/><stop offset="1" stop-color="#26262B"/></linearGradient>
  <linearGradient id="violet" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".5" stop-color="#E2E2E7"/><stop offset="1" stop-color="#9F9FA8"/></linearGradient>
  <linearGradient id="cyan" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".5" stop-color="#F1F1F4"/><stop offset="1" stop-color="#B6B6BF"/></linearGradient>
  <linearGradient id="emerald" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#BDBDC5"/></linearGradient>
  <linearGradient id="amber" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F4F4F6"/><stop offset="1" stop-color="#9A9AA3"/></linearGradient>
  <linearGradient id="coral" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#BDBDC5"/></linearGradient>
  <linearGradient id="screen" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#707078"/><stop offset=".6" stop-color="#303036"/><stop offset="1" stop-color="#0E0E11"/></linearGradient>
  <radialGradient id="orbV" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".35" stop-color="#D2D2D8"/><stop offset="1" stop-color="#5C5C64"/></radialGradient>
  <radialGradient id="orbC" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".38" stop-color="#E8E8EC"/><stop offset="1" stop-color="#868690"/></radialGradient>
  <radialGradient id="orbG" cx=".32" cy=".28" r=".85"><stop offset="0" stop-color="#92929A"/><stop offset=".4" stop-color="#3C3C42"/><stop offset="1" stop-color="#0C0C0E"/></radialGradient>
  <linearGradient id="rim" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset=".45" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <linearGradient id="shade" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".35"/></linearGradient>
  <filter id="contact" x="-30%" y="-30%" width="160%" height="170%"><feGaussianBlur stdDeviation="7"/></filter>
  <filter id="soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation=".6"/></filter>
</defs>"""'''
src = src[:a] + MONO_DEFS + src[b:]

# 2) neutral extrusion / accent literals
for old, new in {"#0C1024": "#0A0A0C", "#1B2142": "#17171A", "#02030A": "#000000", "#1A1260": "#17171A", "#2A1670": "#222226",
                 "#7A4A06": "#3A3A40", "#4A2D05": "#1C1C20", "#22D3EE": "#FFFFFF", "#0B1120": "#0C0C0E"}.items():
    src = src.replace(old, new)

# 3) output folder
src = src.replace('OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "icons-3d" / "source"',
                  'OUT = pathlib.Path(r"E:\\airscreen\\design-system\\assets\\icons-3d-mono\\source")')
exec(compile(src, "gen_icons_mono(generated)", "exec"))
