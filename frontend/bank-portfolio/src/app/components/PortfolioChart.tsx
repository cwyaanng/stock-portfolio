import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface PortfolioData {
  name: string;
  value: number;
  color: string;
}

interface PortfolioChartProps {
  data: PortfolioData[];
}

const COLORS = [
  '#FFB5BA', // 파스텔 핑크
  '#B5D4FF', // 파스텔 블루
  '#B5FFB5', // 파스텔 그린
  '#FFE4B5', // 파스텔 오렌지
  '#E4B5FF', // 파스텔 퍼플
  '#B5FFF0', // 파스텔 민트
];

export function PortfolioChart({ data }: PortfolioChartProps) {
  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text 
        x={x} 
        y={y} 
        fill="white" 
        textAnchor={x > cx ? 'start' : 'end'} 
        dominantBaseline="central"
        className="text-sm font-medium"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  if (!data || data.length === 0) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-2xl">
        <p className="text-gray-500">포트폴리오를 생성해주세요</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm">
      <h3 className="mb-6 text-center text-gray-800">포트폴리오 구성</h3>
      <ResponsiveContainer width="100%" height={400}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomizedLabel}
            outerRadius={120}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value: number) => [`${value}%`, '비중']} />
          <Legend 
            wrapperStyle={{ paddingTop: '20px' }}
            formatter={(value) => <span className="text-gray-700">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}