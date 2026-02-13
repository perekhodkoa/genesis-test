import { useState, useCallback, useRef, useEffect, type DragEvent, type ChangeEvent } from 'react';
import { api } from '../api/client';
import { ApiError } from '../api/client';
import type { SniffResult, UploadResponse, CollectionSummary } from '../api/types';
import './UploadPage.css';

const ACCEPTED_EXTENSIONS = ['.csv', '.tsv', '.xlsx', '.xls', '.json'];

type Step = 'idle' | 'sniffing' | 'preview' | 'uploading' | 'done';

export default function UploadPage() {
  const [step, setStep] = useState<Step>('idle');
  const [file, setFile] = useState<File | null>(null);
  const [sniffResult, setSniffResult] = useState<SniffResult | null>(null);
  const [dbType, setDbType] = useState<'postgres' | 'mongodb'>('postgres');
  const [collectionName, setCollectionName] = useState('');
  const [overwrite, setOverwrite] = useState(false);
  const [existingCollections, setExistingCollections] = useState<string[]>([]);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.get<CollectionSummary[]>('/api/collections/').then(
      (cols) => setExistingCollections(cols.map((c) => c.name))
    ).catch(() => {});
  }, []);

  const nameConflict = existingCollections.includes(collectionName);

  const reset = () => {
    setStep('idle');
    setFile(null);
    setSniffResult(null);
    setDbType('postgres');
    setCollectionName('');
    setOverwrite(false);
    setUploadResult(null);
    setError('');
    // Refresh collections list for next upload
    api.get<CollectionSummary[]>('/api/collections/').then(
      (cols) => setExistingCollections(cols.map((c) => c.name))
    ).catch(() => {});
  };

  const validateFile = (f: File): boolean => {
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return false;
    }
    return true;
  };

  const handleFile = useCallback(async (f: File) => {
    setError('');
    if (!validateFile(f)) return;

    setFile(f);
    setStep('sniffing');

    const formData = new FormData();
    formData.append('file', f);

    try {
      const result = await api.postForm<SniffResult>('/api/upload/sniff', formData);
      setSniffResult(result);
      setDbType(result.recommended_db);
      // Auto-generate collection name from filename
      const baseName = f.name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]/g, '_');
      setCollectionName(baseName.startsWith('_') ? `data${baseName}` : baseName);
      setStep('preview');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to analyze file');
      setStep('idle');
    }
  }, []);

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
  };

  const handleConfirm = async () => {
    if (!file || !sniffResult) return;
    setError('');
    setStep('uploading');

    const formData = new FormData();
    formData.append('original_filename', file.name);
    formData.append('collection_name', collectionName);
    formData.append('db_type', dbType);
    formData.append('overwrite', overwrite ? 'true' : 'false');

    try {
      const result = await api.postForm<UploadResponse>('/api/upload/confirm', formData);
      setUploadResult(result);
      setStep('done');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Upload failed');
      setStep('preview');
    }
  };

  return (
    <div className="upload-page">
      <h2 className="upload-title">Upload Data</h2>

      {error && <div className="upload-error">{error}</div>}

      {step === 'idle' && (
        <div
          className={`upload-dropzone ${dragOver ? 'dragover' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <div className="dropzone-icon">+</div>
          <p className="dropzone-text">Drop a file here or click to browse</p>
          <p className="dropzone-hint">CSV, TSV, Excel (.xlsx), or JSON</p>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(',')}
            onChange={handleFileInput}
            hidden
          />
        </div>
      )}

      {step === 'sniffing' && (
        <div className="upload-loading">
          <div className="spinner" />
          <p>Analyzing {file?.name}...</p>
        </div>
      )}

      {step === 'preview' && sniffResult && (
        <div className="upload-preview">
          <div className="preview-header">
            <h3>{file?.name}</h3>
            <span className="preview-meta">
              {sniffResult.row_count} rows, {sniffResult.columns.length} columns
            </span>
          </div>

          <div className="preview-recommendation">
            <span className="rec-label">Recommended:</span>
            <span className="rec-value">{sniffResult.recommended_db === 'postgres' ? 'PostgreSQL' : 'MongoDB'}</span>
            <span className="rec-reason">{sniffResult.recommendation_reason}</span>
          </div>

          <div className="preview-schema">
            <h4>Schema</h4>
            <table className="schema-table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Type</th>
                  <th>Nullable</th>
                  <th>Sample Values</th>
                </tr>
              </thead>
              <tbody>
                {sniffResult.columns.map((col) => (
                  <tr key={col.name}>
                    <td className="col-name">{col.name}</td>
                    <td><span className="type-badge">{col.dtype}</span></td>
                    <td>{col.nullable ? 'Yes' : 'No'}</td>
                    <td className="col-samples">{col.sample_values.map(String).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="preview-sample">
            <h4>Sample Rows</h4>
            <div className="sample-table-wrap">
              <table className="sample-table">
                <thead>
                  <tr>
                    {sniffResult.columns.map((col) => (
                      <th key={col.name}>{col.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sniffResult.sample_rows.map((row, i) => (
                    <tr key={i}>
                      {sniffResult.columns.map((col) => (
                        <td key={col.name}>{String(row[col.name] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="upload-config">
            <label className="config-field">
              <span>Collection Name</span>
              <input
                type="text"
                value={collectionName}
                onChange={(e) => setCollectionName(e.target.value)}
                pattern="^[a-z][a-z0-9_]*$"
                className="config-input"
              />
              <span className="config-hint">Lowercase, letters/numbers/underscores, starts with letter</span>
            </label>

            <label className="config-field">
              <span>Database Target</span>
              <div className="db-toggle">
                <button
                  className={`db-option ${dbType === 'postgres' ? 'active' : ''}`}
                  onClick={() => setDbType('postgres')}
                >
                  PostgreSQL
                  {sniffResult.recommended_db === 'postgres' && <span className="rec-badge">Rec.</span>}
                </button>
                <button
                  className={`db-option ${dbType === 'mongodb' ? 'active' : ''}`}
                  onClick={() => setDbType('mongodb')}
                >
                  MongoDB
                  {sniffResult.recommended_db === 'mongodb' && <span className="rec-badge">Rec.</span>}
                </button>
              </div>
            </label>
          </div>

          {nameConflict && (
            <div className="overwrite-warning">
              <div className="overwrite-message">
                Collection <strong>{collectionName}</strong> already exists.
              </div>
              <label className="overwrite-toggle">
                <input
                  type="checkbox"
                  checked={overwrite}
                  onChange={(e) => setOverwrite(e.target.checked)}
                />
                <span>Overwrite existing data</span>
              </label>
            </div>
          )}

          <div className="upload-actions">
            <button className="btn-secondary" onClick={reset}>Cancel</button>
            <button
              className="btn-primary"
              onClick={handleConfirm}
              disabled={!collectionName.match(/^[a-z][a-z0-9_]*$/) || (nameConflict && !overwrite)}
            >
              {nameConflict && overwrite ? 'Replace' : 'Upload to'} {dbType === 'postgres' ? 'PostgreSQL' : 'MongoDB'}
            </button>
          </div>
        </div>
      )}

      {step === 'uploading' && (
        <div className="upload-loading">
          <div className="spinner" />
          <p>Uploading {sniffResult?.row_count} rows to {dbType}...</p>
        </div>
      )}

      {step === 'done' && uploadResult && (
        <div className="upload-done">
          <div className="done-icon">&#10003;</div>
          <h3>Upload Complete</h3>
          <p className="done-message">{uploadResult.message}</p>
          <div className="done-details">
            <span>Collection: <strong>{uploadResult.collection_name}</strong></span>
            <span>Database: <strong>{uploadResult.db_type}</strong></span>
            <span>Rows: <strong>{uploadResult.row_count}</strong></span>
            <span>Columns: <strong>{uploadResult.column_count}</strong></span>
          </div>
          <button className="btn-primary" onClick={reset}>Upload Another File</button>
        </div>
      )}
    </div>
  );
}
