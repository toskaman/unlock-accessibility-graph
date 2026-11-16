# Risk register

| Risk | Likelihood | Impact | Mitigation / status |
|---|---|---|---|
| Judges read "blocked" as proven inaccessibility | M | H | Methodology + UI copy say "no modeled step-free route"; evidence panel lists unknowns |
| Text-derived lift edges are wrong for some stations | M | M | Every edge labelled; unmatched tokens never linked (60 logged); spot-check top stations before video |
| Relate 1.0.x API change before judging | L | H | Pinned `relate-db==1.0.2`; integration tests catch breakage |
| Windows install untested | M | H | Windows wheel exists; **test on the entrant's Windows 10 before submission** |
| Basemap tiles unavailable during judging | L | L | Blank-style fallback; stations still plotted |
| ODbL / Licence Mobilités compliance of redistributed derived data | L | M | `data/LICENSE-DATA.md`; raw files not redistributed; entrant to confirm GTFS terms |
| Live status changes make demo numbers differ from video | H | L | Demo uses committed snapshot; `fetch` documented as optional refresh |
| Only SNCF stations (no RATP) limits usefulness | H | M | Documented; IDFM key path planned |
| Single-writer lease blocks re-import while server runs | M | L | Documented; startup failure releases the lease |
| Large stations' cross-sections become wide | M | L | Horizontal scroll, min-width scaling |
