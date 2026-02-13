import { useState, useRef, useEffect, type KeyboardEvent, type FormEvent } from 'react';
import type { CollectionSummary } from '../api/types';
import './ChatInput.css';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
  collections: CollectionSummary[];
  initialValue?: string;
}

export default function ChatInput({ onSend, disabled, collections, initialValue }: Props) {
  const [value, setValue] = useState(initialValue ?? '');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (initialValue !== undefined) {
      setValue(initialValue);
      // Focus and put cursor at end
      setTimeout(() => {
        const el = inputRef.current;
        if (el) {
          el.focus();
          el.setSelectionRange(el.value.length, el.value.length);
        }
      }, 0);
    }
  }, [initialValue]);

  const filteredCollections = collections.filter((c) =>
    c.name.toLowerCase().includes(mentionFilter.toLowerCase())
  );

  const handleChange = (text: string) => {
    setValue(text);

    // Detect @ mention trigger
    const cursor = inputRef.current?.selectionStart ?? text.length;
    const beforeCursor = text.slice(0, cursor);
    const atMatch = beforeCursor.match(/@(\w*)$/);

    if (atMatch) {
      setShowMentions(true);
      setMentionFilter(atMatch[1]);
      setMentionIndex(0);
    } else {
      setShowMentions(false);
    }
  };

  const insertMention = (name: string) => {
    const cursor = inputRef.current?.selectionStart ?? value.length;
    const beforeCursor = value.slice(0, cursor);
    const afterCursor = value.slice(cursor);
    const atPos = beforeCursor.lastIndexOf('@');

    const newValue = beforeCursor.slice(0, atPos) + `@${name} ` + afterCursor;
    setValue(newValue);
    setShowMentions(false);

    setTimeout(() => {
      const newCursor = atPos + name.length + 2;
      inputRef.current?.setSelectionRange(newCursor, newCursor);
      inputRef.current?.focus();
    }, 0);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (showMentions && filteredCollections.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex((i) => Math.min(i + 1, filteredCollections.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === 'Tab' || e.key === 'Enter') {
        e.preventDefault();
        insertMention(filteredCollections[mentionIndex].name);
        return;
      }
      if (e.key === 'Escape') {
        setShowMentions(false);
        return;
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = (e?: FormEvent) => {
    e?.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
    setShowMentions(false);
  };

  return (
    <form className="chat-input-form" onSubmit={handleSubmit}>
      <div className="chat-input-wrap">
        {showMentions && filteredCollections.length > 0 && (
          <div className="mention-dropdown">
            {filteredCollections.slice(0, 8).map((col, i) => (
              <button
                key={col.name}
                type="button"
                className={`mention-item ${i === mentionIndex ? 'active' : ''}`}
                onMouseDown={(e) => { e.preventDefault(); insertMention(col.name); }}
              >
                <span className="mention-name">@{col.name}</span>
                <span className={`mention-db ${col.db_type}`}>
                  {col.db_type === 'postgres' ? 'PG' : 'Mongo'}
                </span>
                <span className="mention-info">{col.row_count} rows</span>
              </button>
            ))}
          </div>
        )}

        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Ask about your data... Use @collection to reference tables"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = 'auto';
            target.style.height = Math.min(target.scrollHeight, 150) + 'px';
          }}
        />
        <button type="submit" className="chat-send-btn" disabled={disabled || !value.trim()}>
          Send
        </button>
      </div>
    </form>
  );
}
