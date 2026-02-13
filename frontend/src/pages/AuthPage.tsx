import { useState, type FormEvent } from 'react';
import { useAuth } from '../hooks/useAuth';
import { ApiError } from '../api/client';
import './AuthPage.css';

export default function AuthPage() {
  const { login, register } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        await login(username, password);
      } else {
        await register(username, password, inviteCode || undefined);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Something went wrong');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-brand">Data Lens</h1>
        <p className="auth-subtitle">Analyze your data with natural language</p>

        <div className="auth-tabs">
          <button
            className={`auth-tab ${isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(true)}
          >
            Sign in
          </button>
          <button
            className={`auth-tab ${!isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(false)}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <div className="auth-error">{error}</div>}

          <label className="auth-label">
            <span>Username</span>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="auth-input"
              required
              minLength={3}
              autoFocus
            />
          </label>

          <label className="auth-label">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="auth-input"
              required
              minLength={6}
            />
          </label>

          {!isLogin && (
            <label className="auth-label">
              <span>Invite code</span>
              <input
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                className="auth-input"
                placeholder="Required unless you're the first user"
              />
            </label>
          )}

          <button type="submit" className="auth-submit" disabled={loading}>
            {loading ? 'Please wait...' : isLogin ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </div>
  );
}
