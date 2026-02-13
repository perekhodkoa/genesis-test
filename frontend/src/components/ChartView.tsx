import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
  LineChart, Line,
} from 'recharts';
import type { VisualizationData } from '../api/types';
import './ChartView.css';

const COLORS = [
  'var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)',
  'var(--chart-5)', 'var(--chart-6)', 'var(--chart-7)', 'var(--chart-8)',
];

// Resolve CSS custom property values for Recharts (which needs actual color strings)
function resolveCssColor(cssVar: string): string {
  const match = cssVar.match(/var\(--(.+)\)/);
  if (!match) return cssVar;
  return getComputedStyle(document.documentElement).getPropertyValue(`--${match[1]}`).trim() || cssVar;
}

interface Props {
  data: VisualizationData;
}

export default function ChartView({ data }: Props) {
  const { chart_type, title, labels, datasets } = data;

  if (!labels.length || !datasets.length) return null;

  const resolvedColors = COLORS.map(resolveCssColor);

  if (chart_type === 'pie') {
    const pieData = labels.map((label, i) => ({
      name: label,
      value: datasets[0]?.data[i] ?? 0,
    }));

    return (
      <div className="chart-container">
        {title && <h4 className="chart-title">{title}</h4>}
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              outerRadius={100}
              innerRadius={40}
              dataKey="value"
              label={({ name, percent }) =>
                `${name.length > 12 ? name.slice(0, 12) + '...' : name} ${(percent * 100).toFixed(0)}%`
              }
              labelLine={{ strokeWidth: 1 }}
            >
              {pieData.map((_, i) => (
                <Cell key={i} fill={resolvedColors[i % resolvedColors.length]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#1a1d27', border: '1px solid #363a48', borderRadius: 8 }}
              itemStyle={{ color: '#e4e6ed' }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Transform data for bar/line charts
  const chartData = labels.map((label, i) => {
    const point: Record<string, unknown> = { name: label };
    datasets.forEach((ds) => {
      point[ds.label] = ds.data[i] ?? 0;
    });
    return point;
  });

  if (chart_type === 'bar') {
    return (
      <div className="chart-container">
        {title && <h4 className="chart-title">{title}</h4>}
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 40, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#363a48" />
            <XAxis
              dataKey="name"
              tick={{ fill: '#9499a8', fontSize: 11 }}
              angle={labels.some((l) => l.length > 8) ? -35 : 0}
              textAnchor={labels.some((l) => l.length > 8) ? 'end' : 'middle'}
              height={60}
              interval={0}
              tickFormatter={(v: string) => v.length > 15 ? v.slice(0, 15) + '...' : v}
            />
            <YAxis tick={{ fill: '#9499a8', fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: '#1a1d27', border: '1px solid #363a48', borderRadius: 8 }}
              itemStyle={{ color: '#e4e6ed' }}
            />
            {datasets.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
            {datasets.map((ds, i) => (
              <Bar key={ds.label} dataKey={ds.label} fill={resolvedColors[i % resolvedColors.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart_type === 'line') {
    return (
      <div className="chart-container">
        {title && <h4 className="chart-title">{title}</h4>}
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 40, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#363a48" />
            <XAxis
              dataKey="name"
              tick={{ fill: '#9499a8', fontSize: 11 }}
              angle={labels.some((l) => l.length > 8) ? -35 : 0}
              textAnchor={labels.some((l) => l.length > 8) ? 'end' : 'middle'}
              height={60}
              interval={0}
              tickFormatter={(v: string) => v.length > 15 ? v.slice(0, 15) + '...' : v}
            />
            <YAxis tick={{ fill: '#9499a8', fontSize: 11 }} />
            <Tooltip
              contentStyle={{ background: '#1a1d27', border: '1px solid #363a48', borderRadius: 8 }}
              itemStyle={{ color: '#e4e6ed' }}
            />
            {datasets.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
            {datasets.map((ds, i) => (
              <Line
                key={ds.label}
                type="monotone"
                dataKey={ds.label}
                stroke={resolvedColors[i % resolvedColors.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}
