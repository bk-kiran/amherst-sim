"""Amherst sim - step 1: map -> SUMO network -> baseline demand -> measured run.

Usage:
    python pipeline.py all          # fetch + build + demand + run
    python pipeline.py fetch        # download OpenStreetMap extract
    python pipeline.py build        # OSM -> SUMO network (roads, sidewalks, crossings, signals, bus stops)
    python pipeline.py demand       # placeholder random car + pedestrian trips
    python pipeline.py run          # headless run, prints baseline metrics
    python pipeline.py gui          # open the scenario in sumo-gui
"""
import argparse, os, subprocess, sys, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path

import sumo  # pip install eclipse-sumo

SUMO_HOME = sumo.SUMO_HOME
os.environ["SUMO_HOME"] = SUMO_HOME
BIN = Path(SUMO_HOME) / "bin"
TOOLS = Path(SUMO_HOME) / "tools"
TYPEMAP = Path(SUMO_HOME) / "data" / "typemap"

ROOT = Path(__file__).parent
DATA, OUT = ROOT / "data", ROOT / "out"

# Study area: UMass campus (incl. McGuirk, Mullins, Southwest) + downtown Amherst + Route 9 / University Dr.
# (west, south, east, north) - widen here if trips get cut off at the edges.
BBOX = (-72.545, 42.362, -72.505, 42.402)

OSM = DATA / "amherst.osm.xml"
NET = DATA / "amherst.net.xml"
STOPS = DATA / "amherst.stops.add.xml"
CAR_TRIPS, CAR_ROUTES = DATA / "cars.trips.xml", DATA / "cars.rou.xml"
PED_ROUTES = DATA / "peds.rou.xml"
CFG = DATA / "amherst.sumocfg"

SIM_END = 3600          # seconds simulated
CAR_PERIOD = 1.5        # one new car every N seconds  (~2400 veh/h, placeholder)
PED_PERIOD = 2.0        # one new pedestrian every N seconds


def sh(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=DATA)  # stray tool outputs land in data/


def exe(name):
    p = BIN / (name + (".exe" if os.name == "nt" else ""))
    return p if p.exists() else name


def fetch():
    DATA.mkdir(exist_ok=True)
    w, s, e, n = BBOX
    mirrors = ["https://overpass-api.de/api/map", "https://overpass.kumi.systems/api/map"]
    for base in mirrors:
        url = f"{base}?bbox={w},{s},{e},{n}"
        print("  GET", url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "amherst-sim/0.1 (student project)"})
            with urllib.request.urlopen(req, timeout=180) as r:
                OSM.write_bytes(r.read())
            print(f"  saved {OSM} ({OSM.stat().st_size/1e6:.1f} MB)")
            return
        except Exception as ex:
            print("  failed:", ex)
    sys.exit("Could not download OSM data. Export the bbox manually from openstreetmap.org "
             f"(Export tab) and save it as {OSM}")


def build():
    if not OSM.exists():
        sys.exit(f"{OSM} missing - run `python pipeline.py fetch` first")
    typemaps = ",".join(str(TYPEMAP / f) for f in
                        ["osmNetconvert.typ.xml", "osmNetconvertPedestrians.typ.xml"])
    sh([exe("netconvert"),
        "--osm-files", OSM, "--type-files", typemaps, "-o", NET,
        "--geometry.remove", "--roundabouts.guess", "--ramps.guess",
        "--junctions.join", "--junctions.corner-detail", "5",
        "--tls.guess-signals", "--tls.discard-simple", "--tls.join", "--tls.default-type", "actuated",
        "--sidewalks.guess", "--crossings.guess", "--osm.sidewalks",
        "--remove-edges.isolated", "--keep-edges.by-vclass", "passenger,bus,pedestrian,bicycle",
        "--output.street-names", "--output.original-names",
        "--ptstop-output", STOPS,          # bus stops, used when PVTA routes are added
        "--no-warnings"])
    stats()


def stats():
    edges = junctions = tls = crossings = 0
    for _, el in ET.iterparse(NET):
        if el.tag == "edge":
            f = el.get("function")
            if f == "crossing": crossings += 1
            elif f is None: edges += 1
        elif el.tag == "junction" and el.get("type") != "internal": junctions += 1
        elif el.tag == "tlLogic": tls += 1
        if el.tag in ("edge", "junction", "tlLogic"): el.clear()
    stops = len(ET.parse(STOPS).getroot()) if STOPS.exists() else 0
    print(f"  network: {edges} edges, {junctions} junctions, {tls} signals, "
          f"{crossings} crossings, {stops} bus stops")


def demand():
    rt = TOOLS / "randomTrips.py"
    sh([sys.executable, rt, "-n", NET, "-o", CAR_TRIPS, "-r", CAR_ROUTES,
        "-e", SIM_END, "-p", CAR_PERIOD, "--fringe-factor", "5", "--validate",
        "--vehicle-class", "passenger", "--prefix", "car", "--seed", "42"])
    sh([sys.executable, rt, "-n", NET, "-o", PED_ROUTES, "--pedestrians",
        "-e", SIM_END, "-p", PED_PERIOD, "--max-distance", "2000",
        "--prefix", "ped", "--seed", "43"])
    add = f'<additional-files value="{STOPS.name}"/>' if STOPS.exists() else ""
    CFG.write_text(f"""<configuration>
  <input>
    <net-file value="{NET.name}"/>
    <route-files value="{CAR_ROUTES.name},{PED_ROUTES.name}"/>
    {add}
  </input>
  <time><begin value="0"/><end value="{SIM_END}"/></time>
  <processing><ignore-route-errors value="true"/></processing>
</configuration>
""")
    print(f"  wrote {CFG}")


def run():
    OUT.mkdir(exist_ok=True)
    trip, summ = OUT / "tripinfo.xml", OUT / "summary.xml"
    sh([exe("sumo"), "-c", CFG, "--tripinfo-output", trip, "--summary-output", summ,
        "--no-step-log", "--duration-log.statistics", "--no-warnings"])
    report(trip)


def report(trip):
    cars, peds = [], []
    for el in ET.parse(trip).getroot():
        if el.tag == "tripinfo":
            cars.append((float(el.get("duration")), float(el.get("timeLoss")), float(el.get("routeLength"))))
        elif el.tag == "personinfo":
            peds += [float(w.get("duration")) for w in el.iter("walk")]
    print("\n=== Baseline (placeholder demand) ===")
    if cars:
        n = len(cars)
        dur, loss, dist = (sum(c[i] for c in cars) / n for i in range(3))
        print(f"cars finished      : {n}")
        print(f"avg trip time      : {dur/60:.1f} min over {dist/1000:.2f} km")
        print(f"avg delay per trip : {loss:.0f} s ({100*loss/dur:.0f}% of trip time)")
    if peds:
        print(f"walks finished     : {len(peds)}, avg {sum(peds)/len(peds)/60:.1f} min")


def gui():
    sh([exe("sumo-gui"), "-c", CFG])


if __name__ == "__main__":
    steps = {"fetch": fetch, "build": build, "demand": demand, "run": run, "gui": gui}
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=[*steps, "all"])
    a = ap.parse_args()
    for name in (["fetch", "build", "demand", "run"] if a.step == "all" else [a.step]):
        print(f"[{name}]")
        steps[name]()
