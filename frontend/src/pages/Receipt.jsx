import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getReceipt } from '../api/user'
import Loading from '../components/Loading'

export default function Receipt() {
  const { slug } = useParams()
  const { data, isLoading } = useQuery({
    queryKey: ['receipt', slug],
    queryFn: () => getReceipt(slug),
  })

  if (isLoading) return <Loading full />
  const r = data?.receipt
  if (!r) return <div className="empty-state"><p>Receipt not found.</p></div>

  return (
    <div className="receipt-page">
      <h1>{r.title}</h1>
      <div>{r.summary}</div>
      {r.final_score && <div>Final: {r.final_score}</div>}
      <div>{r.shame_points} shame points</div>
    </div>
  )
}
