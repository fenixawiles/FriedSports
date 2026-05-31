export default function Loading({ full = false }) {
  if (full) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '60vh', color: 'var(--text-muted)', fontSize: '0.9rem'
      }}>
        Loading…
      </div>
    )
  }
  return <div style={{ padding: '2rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Loading…</div>
}
