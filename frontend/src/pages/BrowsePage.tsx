import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ApiError } from '../api/client';
import type { CollectionSummary, CollectionDetail } from '../api/types';
import './BrowsePage.css';

export default function BrowsePage() {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      const data = await api.get<CollectionSummary[]>('/api/collections/');
      setCollections(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load collections');
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = async (name: string) => {
    if (expanded === name) {
      setExpanded(null);
      setDetail(null);
      return;
    }

    setExpanded(name);
    setDetail(null);
    setDetailLoading(true);

    try {
      const data = await api.get<CollectionDetail>(`/api/collections/${name}`);
      setDetail(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load details');
    } finally {
      setDetailLoading(false);
    }
  };

  const filtered = collections.filter(
    (c) =>
      c.name.toLowerCase().includes(search.toLowerCase()) ||
      c.original_filename.toLowerCase().includes(search.toLowerCase()) ||
      c.description.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div className="browse-page">
        <div className="browse-loading"><div className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="browse-page">
      <div className="browse-header">
        <h2 className="browse-title">Data Browser</h2>
        <span className="browse-count">{collections.length} collection{collections.length !== 1 ? 's' : ''}</span>
      </div>

      {error && <div className="browse-error">{error}</div>}

      {collections.length === 0 ? (
        <div className="browse-empty">
          <p>No collections yet.</p>
          <p className="browse-empty-hint">Upload data files from the Upload tab to get started.</p>
        </div>
      ) : (
        <>
          <input
            type="text"
            placeholder="Search collections..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="browse-search"
          />

          <div className="browse-list">
            {filtered.map((col) => (
              <div key={col.name} className={`browse-card ${expanded === col.name ? 'expanded' : ''}`}>
                <button className="browse-card-header" onClick={() => toggleExpand(col.name)}>
                  <div className="card-info">
                    <span className="card-name">{col.name}</span>
                    <span className={`card-db-badge ${col.db_type}`}>
                      {col.db_type === 'postgres' ? 'PostgreSQL' : 'MongoDB'}
                    </span>
                    {col.is_public && <span className="card-public-badge">Public</span>}
                    {!col.is_own && <span className="card-shared-badge">Shared</span>}
                  </div>
                  <div className="card-meta">
                    <span>{col.row_count} rows</span>
                    <span>{col.column_count} cols</span>
                    <span className="card-file">{col.original_filename}</span>
                  </div>
                  <p className="card-desc">{col.description}</p>
                  <span className={`card-chevron ${expanded === col.name ? 'open' : ''}`}>&#9662;</span>
                </button>

                {expanded === col.name && (
                  <div className="browse-card-body">
                    {detailLoading ? (
                      <div className="card-body-loading"><div className="spinner" /></div>
                    ) : detail ? (
                      <>
                        <div className="detail-section">
                          <h4>Schema</h4>
                          <table className="detail-table">
                            <thead>
                              <tr>
                                <th>Column</th>
                                <th>Type</th>
                                <th>Nullable</th>
                                <th>Sample Values</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detail.columns.map((col) => (
                                <tr key={col.name}>
                                  <td className="col-mono">{col.name}</td>
                                  <td><span className="type-badge">{col.dtype}</span></td>
                                  <td>{col.nullable ? 'Yes' : 'No'}</td>
                                  <td className="col-samples">{col.sample_values.map(String).join(', ')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>

                        <div className="detail-section">
                          <h4>Sample Data</h4>
                          <div className="detail-table-wrap">
                            <table className="detail-table">
                              <thead>
                                <tr>
                                  {detail.columns.map((col) => (
                                    <th key={col.name}>{col.name}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {detail.sample_rows.map((row, i) => (
                                  <tr key={i}>
                                    {detail.columns.map((col) => (
                                      <td key={col.name}>{String(row[col.name] ?? '')}</td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            ))}

            {filtered.length === 0 && (
              <p className="browse-no-results">No collections match "{search}"</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
