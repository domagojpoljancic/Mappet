'use client'

import { useMemo } from 'react'
import {
  MapContainer,
  Marker,
  Polyline,
  Popup,
  TileLayer,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import type { LatLng, RouteResult } from '@/lib/api'

const DefaultIcon = L.icon({
  iconRetinaUrl: (markerIcon2x as unknown as { src: string }).src,
  iconUrl: (markerIcon as unknown as { src: string }).src,
  shadowUrl: (markerShadow as unknown as { src: string }).src,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})
L.Marker.prototype.options.icon = DefaultIcon

const PALETTE = ['#2563eb', '#db2777', '#16a34a', '#d97706', '#7c3aed', '#0891b2']

function ClickHandler({ onPick }: { onPick: (p: LatLng) => void }) {
  useMapEvents({
    click(e) {
      onPick({ lat: e.latlng.lat, lng: e.latlng.lng })
    },
  })
  return null
}

type Props = {
  origin: LatLng
  onOriginChange: (p: LatLng) => void
  results: RouteResult[]
  selectedRouteId: string | null
  onSelectRoute: (routeId: string) => void
}

export default function MapView({
  origin,
  onOriginChange,
  results,
  selectedRouteId,
  onSelectRoute,
}: Props) {
  const center = useMemo<[number, number]>(() => [origin.lat, origin.lng], [origin])

  return (
    <MapContainer center={center} zoom={14} scrollWheelZoom className="h-full w-full">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickHandler onPick={onOriginChange} />

      <Marker
        position={center}
        draggable
        eventHandlers={{
          dragend(e) {
            const p = e.target.getLatLng()
            onOriginChange({ lat: p.lat, lng: p.lng })
          },
        }}
      >
        <Popup>Start / origin — drag me or click the map to move</Popup>
      </Marker>

      {results.map((r, i) => {
        const selected = r.route_id === selectedRouteId
        return (
          <Polyline
            key={r.route_id}
            positions={r.polyline}
            pathOptions={{
              color: PALETTE[i % PALETTE.length],
              weight: selected ? 6 : 3,
              opacity: selectedRouteId && !selected ? 0.35 : 0.9,
            }}
            eventHandlers={{ click: () => onSelectRoute(r.route_id) }}
          >
            <Popup>
              {r.emoji} {r.label} · {(r.distance_m / 1000).toFixed(1)} km
            </Popup>
          </Polyline>
        )
      })}
    </MapContainer>
  )
}
