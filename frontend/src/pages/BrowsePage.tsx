import { useState, useEffect } from 'react';
import { api } from '../api/client';
import { ApiError } from '../api/client';
import type { CollectionSummary, CollectionDetail } from '../api/types';
import TrashIcon from '../components/icons/TrashIcon';
import './BrowsePage.css';

export default function BrowsePage() {
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<CollectionDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

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

  const togglePublic = async (name: string, currentlyPublic: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    setToggling(name);
    try {
      await api.patch(`/api/collections/${name}/public`, { is_public: !currentlyPublic });
      setCollections((prev) =>
        prev.map((c) => c.name === name ? { ...c, is_public: !currentlyPublic } : c)
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to update sharing');
    } finally {
      setToggling(null);
    }
  };

  const deleteCollection = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete collection "${name}"? This will permanently remove all data.`)) return;
    setDeleting(name);
    try {
      await api.del(`/api/collections/${name}`);
      setCollections((prev) => prev.filter((c) => c.name !== name));
      if (expanded === name) {
        setExpanded(null);
        setDetail(null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to delete collection');
    } finally {
      setDeleting(null);
    }
  };

  // Detect name collisions for disambiguation
  const nameCounts = collections.reduce<Record<string, number>>((acc, c) => {
    acc[c.name] = (acc[c.name] || 0) + 1;
    return acc;
  }, {});

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
              <div key={`${col.name}-${col.owner_username}`} className={`browse-card ${expanded === col.name ? 'expanded' : ''}`}>
                <button className="browse-card-header" onClick={() => toggleExpand(col.name)}>
                  <div className="card-info">
                    <span className="card-name">{col.name}</span>
                    <span className={`card-db-badge ${col.db_type}`}>
                      {col.db_type === 'postgres' ? 'PostgreSQL' : 'MongoDB'}
                    </span>
                    {col.is_public && <span className="card-public-badge">Public</span>}
                    {!col.is_own && <span className="card-shared-badge">Shared by: {col.owner_username}</span>}
                    {(nameCounts[col.name] ?? 0) > 1 && col.is_own && col.owner_username && (
                      <span className="card-owner-badge">Yours</span>
                    )}
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
                    {col.is_own && (
                      <div className="card-share-bar">
                        <button
                          className={`share-btn ${col.is_public ? 'shared' : ''}`}
                          onClick={(e) => togglePublic(col.name, col.is_public, e)}
                          disabled={toggling === col.name}
                        >
                          {toggling === col.name
                            ? 'Updating...'
                            : col.is_public
                              ? 'Make Private'
                              : 'Share Publicly'}
                        </button>
                        <span className="share-hint">
                          {col.is_public
                            ? 'This collection is visible to all users'
                            : 'Only you can see this collection'}
                        </span>
                        <button
                          className="delete-btn"
                          onClick={(e) => deleteCollection(col.name, e)}
                          disabled={deleting === col.name}
                          title="Delete collection"
                        >
                          <TrashIcon size={13} />
                        </button>
                      </div>
                    )}

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
