import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import io, index
from index import *
from PIL import Image
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
for r in ["kanto","johto","hoenn","sinnoh","unova","kalos","alola","galar","paldea"]:
    b=scene_slide(r,2).body; im=Image.open(io.BytesIO(b)); im.verify()
ok(True,"9 region slides render as valid PNGs")
ok(len({scene_slide(r,2).body for r in ["kanto","johto","hoenn","sinnoh","unova"]})==5,"each region looks different")
for k in ["region","route","town","care","lab"]:
    g=scene_gif(k,"kanto","ember",2).body; im=Image.open(io.BytesIO(g)); ok(im.n_frames==12 and im.size==(320,180),f"{k}.gif: 12 frames, 320x180")
    scene_png(k,"johto","frost",2)
frames=[]; im=Image.open(io.BytesIO(scene_gif("route","kanto","ember",2).body))
for i in range(im.n_frames): im.seek(i); frames.append(im.convert("RGB").tobytes())
ok(len(set(frames))>=10,"route GIF actually animates (the trainer walks)")
try: scene_png("nope"); ok(False,"")
except HTTPException as e: ok(e.status_code==404,"unknown scene 404")
ok(scene_png("route","atlantis","bogus").media_type=="image/png","bad region/avatar fall back instead of erroring")
print("ALL SCENE TESTS PASSED")
