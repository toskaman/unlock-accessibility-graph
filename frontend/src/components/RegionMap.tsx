import { useEffect, useRef, useState } from "react";
import { tr } from "../i18n";
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

const cssVar = (n: string, fb: string) => (typeof document === "undefined" ? fb : getComputedStyle(document.documentElement).getPropertyValue(n).trim() || fb);
const dark = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
const reduced = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Station marks drawn once per theme: shape carries the state (dot / ring / cross), colour only repeats it. */
function drawIcons(m: maplibregl.Map) {
  const halo = cssVar("--panel", "#ffffff");
  const c = { ink: cssVar("--ink", "#14213d"), ok: cssVar("--ok", "#0b6e4c"), doubt: cssVar("--doubt-mark", "#c98a12"), ko: cssVar("--ko", "#b00d27") };
  const R = 2;  // pixel ratio
  const make = (size: number, paint: (g: CanvasRenderingContext2D, h: number) => void) => {
    const cv = document.createElement("canvas");
    cv.width = cv.height = size * R;
    const g = cv.getContext("2d")!;
    g.scale(R, R);
    paint(g, size / 2);
    return g.getImageData(0, 0, size * R, size * R);
  };
  const dot = (r: number, fill: string) => (g: CanvasRenderingContext2D, h: number) => {
    g.beginPath(); g.arc(h, h, r + 1.2, 0, Math.PI * 2); g.fillStyle = halo; g.fill();
    g.beginPath(); g.arc(h, h, r, 0, Math.PI * 2); g.fillStyle = fill; g.fill();
  };
  const icons: Record<string, ImageData> = {
    "s-open": make(10, dot(3.2, c.ink)),
    "s-ok": make(12, dot(4.3, c.ok)),
    "s-doubt": make(14, (g, h) => {
      g.beginPath(); g.arc(h, h, 5.4, 0, Math.PI * 2); g.fillStyle = halo; g.fill();
      g.beginPath(); g.arc(h, h, 4.2, 0, Math.PI * 2); g.lineWidth = 2.4; g.strokeStyle = c.doubt; g.stroke();
    }),
    "s-cut": make(16, (g, h) => {
      const d = 4.4;
      g.lineCap = "round";
      g.strokeStyle = halo; g.lineWidth = 6;
      g.beginPath(); g.moveTo(h - d, h - d); g.lineTo(h + d, h + d); g.moveTo(h + d, h - d); g.lineTo(h - d, h + d); g.stroke();
      g.strokeStyle = c.ko; g.lineWidth = 3;
      g.beginPath(); g.moveTo(h - d, h - d); g.lineTo(h + d, h + d); g.moveTo(h + d, h - d); g.lineTo(h - d, h + d); g.stroke();
    }),
    "s-origin": make(22, (g, h) => {
      g.beginPath(); g.arc(h, h, 9.5, 0, Math.PI * 2); g.fillStyle = halo; g.fill();
      g.beginPath(); g.arc(h, h, 7.5, 0, Math.PI * 2); g.fillStyle = c.ink; g.fill();
      g.beginPath(); g.arc(h, h, 3, 0, Math.PI * 2); g.fillStyle = halo; g.fill();
    }),
  };
  for (const [k, img] of Object.entries(icons)) {
    if (m.hasImage(k)) m.updateImage(k, img); else m.addImage(k, img, { pixelRatio: R });
  }
}

/** The basemap in UNLOCK's palette: muted land, quiet roads, small grey labels — light or dark like the page. */
function tintBasemap(m: maplibregl.Map) {
  const d = dark();
  const pal = d ? { bg: "#101a2c", land: "#142037", water: "#0b1626", road: "#25314b", border: "#33405e", text: "#8d99ae" }
    : { bg: "#eef1f4", land: "#e6eaef", water: "#d4dce6", road: "#ffffff", border: "#c3cad5", text: "#687286" };
  for (const l of m.getStyle()?.layers || []) {
    if (["dim", "route-casing", "route", "rst", "rsel", "routestops"].includes(l.id)) continue;
    const id = l.id.toLowerCase();
    try {
      if (l.type === "background") m.setPaintProperty(l.id, "background-color", pal.bg);
      else if (l.type === "fill") m.setPaintProperty(l.id, "fill-color", id.includes("water") ? pal.water : pal.land);
      else if (l.type === "line") m.setPaintProperty(l.id, "line-color", id.includes("water") || id.includes("river") ? pal.water
        : id.includes("boundary") || id.includes("admin") ? pal.border : pal.road);
      else if (l.type === "symbol" && (l.layout as any)?.["text-field"]) {
        m.setPaintProperty(l.id, "text-color", pal.text);
        m.setPaintProperty(l.id, "text-halo-color", pal.bg);
      } else if (l.type === "fill-extrusion") m.setLayoutProperty(l.id, "visibility", "none");
    } catch { /* a layer whose paint is not settable: leave it */ }
  }
}

