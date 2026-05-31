import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getOnboarding, submitOnboarding } from '../api/user'
import { useAuth } from '../context/AuthContext'
import Loading from '../components/Loading'

export default function Onboarding() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const { data, isLoading } = useQuery({ queryKey: ['onboarding'], queryFn: getOnboarding })
  const [selections, setSelections] = useState({})
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => submitOnboarding(selections),
    onSuccess: async () => { await refresh(); navigate('/dashboard') },
    onError: (err) => setError(err.message || 'Failed to save'),
  })

  if (isLoading) return <Loading full />

  const { teams_by_league = {}, league_labels = {} } = data ?? {}

  function handleSelect(league, teamId) {
    setSelections(s => ({ ...s, [`${league.toLowerCase()}_team_id`]: teamId }))
  }

  return (
    <div className="onboarding-container">
      <h1 className="onboarding-title">Pick Your Teams</h1>
      <p className="onboarding-sub">Select your team for each sport. You can update these anytime.</p>

      {error && <div className="flash flash-error">{error}</div>}

      <div className="onboarding-leagues">
        {Object.entries(teams_by_league).map(([league, teams]) => (
          <div key={league} className="onboarding-league-section">
            <div className="onboarding-league-label">{league_labels[league] || league}</div>
            <select value={selections[`${league.toLowerCase()}_team_id`] || ''}
              onChange={e => handleSelect(league, e.target.value)}>
              <option value="">No team</option>
              {teams.map(t => (
                <option key={t.id} value={t.id}>{t.city} {t.name}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      <button className="btn-primary btn-full" style={{ marginTop: '2rem' }}
        onClick={() => mut.mutate()} disabled={mut.isPending}>
        {mut.isPending ? 'Saving…' : 'Lock In My Teams'}
      </button>
    </div>
  )
}
