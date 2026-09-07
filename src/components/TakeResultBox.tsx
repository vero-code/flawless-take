import { downloadPdf, getMediaUrl } from '../config'
import type { CheckResult, CompareResult, Status } from '../types'
import { Markdown } from './Markdown'
import { MatchBadge } from './MatchBadge'

type TakeResultBoxProps = {
  status: Status
  result: CheckResult | null
  compareResult: CompareResult | null
  errorMsg: string | null
}

export function TakeResultBox({ status, result, compareResult, errorMsg }: TakeResultBoxProps) {
  if (status === 'error' && errorMsg) {
    return (
      <div className="result-box result-box--err">
        <p className="result-label">Error</p>
        <p className="result-value">{errorMsg}</p>
      </div>
    )
  }

  if (status !== 'success') return null

  return (
    <>
      {/* Single check result */}
      {result && (
        <div className="result-box result-box--ok">
          <p className="result-label">
            Continuity report — {result.character} · Scene {result.scene} · Take {result.take}
            {result.script_grounded && <span className="grounded-badge"> · script grounded</span>}
          </p>
          {result.preview_url && (
            <div className="result-preview-container">
              <img src={getMediaUrl(result.preview_url)} className="result-preview-img" alt={`Take ${result.take}`} />
            </div>
          )}
          <Markdown text={result.result} />
          <p className="result-meta-line">
            {result.filename} · {(result.size_bytes / 1024).toFixed(1)} KB
          </p>
          {result.id && (
            <div className="pdf-export-row">
              <button
                type="button"
                className="pdf-export-btn"
                onClick={() => downloadPdf(result.id!, `continuity_${result.scene}_take_${result.take}.pdf`)}
              >
                📄 Export Continuity Log (PDF)
              </button>
            </div>
          )}
        </div>
      )}

      {/* Compare takes result */}
      {compareResult && (
        <div className="result-box result-box--ok">
          <p className="result-label">
            Comparison — {compareResult.character} · Scene {compareResult.scene}
            · Take {compareResult.take_ref} vs {compareResult.take_current}
            {' '}<MatchBadge score={compareResult.match_score} />
            {compareResult.script_grounded && <span className="grounded-badge"> · script grounded</span>}
          </p>
          {(compareResult.preview_ref_url || compareResult.preview_cur_url) && (
            <div className="history-previews">
              {compareResult.preview_ref_url && (
                <img src={getMediaUrl(compareResult.preview_ref_url)} className="history-preview-img" alt="Reference take" />
              )}
              {compareResult.preview_cur_url && (
                <img src={getMediaUrl(compareResult.preview_cur_url)} className="history-preview-img" alt="Current take" />
              )}
            </div>
          )}
          <Markdown text={compareResult.differences} />
          <p className="result-meta-line">
            REF: {compareResult.ref_filename} · CUR: {compareResult.cur_filename}
          </p>
          {compareResult.id && (
            <div className="pdf-export-row">
              <button
                type="button"
                className="pdf-export-btn"
                onClick={() => downloadPdf(compareResult.id!, `continuity_${compareResult.scene}_take_${compareResult.take_ref}_vs_${compareResult.take_current}.pdf`)}
              >
                📄 Export Continuity Log (PDF)
              </button>
            </div>
          )}
        </div>
      )}
    </>
  )
}
