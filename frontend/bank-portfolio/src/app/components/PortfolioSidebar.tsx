"use client"
import { useState } from 'react';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Checkbox } from './ui/checkbox';
import { Separator } from './ui/separator';
import { TrendingUp, Sparkles, BarChart3 } from 'lucide-react';

interface Stock {
  symbol: string;
  name: string;
  sector: string;
}

interface PortfolioSidebarProps {
  onGeneratePortfolio: (selectedStocks: Stock[]) => void;
  onTodayRecommendation: () => void;
}

const AVAILABLE_STOCKS: Stock[] = [
  { symbol: 'AAPL', name: '애플', sector: '기술' },
  { symbol: 'MSFT', name: '마이크로소프트', sector: '기술' },
  { symbol: 'GOOGL', name: '구글', sector: '기술' },
  { symbol: 'TSLA', name: '테슬라', sector: '자동차' },
  { symbol: 'AMZN', name: '아마존', sector: '소비재' },
  { symbol: 'NVDA', name: '엔비디아', sector: '기술' },
  { symbol: 'JPM', name: 'JP모건', sector: '금융' },
  { symbol: 'JNJ', name: '존슨앤존슨', sector: '헬스케어' },
  { symbol: 'PG', name: 'P&G', sector: '소비재' },
  { symbol: 'UNH', name: '유나이티드헬스', sector: '헬스케어' }
];

export function PortfolioSidebar({ onGeneratePortfolio, onTodayRecommendation }: PortfolioSidebarProps) {
  const [selectedStocks, setSelectedStocks] = useState<Stock[]>([]);

  const handleStockToggle = (stock: Stock) => {
    setSelectedStocks(prev => {
      const isSelected = prev.find(s => s.symbol === stock.symbol);
      if (isSelected) {
        return prev.filter(s => s.symbol !== stock.symbol);
      } else {
        return [...prev, stock];
      }
    });
  };

  const handleGeneratePortfolio = () => {
    if (selectedStocks.length > 0) {
      onGeneratePortfolio(selectedStocks);
    }
  };

  return (
    <div className="w-80 bg-gradient-to-b from-gray-50 to-white border-r border-gray-100 p-6 overflow-y-auto">
      {/* 오늘의 포트폴리오 추천 - 강조 */}
      <Button 
        onClick={onTodayRecommendation}
        className="w-full mb-8 h-14 bg-gradient-to-r from-blue-400 to-purple-400 hover:from-blue-500 hover:to-purple-500 text-white rounded-xl shadow-md hover:shadow-lg transition-all duration-200"
      >
        <Sparkles className="mr-3 h-5 w-5" />
        오늘의 포트폴리오 추천
      </Button>

      <Separator className="mb-6" />

      {/* 종목 선택 섹션 */}
      <Card className="p-4 mb-6 bg-white/70 backdrop-blur-sm border-gray-100 shadow-sm">
        <div className="flex items-center mb-4">
          <BarChart3 className="mr-2 h-5 w-5 text-gray-600" />
          <h3 className="text-gray-800">종목 선택</h3>
        </div>
        
        <div className="space-y-3 max-h-64 overflow-y-auto">
          {AVAILABLE_STOCKS.map((stock) => (
            <div key={stock.symbol} className="flex items-center space-x-3 p-2 rounded-lg hover:bg-gray-50 transition-colors">
              <Checkbox
                id={stock.symbol}
                checked={selectedStocks.some(s => s.symbol === stock.symbol)}
                onCheckedChange={() => handleStockToggle(stock)}
                className="data-[state=checked]:bg-blue-400 data-[state=checked]:border-blue-400"
              />
              <div className="flex-1 min-w-0">
                <label htmlFor={stock.symbol} className="cursor-pointer">
                  <div className="text-sm text-gray-900 truncate">{stock.name}</div>
                  <div className="text-xs text-gray-500">{stock.symbol} • {stock.sector}</div>
                </label>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* 선택된 종목 수 표시 */}
      {selectedStocks.length > 0 && (
        <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <p className="text-sm text-blue-700">
            {selectedStocks.length}개 종목이 선택되었습니다
          </p>
        </div>
      )}

      {/* 포트폴리오 생성 버튼 */}
      <Button 
        onClick={handleGeneratePortfolio}
        disabled={selectedStocks.length === 0}
        className="w-full h-12 bg-gradient-to-r from-green-400 to-blue-400 hover:from-green-500 hover:to-blue-500 disabled:from-gray-300 disabled:to-gray-300 text-white rounded-xl shadow-sm hover:shadow-md transition-all duration-200"
      >
        <TrendingUp className="mr-2 h-4 w-4" />
        포트폴리오 생성
      </Button>
    </div>
  );
}