import { useRef, useState } from 'react'
import {
  uploadAvailability,
  parseTimeOffReport,
  applyTimeOffRecords,
  type AvailabilityUploadResult,
  type TimeOffRecord,
  type TimeOffApplyResult,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import './CsvUpload.css'

function TimeOffUpload({ restaurantId }: { restaurantId: number }) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [records, setRecords] = useState<TimeOffRecord[] | null>(null)

  const [applying, setApplying] = useState(false)
  const [applyError, setApplyError] = useState<string | null>(null)
  const [applyResult, setApplyResult] = useState<TimeOffApplyResult | null>(null)

  async function handleParse() {
    if (!selectedFile) return
    setParsing(true)
    setParseError(null)
    setRecords(null)
    setApplyResult(null)
    try {
      const parsed = await parseTimeOffReport(restaurantId, selectedFile)
      setRecords(parsed)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err))
    } finally {
      setParsing(false)
    }
  }

  async function handleApply() {
    if (!records) return
    setApplying(true)
    setApplyError(null)
    try {
      const result = await applyTimeOffRecords(restaurantId, records)
      setApplyResult(result)
      setRecords(null)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setApplyError(err instanceof Error ? err.message : String(err))
    } finally {
      setApplying(false)
    }
  }

  const approvedCount = records?.filter((r) => r.status === 'Approved').length ?? 0
  const unmatchedCount = records?.filter((r) => r.status === 'Approved' && r.employee_id == null).length ?? 0

  return (
    <div className="csv-section">
      <h2>Time Off Requests</h2>
      <p className="csv-upload-intro">
        Upload a Time Off &amp; Request Report (copy/pasted export, not a real CSV — no reformatting
        needed). Every <strong>Approved</strong> request marks that employee unavailable for each day in
        its date range, overriding their existing availability for those specific dates. Denied,
        Canceled, and Pending requests are shown but never applied.
      </p>

      <div className="csv-upload-controls">
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.csv"
          onChange={(e) => {
            setSelectedFile(e.target.files?.[0] ?? null)
            setRecords(null)
            setApplyResult(null)
          }}
        />
        <button className="primary" onClick={handleParse} disabled={!selectedFile || parsing}>
          {parsing ? 'Parsing...' : 'Parse report'}
        </button>
      </div>

      {parseError && <p className="csv-error">Could not parse report: {parseError}</p>}

      {records && (
        <div className="csv-result">
          <h3>Parsed {records.length} request(s) — {approvedCount} approved will be applied</h3>
          {unmatchedCount > 0 && (
            <p className="csv-warning">
              {unmatchedCount} approved request(s) reference a name that doesn't match any employee —
              those will be skipped.
            </p>
          )}
          <div className="time-off-table-wrapper">
            <table className="time-off-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Dates</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r, i) => (
                  <tr key={i} className={r.status !== 'Approved' ? 'time-off-inactive' : ''}>
                    <td>
                      {r.employee_name}
                      {r.status === 'Approved' && r.employee_id == null && (
                        <span className="badge badge-warning"> no match</span>
                      )}
                    </td>
                    <td>{r.start_date === r.end_date ? r.start_date : `${r.start_date} → ${r.end_date}`}</td>
                    <td>{r.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="time-off-actions">
            <button onClick={() => setRecords(null)} disabled={applying}>Cancel</button>
            <button className="primary" onClick={handleApply} disabled={applying || approvedCount === 0}>
              {applying ? 'Applying...' : `Apply ${approvedCount} approved request(s)`}
            </button>
          </div>
          {applyError && <p className="csv-error">Could not apply: {applyError}</p>}
        </div>
      )}

      {applyResult && (
        <div className="csv-result csv-created">
          <h3>Applied</h3>
          <ul>
            <li>{applyResult.requests_applied} approved request(s) applied</li>
            <li>{applyResult.days_blocked} day(s) marked unavailable</li>
            {applyResult.requests_skipped_not_approved > 0 && (
              <li>{applyResult.requests_skipped_not_approved} non-approved request(s) skipped</li>
            )}
            {applyResult.requests_skipped_unmatched > 0 && (
              <li>{applyResult.requests_skipped_unmatched} unmatched-employee request(s) skipped</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

function CsvUpload() {
  const { restaurant, loading: restaurantLoading, error: restaurantError } = useCurrentRestaurant()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [autoCreateEmployees, setAutoCreateEmployees] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<AvailabilityUploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleUpload() {
    if (!restaurant || !selectedFile) return
    setUploading(true)
    setError(null)
    setResult(null)
    try {
      const uploadResult = await uploadAvailability(restaurant.restaurant_id, selectedFile, autoCreateEmployees)
      setResult(uploadResult)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setUploading(false)
    }
  }

  if (restaurantLoading) return <p>Loading...</p>
  if (restaurantError) return <p className="form-error">{restaurantError}</p>

  return (
    <div>
      <h1>CSV Upload</h1>
      <p className="csv-upload-intro">
        Upload this week's employee availability. For every employee found in the file,
        their existing availability is completely replaced by what's in this file — this
        is the source of truth the solver uses; it overrides everything else (an employee
        will never be scheduled outside what's uploaded here, no matter what other rules
        are configured in Constraints).
      </p>

      <div className="csv-format-hint">
        <strong>Just upload your HotSchedules Availability Report as-is</strong> — no
        reformatting needed. It's recognized automatically:
        <pre>{`Employees,Sun  7/19/26,Mon  7/20/26,...
"Aaliyah Brown","Available All Day","Partially Available 11:00 AM - 5:00 PM",...`}</pre>
        <span>
          Employees are matched by name. A pre-formatted long CSV
          (<code>employee_id,day,start_time,end_time</code>) also works, if you have one.
        </span>
      </div>

      <div className="csv-upload-controls">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
        />
        <button className="primary" onClick={handleUpload} disabled={!selectedFile || uploading}>
          {uploading ? 'Uploading...' : 'Upload availability'}
        </button>
      </div>

      <label className="csv-auto-create-toggle">
        <input
          type="checkbox"
          checked={autoCreateEmployees}
          onChange={(e) => setAutoCreateEmployees(e.target.checked)}
        />
        Automatically add employees found in this file but not yet in the system
        (name-matched files only — a long-format file with just an employee_id has no name to create a record from)
      </label>

      {error && <p className="csv-error">Upload failed: {error}</p>}

      {result && (
        <div className="csv-result">
          <h2>Upload complete</h2>
          <ul>
            <li>{result.rows_read} rows read</li>
            <li>{result.employees_updated} employees' availability updated</li>
            <li>{result.windows_applied} availability windows applied</li>
          </ul>
          {result.created_employees.length > 0 && (
            <div className="csv-warning csv-created">
              <strong>{result.created_employees.length} new employee(s) automatically added:</strong>
              <p>{result.created_employees.join(', ')}</p>
            </div>
          )}
          {result.orphaned_employee_ids.length > 0 && (
            <div className="csv-warning">
              <strong>{result.orphaned_employee_ids.length} employee_id(s) in the file didn't match anyone:</strong>
              <p>{result.orphaned_employee_ids.join(', ')}</p>
            </div>
          )}
          {result.unmatched_names.length > 0 && (
            <div className="csv-warning">
              <strong>{result.unmatched_names.length} name(s) in the file didn't match any employee:</strong>
              <p>{result.unmatched_names.join(', ')}</p>
              <p>Check "Automatically add employees" above and re-upload to create them.</p>
            </div>
          )}
        </div>
      )}

      <hr className="csv-section-divider" />
      <TimeOffUpload restaurantId={restaurant.restaurant_id} />
    </div>
  )
}

export default CsvUpload
