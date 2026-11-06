"""Rasterises the SVG icon sources to transparent PNG exports (256/128/64) using headless Edge + ffmpeg, and writes manifest.json."""
import json, pathlib, subprocess, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "icons-3d"
SRC, EXP = ROOT / "source", ROOT / "exports"
EXP.mkdir(exist_ok=True)
names = sorted(p.stem for p in SRC.glob("*.svg"))
cols = 5
rows = -(-len(names) // cols)
cells = "".join(f"<img src='{(SRC / n).as_uri()}.svg' style='position:absolute;left:{(i % cols) * 256}px;top:{(i // cols) * 256}px' width=256 height=256>" for i, n in enumerate(names))
html = pathlib.Path(tempfile.gettempdir()) / "icons_export.html"
html.write_text(f"<html><body style='margin:0;background:transparent'>{cells}</body></html>", encoding="utf-8")
sheet = pathlib.Path(tempfile.gettempdir()) / "icons_sheet_alpha.png"
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
subprocess.run([edge, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                "--default-background-color=00000000", f"--window-size={cols * 256},{rows * 256 + 120}",
                f"--screenshot={sheet}", html.as_uri()], capture_output=True)
time.sleep(2)
manifest = []
for i, n in enumerate(names):
    x, y = (i % cols) * 256, (i // cols) * 256
    for size in (256, 128, 64):
        out = EXP / f"{n}@{size}.png"
        vf = f"crop=256:256:{x}:{y}" + (f",scale={size}:{size}:flags=lanczos" if size != 256 else "")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sheet), "-vf", vf, "-pix_fmt", "rgba", str(out)], check=True)
    manifest.append({"name": n, "version": "0.1.0", "source": f"source/{n}.svg", "sizes": [256, 128, 64],
                     "exports": [f"exports/{n}@{s}.png" for s in (256, 128, 64)],
                     "usage": "Windows nav/cards (64-128), TV (256). Static; never animate over video.",
                     "generator": "design-system/tools/gen_icons.py"})
(ROOT / "manifest.json").write_text(json.dumps({"family": "AirScreen 3D Icons (pilot)", "version": "0.1.0", "icons": manifest}, indent=2), encoding="utf-8")
print("exported", len(names), "icons")
