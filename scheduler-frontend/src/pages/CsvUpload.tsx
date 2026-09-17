import { useRef, useState } from 'react'
import {
  uploadAvailability,
  parseTimeOffReport,
  applyTimeOffRecords,
  parseScheduleTemplate,
  saveScheduleTemplate,
  type AvailabilityUploadResult,
  type TimeOffRecord,
  type TimeOffApplyResult,
  type ScheduleTemplateEntry,
  type ScheduleTemplateParseResult,
  type ScheduleTemplateSaveResult,
} from '../api'
import { useCurrentRestaurant } from '../hooks/useCurrentRestaurant'
import './CsvUpload.css'

function ScheduleTemplateUpload({ restaurantId }: { restaurantId: number }) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parsed, setParsed] = useState<ScheduleTemplateParseResult | null>(null)
  const [entries, setEntries] = useState<ScheduleTemplateEntry[] | null>(null)

  const [templateName, setTemplateName] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveResult, setSaveResult] = useState<ScheduleTemplateSaveResult | null>(null)

  async function handleParse() {
    if (!selectedFile) return
    setParsing(true)
    setParseError(null)
    setParsed(null)
    setEntries(null)
    setSaveResult(null)
    try {
      const result = await parseScheduleTemplate(restaurantId, selectedFile)
      setParsed(result)
      setEntries(result.entries)
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err))
    } finally {
      setParsing(false)
    }
  }

  async function handleSave() {
    if (!entries || !templateName.trim()) return
    setSaving(true)
    setSaveError(null)
    try {
      const result = await saveScheduleTemplate(restaurantId, templateName.trim(), entries)
      setSaveResult(result)
      setParsed(null)
      setEntries(null)
      setTemplateName('')
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const matchedCount = entries?.filter((e) => e.employee_id != null).length ?? 0

  return (
    <div className="csv-section">
      <h2>Schedule Template</h2>
      <p className="csv-upload-intro">
        Upload a past (or hand-crafted) week's schedule — one row per employee, one column per
        day of week, each cell an <code>HH:MM-HH:MM</code> shift (blank or "OFF" for a day off).
        Save it as a named template, then pick it when generating a new week's schedule to softly
        bias the solver toward reproducing this pattern — availability, time off, and all other
        enabled constraints still take priority over it.
      </p>

      <div className="csv-upload-controls">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          onChange={(e) => {
            setSelectedFile(e.target.files?.[0] ?? null)
            setParsed(null)
            setEntries(null)
            setSaveResult(null)
          }}
        />
        <button className="primary" onClick={handleParse} disabled={!selectedFile || parsing}>
          {parsing ? 'Parsing...' : 'Parse schedule'}
        </button>
      </div>

      {parseError && <p className="csv-error">Could not parse file: {parseError}</p>}

      {parsed && entries && (
        <div className="csv-result">
          <h3>Parsed {parsed.rows_read} row(s) — {matchedCount} of {entries.length} shift(s) matched an employee</h3>
          {parsed.unmatched_labels.length > 0 && (
            <div className="csv-warning">
              <strong>{parsed.unmatched_labels.length} name(s) in the file didn't match any employee:</strong>
              <p>{parsed.unmatched_labels.join(', ')}</p>
            </div>
          )}
          {parsed.unparsed_cells.length > 0 && (
            <div className="csv-warning">
              <strong>{parsed.unparsed_cells.length} cell(s) could not be read as a shift and were skipped:</strong>
              <p>{parsed.unparsed_cells.join('; ')}</p>
            </div>
          )}

          <div className="time-off-table-wrapper">
            <table className="time-off-table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Day</th>
                  <th>Shift</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={i} className={e.employee_id == null ? 'time-off-inactive' : ''}>
                    <td>
                      {e.employee_name ?? e.raw_employee_label}
                      {e.employee_id == null && <span className="badge badge-warning"> no match</span>}
                    </td>
                    <td>{e.day_name}</td>
                    <td>{e.start_time}–{e.end_time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="time-off-actions">
            <input
              type="text"
              placeholder="Template name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
            />
            <button
              className="primary"
              onClick={handleSave}
              disabled={saving || matchedCount === 0 || !templateName.trim()}
            >
              {saving ? 'Saving...' : `Save template (${matchedCount} shift(s))`}
            </button>
          </div>
          {saveError && <p className="csv-error">Could not save: {saveError}</p>}
        </div>
      )}

      {saveResult && (
        <div className="csv-result csv-created">
          <h3>Saved "{saveResult.name}"</h3>
          <ul>
            <li>{saveResult.entries_saved} shift(s) saved</li>
            {saveResult.entries_skipped_unmatched > 0 && (
              <li>{saveResult.entries_skipped_unmatched} unmatched shift(s) skipped</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

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
  if (!restaurant) return null

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

      <hr className="csv-section-divider" />
      <ScheduleTemplateUpload restaurantId={restaurant.restaurant_id} />
    </div>
  )
}

export default CsvUpload
