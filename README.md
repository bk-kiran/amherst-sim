# Amherst Sim

Multi-agent simulation of downtown Amherst + UMass Amherst for snow, traffic and town-event scenarios.
SUMO is the ground truth for movement; AI agents get layered on top in later steps.

## Step 1: map -> network -> baseline run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt                      # installs SUMO itself, no separate install
python pipeline.py all                               # fetch, build, demand, run
python pipeline.py gui                               # watch it in sumo-gui
```

What each stage does:

| Stage | Output | Notes |
|---|---|---|
| `fetch` | `data/amherst.osm.xml` | OpenStreetMap extract for `BBOX` in `pipeline.py` |
| `build` | `data/amherst.net.xml`, `data/amherst.stops.add.xml` | Roads, sidewalks, crossings, signals, bus stops |
| `demand` | `data/cars.rou.xml`, `data/peds.rou.xml`, `data/amherst.sumocfg` | Random placeholder trips, replaced in step 2 |
| `run` | `out/tripinfo.xml`, `out/summary.xml` | Prints baseline trip time and delay |

`tests/make_fake_osm.py data/amherst.osm.xml` writes a synthetic grid if you need to test offline.

## Things to check in sumo-gui after the first build

- North Pleasant St, Massachusetts Ave, Route 9, Route 116 and University Dr are connected end to end
- Signals exist where they do in real life (netconvert guesses; fix wrong ones in `netedit`)
- Campus footpaths and crosswalks exist around Southwest, the Campus Center and Haigis Mall
- Nothing important is cut off at the bbox edge (widen `BBOX` if so)

## Roadmap

1. Network + baseline (this step)
2. Real demand: PVTA routes from GTFS, class-change pedestrian waves, commuter and lot demand
3. Scenario engine: JSON events (closure, demand spike, weather), before/after comparison
4. Game day: McGuirk scenario end to end with rule-based agents
5. LLM agents: decision-point residents, institution swarms, validators, natural-language input
6. Snow: plows, parking ban, delayed opening
7. 3D frontend + resident inspection
