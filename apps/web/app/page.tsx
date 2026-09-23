'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import {
  formatDistance,
  formatDuration,
  gpxUrl,
  searchRoutes,
  type LatLng,
  type RouteResult,
} from '@/lib/api'

const MapView = dynamic(() => import('@/components/MapView'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-sky-100 text-slate-500">
      Loading map…
    </div>
  ),
})

const DEFAULT_ORIGIN: LatLng = { lat: 45.815, lng: 15.982 } // Zagreb

export default function Home() {
  const [origin, setOrigin] = useState<LatLng>(DEFAULT_ORIGIN)
  const [activity, setActivity] = useState<'run' | 'walk'>('run')
  const [distanceKm, setDistanceKm] = useState(5)
  const [avoidBusyRoads, setAvoidBusyRoads] = useState(true)
  const [preferQuiet, setPreferQuiet] = useState(true)

  const [results, setResults] = useState<RouteResult[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  const runSearch = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await searchRoutes({
        origin,
        activity,
        distanceKm,
        avoidBusyRoads,
        preferQuiet,
      })
      setResults(res.results)
      setSelected(res.results[0]?.route_id ?? null)
      setSearched(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const useMyLocation = () => {
    if (!('geolocation' in navigator)) {
      setError('Geolocation is not available in this browser.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => setOrigin({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setError('Could not get your location — drag the pin instead.'),
    )
  }

  return (
    <main className="flex h-screen flex-col md:flex-row">
      <aside className="flex w-full flex-col gap-4 overflow-y-auto border-b border-slate-200 bg-white p-5 md:w-96 md:border-b-0 md:border-r">
        <header>
          <h1 className="text-2xl font-bold text-brand">Mappet 🗺️</h1>
          <p className="text-sm text-slate-500">
            Find nearby loops shaped like recognisable things.
          </p>
        </header>

        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Origin
          </label>
          <p className="font-mono text-sm text-slate-700">
            {origin.lat.toFixed(4)}, {origin.lng.toFixed(4)}
          </p>
          <button
            type="button"
            onClick={useMyLocation}
            className="mt-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            📍 Use my location
          </button>
          <p className="text-xs text-slate-400">Or click / drag the pin on the map.</p>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Activity
          </label>
          <div className="flex overflow-hidden rounded-md border border-slate-300">
            {(['run', 'walk'] as const).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setActivity(a)}
                className={`flex-1 px-3 py-2 text-sm font-medium capitalize ${
                  activity === a
                    ? 'bg-brand text-white'
                    : 'bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                {a === 'run' ? '🏃 Run' : '🚶 Walk'}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1">
          <label className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Distance</span>
            <span className="text-sm font-bold text-brand">{distanceKm} km</span>
          </label>
          <input
            type="range"
            min={2}
            max={100}
            step={1}
            value={distanceKm}
            onChange={(e) => setDistanceKm(Number(e.target.value))}
            className="w-full accent-brand"
          />
          <div className="flex justify-between text-xs text-slate-400">
            <span>2 km</span>
            <span>100 km</span>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Preferences
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={avoidBusyRoads}
              onChange={(e) => setAvoidBusyRoads(e.target.checked)}
              className="accent-brand"
            />
            Avoid busy roads
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={preferQuiet}
              onChange={(e) => setPreferQuiet(e.target.checked)}
              className="accent-brand"
            />
            Prefer quiet streets / parks
          </label>
        </div>

        <button
          type="button"
          onClick={runSearch}
          disabled={loading}
          className="rounded-md bg-brand px-4 py-2.5 font-semibold text-white shadow-sm hover:bg-brand-dark disabled:opacity-60"
        >
          {loading ? 'Searching…' : '✨ Find shapes'}
        </button>

        {error && (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        <div className="flex-1 space-y-2">
          {searched && !loading && results.length === 0 && (
            <p className="text-sm text-slate-500">
              No strong shapes here. Try a different spot or widen the distance.
            </p>
          )}
          {results.map((r) => {
            const isSel = r.route_id === selected
            return (
              <button
                key={r.route_id}
                type="button"
                onClick={() => setSelected(r.route_id)}
                className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition ${
                  isSel
                    ? 'border-brand bg-blue-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <span className="text-2xl">{r.emoji}</span>
                <span className="flex-1">
                  <span className="block font-semibold capitalize text-slate-800">
                    {r.label}
                  </span>
                  <span className="block text-xs text-slate-500">
                    {formatDistance(r.distance_m)} · {formatDuration(r.est_time_s)} ·{' '}
                    {Math.round(r.confidence * 100)}% match
                  </span>
                </span>
                <a
                  href={gpxUrl(r.route_id)}
                  onClick={(e) => e.stopPropagation()}
                  className="rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  GPX
                </a>
              </button>
            )
          })}
        </div>

        <p className="text-center text-xs text-slate-400">
          Results are mock data from the local Route Engine — see docs/ARCHITECTURE.md.
        </p>
      </aside>

      <section className="relative min-h-[50vh] flex-1">
        <MapView
          origin={origin}
          onOriginChange={setOrigin}
          results={results}
          selectedRouteId={selected}
          onSelectRoute={setSelected}
        />
      </section>
    </main>
  )
}
