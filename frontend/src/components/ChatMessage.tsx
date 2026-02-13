import type { ChatMessage as ChatMessageType } from '../api/types';
import ChartView from './ChartView';
import './ChatMessage.css';

interface Props {
  message: ChatMessageType;
  onFollowUp?: (question: string) => void;
}

export default function ChatMessageView({ message, onFollowUp }: Props) {
  const isUser = message.role === 'user';

  return (
    <div className={`chat-msg ${isUser ? 'chat-msg-user' : 'chat-msg-assistant'}`}>
      <div className="chat-msg-avatar">{isUser ? 'You' : 'DL'}</div>
      <div className="chat-msg-body">
        <div className="chat-msg-content">{message.content}</div>

        {message.query && (
          <div className="chat-msg-query">
            <div className="query-header">
              <span className="query-type">{message.query_type === 'sql' ? 'SQL' : 'MongoDB'} Query</span>
            </div>
            <pre className="query-code"><code>{message.query}</code></pre>
          </div>
        )}

        {message.visualization && (
          <ChartView data={message.visualization} />
        )}

        {message.follow_ups.length > 0 && !isUser && (
          <div className="chat-msg-followups">
            {message.follow_ups.map((q, i) => (
              <button
                key={i}
                className="followup-bubble"
                onClick={() => onFollowUp?.(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
