import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);
import type { StationRow } from "../types";

type Props = {
  stations: StationRow[];
  selected: string | null;
  affected: Record<string, number>;
  onSelect: (id: string) => void;
};

const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const BLANK: StyleSpecification = {
  version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#E4E8EC" } }],
};

function toGeoJSON(stations: StationRow[], affected: Record<string, number>, selected: string | null) {
  return {
    type: "FeatureCollection" as const,
    features: stations.map((s) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [s.lon, s.lat] },
      properties: {
        id: s.id, name: s.name, lifts: s.lifts,
        ko: s.lift_states.UNAVAILABLE || 0,
        lost: affected[s.id] || 0,
        selected: s.id === selected ? 1 : 0,
      },
    })),
  };
}

export function MapView({ stations, selected, affected, onSelect }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [basemap, setBasemap] = useState<"tiles" | "blank">("tiles");
  const [ready, setReady] = useState(0);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!box.current) return;
    const m = new maplibregl.Map({
      container: box.current, style: STYLE_URL, center: [2.35, 48.8], zoom: 8.3,
      attributionControl: { compact: true }, dragRotate: false,
    });
    map.current = m;
    m.on("error", (e: any) => {
      if (!m.getSource("stations") && String(e.error?.message || "").length && basemap === "tiles") {
        setBasemap("blank");
        m.setStyle(BLANK);
      }
    });
    const addLayers = () => {
      if (m.getSource("stations")) return;
      m.addSource("stations", { type: "geojson", data: toGeoJSON([], {}, null) });
      m.addLayer({
        id: "stations", type: "circle", source: "stations",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "lifts"], 0, 3, 4, 5, 16, 9],
          "circle-color": ["case", [">", ["get", "lost"], 0], "#C8102E", [">", ["get", "ko"], 0], "#B7791F", ["==", ["get", "lifts"], 0], "#9AA5B4", "#14213D"],
          "circle-stroke-color": ["case", ["==", ["get", "selected"], 1], "#0F62FE", "#FFFFFF"],
          "circle-stroke-width": ["case", ["==", ["get", "selected"], 1], 3.5, 1],
        },
      });
      m.on("click", "stations", (e: any) => {
        const id = e.features?.[0]?.properties?.id;
        if (id) onSelectRef.current(id);
      });
      m.on("mouseenter", "stations", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "stations", () => (m.getCanvas().style.cursor = ""));
      setReady((r) => r + 1);
    };
    m.on("load", addLayers);
    m.on("style.load", addLayers);
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    (m.getSource("stations") as GeoJSONSource | undefined)?.setData(toGeoJSON(stations, affected, selected));
  }, [stations, affected, selected, ready]);

  useEffect(() => {
    const s = stations.find((x) => x.id === selected);
    if (s && map.current) map.current.easeTo({ center: [s.lon, s.lat], zoom: Math.max(map.current.getZoom(), 9.5), duration: 600 });
  }, [selected, stations]);

  return (
    <div className="map-wrap">
      <div ref={box} className="map" aria-label="Map of SNCF stations in Île-de-France. Use the station search for keyboard access." role="img" />
      {basemap === "blank" && <p className="map-note">Basemap tiles unavailable — stations are still plotted.</p>}
    </div>
  );
}
