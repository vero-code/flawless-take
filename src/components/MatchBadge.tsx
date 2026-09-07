const SCORE_CLASS: Record<string, string> = {
  GOOD: 'badge--good',
  FAIR: 'badge--fair',
  POOR: 'badge--poor',
}

/**
 * Match score badge (GOOD / FAIR / POOR)
 */
export function MatchBadge({ score }: { score: string }) {
  return (
    <span className={`match-badge ${SCORE_CLASS[score] ?? ''}`}>{score}</span>
  )
}
