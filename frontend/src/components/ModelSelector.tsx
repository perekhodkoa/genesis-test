import { useModel } from '../hooks/useModel';
import './ModelSelector.css';

export default function ModelSelector() {
  const { models, selectedModel, setSelectedModel, loading } = useModel();

  if (loading || models.length === 0) return null;

  return (
    <select
      className="model-selector"
      value={selectedModel}
      onChange={(e) => setSelectedModel(e.target.value)}
    >
      {models.map((m) => (
        <option key={m.id} value={m.id}>
          {m.name}
        </option>
      ))}
    </select>
  );
}
