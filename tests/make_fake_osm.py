"""Writes a small synthetic grid as OSM XML so the pipeline can be tested offline."""
import sys
N, d = 6, 0.002
lat0, lon0 = 42.37, -72.53
o = ['<?xml version="1.0"?><osm version="0.6">']
nid = lambda i, j: 1 + i * N + j
for i in range(N):
    for j in range(N):
        tag = '<tag k="highway" v="traffic_signals"/>' if (i, j) in ((2, 2), (3, 3)) else ""
        o.append(f'<node id="{nid(i,j)}" lat="{lat0+i*d}" lon="{lon0+j*d}" version="1">{tag}</node>')
w = 1000
for i in range(N):
    for kind, nodes in (("h", [nid(i, j) for j in range(N)]), ("v", [nid(j, i) for j in range(N)])):
        w += 1
        hw = "secondary" if i in (2, 3) else "residential"
        o.append(f'<way id="{w}" version="1">' + "".join(f'<nd ref="{n}"/>' for n in nodes) +
                 f'<tag k="highway" v="{hw}"/><tag k="name" v="{kind}{i} St"/><tag k="sidewalk" v="both"/></way>')
o.append("</osm>")
open(sys.argv[1], "w").write("\n".join(o))