type Props = {
  stations: RegionStation[];
  reach: { origin: string; classes: Record<string, ReachClass> } | null;
  journey: Journey | null;
  selected: string | null;
  onSelect: (id: string) => void;
  center?: [number, number]; zoom?: number; label?: string;
  children?: React.ReactNode;
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

export function RegionMap({ stations, reach, journey, selected, onSelect, center, zoom, label, children }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [blank, setBlank] = useState(false);
  const [ready, setReady] = useState(0);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!box.current) return;
    const wide = box.current.clientWidth >= 720;
    const m = new maplibregl.Map({ container: box.current, style: STYLE_URL, center: center || [2.4, 48.83], zoom: zoom ? zoom - (wide ? 0.55 : 1) : 8.6,
      attributionControl: { compact: true }, dragRotate: false });
    // the station plate covers the top-left corner on wide screens: keep the region centred in the free part
    if (wide) m.setPadding({ left: Math.min(380, box.current.clientWidth * 0.45), top: 0, right: 0, bottom: 0 });
    map.current = m;
    m.on("error", (e: any) => {
      if (!m.getSource("rstations") && String(e.error?.message || "").length) { setBlank(true); m.setStyle(BLANK); }
    });
    const add = () => {
      if (m.getSource("rstations")) return;
      m.addSource("rstations", { type: "geojson", data: EMPTY });
      m.addSource("route", { type: "geojson", data: EMPTY });
      m.addSource("routestops", { type: "geojson", data: EMPTY });
      drawIcons(m);
      tintBasemap(m);
      m.addLayer({ id: "dim", type: "circle", source: "rstations", filter: ["==", ["get", "dim"], 1],
        paint: { "circle-radius": 2, "circle-color": cssVar("--map-dim", "#A9B3C1") } });
      m.addLayer({ id: "route-casing", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": cssVar("--panel", "#FFFFFF"), "line-width": 9 } });
      m.addLayer({ id: "route", type: "line", source: "route", layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ["get", "color"], "line-width": 5 } });
      m.addLayer({ id: "rsel", type: "circle", source: "rstations", filter: ["==", ["get", "selected"], 1],
        paint: { "circle-radius": 12, "circle-opacity": 0, "circle-stroke-color": cssVar("--focus", "#0F62FE"), "circle-stroke-width": 3 } });
      m.addLayer({ id: "rst", type: "symbol", source: "rstations", filter: ["==", ["get", "dim"], 0],
        layout: {
          "icon-image": ["match", ["get", "state"], "OPEN", "s-open", "CONFIRMED", "s-ok", "DOUBT", "s-doubt", "IF_LIFTS_WORK", "s-doubt",
            "CLOSED", "s-cut", "CUT", "s-cut", "ORIGIN", "s-origin", "s-open"],
          "icon-allow-overlap": true, "icon-ignore-placement": true,
          "symbol-sort-key": ["match", ["get", "state"], "OPEN", 1, "CONFIRMED", 2, "DOUBT", 3, "IF_LIFTS_WORK", 3, "CLOSED", 4, "CUT", 4, "ORIGIN", 5, 0],
        },
        paint: { "icon-opacity": 1, "icon-opacity-transition": { duration: 0, delay: 0 } } });
      m.addLayer({ id: "routestops", type: "circle", source: "routestops",
        paint: { "circle-radius": 6, "circle-color": cssVar("--panel", "#FFFFFF"), "circle-stroke-color": cssVar("--ink", "#14213D"), "circle-stroke-width": 2.5 } });
      for (const id of ["rst", "dim"]) {
        m.on("click", id, (e: any) => { const sid = e.features?.[0]?.properties?.id; if (sid) onSelectRef.current(sid); });
        m.on("mouseenter", id, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", id, () => (m.getCanvas().style.cursor = ""));
      }
      setReady((r) => r + 1);
    };
    m.on("load", add);
    m.on("style.load", add);
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const retheme = () => { if (!m.getSource("rstations")) return; drawIcons(m); tintBasemap(m);
      m.setPaintProperty("dim", "circle-color", cssVar("--map-dim", "#A9B3C1"));
      m.setPaintProperty("route-casing", "line-color", cssVar("--panel", "#FFFFFF"));
      m.setPaintProperty("routestops", "circle-color", cssVar("--panel", "#FFFFFF"));
      m.setPaintProperty("routestops", "circle-stroke-color", cssVar("--ink", "#14213D")); };
    mq?.addEventListener?.("change", retheme);
    return () => { mq?.removeEventListener?.("change", retheme); m.remove(); };
  }, []);

  const lastReach = useRef<string | null>(null);
  useEffect(() => {
    const m = map.current, src = m?.getSource("rstations") as GeoJSONSource | undefined;
    if (!m || !src) return;
    const key = reach ? reach.origin : null;
    const recolour = key !== lastReach.current && !reduced() && m.getLayer("rst");
    lastReach.current = key;
    if (recolour) {
      m.setPaintProperty("rst", "icon-opacity-transition", { duration: 0, delay: 0 });
      m.setPaintProperty("rst", "icon-opacity", 0.15);
    }
    src.setData(stationsGeo(stations, selected, reach));
    if (recolour) window.setTimeout(() => {
      if (!m.getLayer("rst")) return;
      m.setPaintProperty("rst", "icon-opacity-transition", { duration: 550, delay: 0 });
      m.setPaintProperty("rst", "icon-opacity", 1);
    }, 40);
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
      <div ref={box} className="map" role="region" aria-label={tr(`Map of ${label || "the Île-de-France rail, metro and tram"} stations, marked by step-free state. The same information is available as a list below the map.`, `Carte des gares (${label || "Île-de-France"}), marquées selon l'accès sans marche. La même information existe en liste sous la carte.`)} />
      {children}
      {blank && <p className="map-note">{tr("Basemap tiles unavailable — stations are still plotted.", "Fond de carte indisponible — les gares restent affichées.")}</p>}
    </div>
  );
}
