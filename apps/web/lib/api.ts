export type LatLng = { lat: number; lng: number }

export type RouteResult = {
  route_id: string
  label: string
  emoji: string
  confidence: number
  distance_m: number
  est_time_s: number
  pleasantness: number
  surface_mix: Record<string, number>
  polyline: [number, number][]
}

export type SearchResponse = {
  job_id: string
  status: string
  results: RouteResult[]
}

export type SearchParams = {
  origin: LatLng
  activity: 'run' | 'walk'
  distanceKm: number
  avoidBusyRoads: boolean
  preferQuiet: boolean
}

const ENGINE_URL =
  process.env.NEXT_PUBLIC_ENGINE_URL ?? 'http://localhost:8000'

export async function searchRoutes(params: SearchParams): Promise<SearchResponse> {
  const res = await fetch(`${ENGINE_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin: params.origin,
      activity: params.activity,
      distance_km: params.distanceKm,
      preferences: {
        avoid_busy_roads: params.avoidBusyRoads,
        prefer_quiet: params.preferQuiet,
      },
    }),
  })
  if (!res.ok) {
    throw new Error(`Route engine error: ${res.status}`)
  }
  return res.json()
}

export function gpxUrl(routeId: string): string {
  return `${ENGINE_URL}/route/${routeId}/gpx`
}

export function formatDuration(seconds: number): string {
  const m = Math.round(seconds / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

export function formatDistance(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`
}
