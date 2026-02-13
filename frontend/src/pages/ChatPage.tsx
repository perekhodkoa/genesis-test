import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/client';
import type {
  ChatMessage,
  ChatResponse,
  ChatSessionSummary,
  ChatHistory,
  CollectionSummary,
} from '../api/types';
import ChatMessageView from '../components/ChatMessage';
import ChatInput from '../components/ChatInput';
import TrashIcon from '../components/icons/TrashIcon';
import { useModel } from '../hooks/useModel';
import './ChatPage.css';

export default function ChatPage() {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();
  const { selectedModel } = useModel();

  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(urlSessionId ?? null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [pendingFollowUp, setPendingFollowUp] = useState<string | undefined>(undefined);
  const [sidebarWidth, setSidebarWidth] = useState(260);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  // Load sessions and collections on mount
  useEffect(() => {
    api.get<ChatSessionSummary[]>('/api/chat/sessions').then(setSessions).catch(() => {});
    api.get<CollectionSummary[]>('/api/collections/').then(setCollections).catch(() => {});
  }, []);

  // Load session messages when URL changes
  useEffect(() => {
    if (urlSessionId) {
      setCurrentSessionId(urlSessionId);
      loadSession(urlSessionId);
    }
  }, [urlSessionId]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Sidebar resize drag
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const newWidth = Math.min(Math.max(ev.clientX, 180), 500);
      setSidebarWidth(newWidth);
    };

    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, []);

  const loadSession = async (id: string) => {
    try {
      const data = await api.get<ChatHistory>(`/api/chat/sessions/${id}`);
      setMessages(data.messages);
    } catch {
      setMessages([]);
    }
  };

  const refreshSessions = useCallback(async () => {
    try {
      const data = await api.get<ChatSessionSummary[]>('/api/chat/sessions');
      setSessions(data);
    } catch { /* silent */ }
  }, []);

  const handleSend = async (message: string) => {
    setError('');
    setSending(true);
    setPendingFollowUp(undefined);

    // Optimistic: add user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: message,
      follow_ups: [],
      referenced_collections: [],
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await api.post<ChatResponse>('/api/chat/message', {
        session_id: currentSessionId,
        message,
        model: selectedModel,
      });

      setCurrentSessionId(res.session_id);
      setMessages((prev) => [...prev, res.message]);

      // Update URL if new session
      if (!urlSessionId || urlSessionId !== res.session_id) {
        navigate(`/chat/${res.session_id}`, { replace: true });
      }

      refreshSessions();
    } catch (err) {
      const errMsg = err instanceof ApiError ? err.message : 'Failed to send message';
      setError(errMsg);
      // Remove optimistic user message on error
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
    }
  };

  const handleFollowUp = (question: string) => {
    setPendingFollowUp(question);
    // The ChatInput will pick this up via initialValue and user can edit or send
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this chat session?')) return;
    try {
      await api.del(`/api/chat/sessions/${id}`);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (currentSessionId === id) {
        setCurrentSessionId(null);
        setMessages([]);
        navigate('/chat');
      }
    } catch { /* silent */ }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setError('');
    navigate('/chat');
  };

  const handleSelectSession = (id: string) => {
    navigate(`/chat/${id}`);
  };

  return (
    <div className="chat-page">
      {/* Session sidebar */}
      <aside className="chat-sidebar" style={{ width: sidebarWidth }}>
        <button className="new-chat-btn" onClick={handleNewChat}>+ New Chat</button>
        <div className="session-list">
          {sessions.map((s) => (
            <div
              key={s.session_id}
              className={`session-item ${currentSessionId === s.session_id ? 'active' : ''}`}
              onClick={() => handleSelectSession(s.session_id)}
            >
              <span className="session-title">{s.title}</span>
              <div className="session-bottom">
                <span className="session-meta">{s.message_count} msgs</span>
                <button
                  className="session-delete-btn"
                  onClick={(e) => handleDeleteSession(s.session_id, e)}
                  title="Delete chat"
                >
                  <TrashIcon size={15} />
                </button>
              </div>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="session-empty">No conversations yet</p>
          )}
        </div>
      </aside>

      {/* Resizable split bar */}
      <div className="chat-split-bar" onMouseDown={handleDragStart} />

      {/* Main chat area */}
      <div className="chat-main">
        <div className="chat-messages">
          {messages.length === 0 && !sending && (
            <div className="chat-welcome">
              <h2>Data Lens</h2>
              <p>Ask questions about your uploaded data. Use <code>@collection_name</code> to reference specific tables.</p>
              {collections.length > 0 && (
                <div className="chat-welcome-collections">
                  <span>Available: </span>
                  {collections.map((c) => (
                    <span key={c.name} className="welcome-collection">@{c.name}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessageView
              key={i}
              message={msg}
              onFollowUp={handleFollowUp}
            />
          ))}

          {sending && (
            <div className="chat-msg chat-msg-assistant">
              <div className="chat-msg-avatar">DL</div>
              <div className="chat-msg-body">
                <div className="chat-typing">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="chat-error">{error}</div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <ChatInput
          onSend={handleSend}
          disabled={sending}
          collections={collections}
          initialValue={pendingFollowUp}
        />
      </div>
    </div>
  );
}
