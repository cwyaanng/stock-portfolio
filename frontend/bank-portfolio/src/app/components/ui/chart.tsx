// PortfolioChart.tsx
'use client';

import { JSX } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend as RechartsLegend,
  Tooltip,
  type LegendProps,
} from 'recharts';

interface PortfolioData {
  name: string;
  value: number; // 비중(%)
  color?: string;
}

interface PortfolioChartProps {
  data: PortfolioData[];
}

const COLORS = ['#FFB5BA','#B5D4FF','#B5FFB5','#FFE4B5','#E4B5FF','#B5FFF0'];

/** Legend payload 아이템 형태 */
interface LegendPayloadItem {
  value: string;
  color: string;
  [key: string]: any;
}

/** Legend 커스텀용 props (payload 포함) */
interface CustomLegendProps extends LegendProps {
  payload?: LegendPayloadItem[];
}

function PrettyLegend({ payload = [] }: CustomLegendProps): JSX.Element | null {
  if (!payload.length) return null;

  return (
    <ul className="flex flex-wrap justify-center gap-3 mt-6">
      {payload.map((entry, idx) => (
        <li
          key={`legend-item-${idx}`}
          className="flex items-center gap-2 px-3 py-1 rounded-full bg-gray-50 shadow-sm"
          title={String(entry.value)}
        >
          <span
            className="inline-block w-3 h-3 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-sm text-gray-700 font-medium">{String(entry.value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Pie 라벨 콜백이 받는 props는 전부 optional 이라고 보고 안전하게 처리 */
type MyPieLabelProps = {
  cx?: number;
  cy?: number;
  midAngle?: number;
  innerRadius?: number;
  outerRadius?: number;
  percent?: number;
};

export function PortfolioChart({ data }: PortfolioChartProps) {
  const renderCustomizedLabel = (p: MyPieLabelProps): React.ReactNode => {
    // ✅ undefined 대비 기본값 지정
    const cx = p.cx ?? 0;
    const cy = p.cy ?? 0;
    const midAngle = p.midAngle ?? 0;
    const innerRadius = p.innerRadius ?? 0;
    const outerRadius = p.outerRadius ?? 0;
    const percent = p.percent ?? 0;

    const RAD = Math.PI / 180;
    const r = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + r * Math.cos(-midAngle * RAD);
    const y = cy + r * Math.sin(-midAngle * RAD);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        className="text-sm font-medium"
      >
        {(percent * 100).toFixed(0)}%
      </text>
    );
  };

  if (!data?.length) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-2xl">
        <p className="text-gray-500">포트폴리오를 생성해주세요</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm">
      <h3 className="mb-2 text-center text-lg font-semibold text-gray-800">포트폴리오 구성</h3>
      <p className="mb-6 text-center text-sm text-gray-500">자산 비중(%) 기준</p>

      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomizedLabel}  
            outerRadius={120}
            dataKey="value"
            nameKey="name"
          >
            {data.map((e, i) => (
              <Cell
                key={`${e.name}-${i}`}
                fill={e.color ?? COLORS[i % COLORS.length]}
                stroke="white"
                strokeWidth={2}
              />
            ))}
          </Pie>

          <Tooltip
            formatter={(v: number, _n: string, item: any) => [`${Number(v)}%`, item?.payload?.name ?? '비중']}
          />

          <RechartsLegend content={(props) => <PrettyLegend {...(props as CustomLegendProps)} />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
