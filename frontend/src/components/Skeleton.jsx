/**
 * Skeleton — shimmer placeholder that matches the shape of real content.
 * Use it inline wherever `isLoading` would otherwise show a spinner.
 *
 * <Skeleton h="1rem" w="60%" />
 * <Skeleton circle size={40} />
 * <SkeletonText lines={2} />
 */

export function Skeleton({ w, h, width, height, circle, size, radius, mb, style = {}, className = '' }) {
  const s = {
    width:        circle ? size : (w || width || '100%'),
    height:       circle ? size : (h || height || '1rem'),
    borderRadius: circle ? '50%' : (radius ?? 'var(--radius-sm)'),
    marginBottom: mb,
    flexShrink: 0,
    ...style,
  }
  return <div className={`skeleton ${className}`} style={s} />
}

export function SkeletonText({ lines = 1, lastWidth = '55%', gap = '0.45rem' }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap }}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} h="0.8rem" w={i === lines - 1 ? lastWidth : '100%'} />
      ))}
    </div>
  )
}
