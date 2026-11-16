import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);
import type { Journey, ReachClass, RegionStation } from "../types";

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const BLANK: StyleSpecification = {
  version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#E4E8EC" } }],
};
const EMPTY = { type: "FeatureCollection" as const, features: [] as any[] };

type Props = {
  stations: RegionStation[];
  reach: { origin: string; classes: Record<string, ReachClass> } | null;
  journey: Journey | null;
  selected: string | null;
  onSelect: (id: string) => void;
};

function stationsGeo(stations: RegionStation[], selected: string | null, reach: Props["reach"]) {
  return {
    type: "FeatureCollection" as const,
    features: stations.map((s) => {
      // in reach mode the colour says where you can go from the origin; otherwise the station's own state
      const cls = reach ? (s.id === reach.origin ? "ORIGIN" : reach.classes[s.id] || "NOT_BOARDABLE") : s.state;
      const dim = cls === "NOT_BOARDABLE" || cls === "UNREACHABLE";
      return {
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, state: cls, dim: dim ? 1 : 0, outages: s.outages, selected: s.id === selected ? 1 : 0 },
      };
    }),
  };
}

function journeyGeo(j: Journey | null) {
  if (!j || !j.legs.length) return { lines: EMPTY, stops: EMPTY };
  const lines = j.legs.map((l) => ({
    type: "Feature" as const,
    geometry: { type: "LineString" as const, coordinates: l.path.length > 1 ? l.path : [] },
    properties: { color: `#${l.color || "14213D"}` },
  }));
  const ends = [j.from, ...j.legs.map((l) => ({ lon: l.path[l.path.length - 1]?.[0], lat: l.path[l.path.length - 1]?.[1], name: l.to_name }))];
  const stops = ends.filter((e) => e.lon != null).map((e) => ({
    type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [e.lon, e.lat] }, properties: { name: e.name },
  }));
  return { lines: { type: "FeatureCollection" as const, features: lines }, stops: { type: "FeatureCollection" as const, features: stops } };
}

export function RegionMap({ stations, reach, journey, selected, onSelect }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [blank, setBlank] = useState(false);
  const [ready, setReady] = useState(0);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({ container: box.current, style: STYLE_URL, center: [2.4, 48.83], zoom: 8.6,
      attributionControl: { compact: true }, dragRotate: false });
    map.current = m;
    m.on("error", (e: any) => {
      if (!m.getSource("rstations") && String(e.error?.message || "").length) { setBlank(true); m.setStyle(BLANK); }
    });
    const add = () => {
      if (m.getSource("rstations")) return;
      m.addSource("rstations", { type: "geojson", data: EMPTY });
      m.addSource("route", { type: "geojson", data: EMPTY });
      m.addSource("routestops", { type: "geojson", data: EMPTY });
      m.addLayer({ id: "dim", type: "circle", source: "rstations", filter: ["==", ["get", "dim"], 1],
        paint: { "circle-radius": 2, "circle-color": "#A9B3C1" } });
      m.addLayer({ id: "route-casing", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FFFFFF", "line-width": 9 } });
      m.addLayer({ id: "route", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 5 } });
      m.addLayer({ id: "rst", type: "circle", source: "rstations", filter: ["==", ["get", "dim"], 0],
        paint: {
          "circle-radius": ["match", ["get", "state"], "OPEN", 3.2, "CONFIRMED", 4.2, "ORIGIN", 9, 5.5],
          "circle-color": ["match", ["get", "state"], "OPEN", "#14213D", "DOUBT", "#C98A12", "CLOSED", "#C8102E",
            "CONFIRMED", "#1F7A4D", "IF_LIFTS_WORK", "#C98A12", "CUT", "#C8102E", "ORIGIN", "#14213D", "#14213D"],
          "circle-stroke-color": ["case", ["==", ["get", "selected"], 1], "#0F62FE", "#FFFFFF"],
          "circle-stroke-width": ["case", ["==", ["get", "selected"], 1], 3.5, 1],
        } });
      m.addLayer({ id: "routestops", type: "circle", source: "routestops",
        paint: { "circle-radius": 6, "circle-color": "#FFFFFF", "circle-stroke-color": "#14213D", "circle-stroke-width": 2.5 } });
      for (const id of ["rst", "dim"]) {
        m.on("click", id, (e: any) => { const sid = e.features?.[0]?.properties?.id; if (sid) onSelectRef.current(sid); });
        m.on("mouseenter", id, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", id, () => (m.getCanvas().style.cursor = ""));
      }
      setReady((r) => r + 1);
    };
    m.on("load", add);
    m.on("style.load", add);
    return () => m.remove();
  }, []);

  useEffect(() => {
    (map.current?.getSource("rstations") as GeoJSONSource | undefined)?.setData(stationsGeo(stations, selected, reach));
  }, [stations, selected, reach, ready]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const g = journeyGeo(journey);
    (m.getSource("route") as GeoJSONSource | undefined)?.setData(g.lines);
    (m.getSource("routestops") as GeoJSONSource | undefined)?.setData(g.stops);
    const pts = journey?.legs.flatMap((l) => l.path) || [];
    if (pts.length > 1) {
      const b = pts.reduce((bb, p) => bb.extend(p as [number, number]), new maplibregl.LngLatBounds(pts[0] as [number, number], pts[0] as [number, number]));
      m.fitBounds(b, { padding: 70, duration: 700, maxZoom: 12.5 });
    }
  }, [journey, ready]);

  useEffect(() => {
    const s = stations.find((x) => x.id === selected);
    if (s && map.current && !journey) map.current.easeTo({ center: [s.lon, s.lat], zoom: Math.max(map.current.getZoom(), 9.4), duration: 600 });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="map-wrap region-map">
      <div ref={box} className="map" role="region" aria-label="Map of the Île-de-France rail, metro and tram stations, coloured by step-free state. Use the journey form and lists for keyboard access." />
      {blank && <p className="map-note">Basemap tiles unavailable — stations are still plotted.</p>}
    </div>
  );
}
