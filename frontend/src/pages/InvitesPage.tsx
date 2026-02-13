import { useState, useEffect, useCallback } from 'react';
import { api, ApiError } from '../api/client';
import type { InviteCodeResponse, InviteCodeDetail } from '../api/types';
import './InvitesPage.css';

export default function InvitesPage() {
  const [invites, setInvites] = useState<InviteCodeDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState<string | null>(null);

  const fetchInvites = useCallback(async () => {
    try {
      const data = await api.get<InviteCodeDetail[]>('/api/auth/invites');
      setInvites(data);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInvites();
  }, [fetchInvites]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const res = await api.post<InviteCodeResponse>('/api/auth/invites', {});
      await copyToClipboard(res.code);
      await fetchInvites();
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Clipboard API may not be available
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const isExpired = (expiresAt: string) => new Date(expiresAt) < new Date();

  return (
    <div className="invites-page">
      <div className="invites-container">
        <div className="invites-header">
          <div>
            <h1 className="invites-title">Invite Codes</h1>
            <p className="invites-subtitle">Generate codes to invite new users. Each code is single-use and expires in 24 hours.</p>
          </div>
          <button
            className="invites-generate-btn"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? 'Generating...' : 'Generate invite'}
          </button>
        </div>

        {error && <div className="invites-error">{error}</div>}

        {loading ? (
          <div className="invites-loading">Loading...</div>
        ) : invites.length === 0 ? (
          <div className="invites-empty">
            No invite codes yet. Generate one to invite someone.
          </div>
        ) : (
          <div className="invites-list">
            {invites.map((inv) => {
              const expired = isExpired(inv.expires_at);
              const status = inv.is_used ? 'used' : expired ? 'expired' : 'active';

              return (
                <div key={inv.code} className={`invite-card invite-${status}`}>
                  <div className="invite-code-row">
                    <code className="invite-code">{inv.code}</code>
                    {status === 'active' && (
                      <button
                        className="invite-copy-btn"
                        onClick={() => copyToClipboard(inv.code)}
                      >
                        {copied === inv.code ? 'Copied!' : 'Copy'}
                      </button>
                    )}
                    <span className={`invite-badge invite-badge-${status}`}>
                      {status}
                    </span>
                  </div>
                  <div className="invite-meta">
                    <span>Created {formatDate(inv.created_at)}</span>
                    <span>Expires {formatDate(inv.expires_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
