"use client"
import { useState } from 'react';
import { PortfolioSidebar } from './components/PortfolioSidebar';
import { PortfolioChart } from './components/PortfolioChart';
import { Card } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { CalendarDays, TrendingUp } from 'lucide-react';

interface Stock {
  symbol: string;
  name: string;
  sector: string;
}

interface PortfolioData {
  name: string;
  value: number;
  color: string;
}

/**
 * generatePortfolioWeights
 * Input: stocks (Stock[])
 * Output: PortfolioData[]
 * 
 * 설명: 종목 배열을 입력받아 랜덤 가중치로 포트폴리오를 생성 (Mock)
 */
const generatePortfolioWeights = (stocks: Stock[]): PortfolioData[] => {
  // 실제로는 Django API로 요청을 보냄
  const colors = ['#FFB5BA', '#B5D4FF', '#B5FFB5', '#FFE4B5', '#E4B5FF', '#B5FFF0'];
  
  // 랜덤 가중치 생성 (실제로는 AI 알고리즘 결과)
  const weights = stocks.map(() => Math.random());
  const totalWeight = weights.reduce((sum, w) => sum + w, 0);
  
  return stocks.map((stock, index) => ({
    name: stock.name,
    value: Math.round((weights[index] / totalWeight) * 100),
    color: colors[index % colors.length]
  }));
};

/**
 * getTodayRecommendation
 * Input: 없음
 * Output: PortfolioData[]
 * 
 * 설명: 오늘의 추천 포트폴리오를 고정된 더미 데이터로 반환
 */
const getTodayRecommendation = (): PortfolioData[] => {
  // 오늘의 추천 포트폴리오 (Mock 데이터)
  return [
    { name: '애플', value: 25, color: '#FFB5BA' },
    { name: '마이크로소프트', value: 20, color: '#B5D4FF' },
    { name: '엔비디아', value: 18, color: '#B5FFB5' },
    { name: '테슬라', value: 15, color: '#FFE4B5' },
    { name: '아마존', value: 12, color: '#E4B5FF' },
    { name: 'JP모건', value: 10, color: '#B5FFF0' }
  ];
};

export default function App() {
  const [portfolioData, setPortfolioData] = useState<PortfolioData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [portfolioType, setPortfolioType] = useState<'custom' | 'recommendation'>('custom');

  
  /**
   * handleGeneratePortfolio
   * Input: selectedStocks (Stock[])
   * Output: void (상태 업데이트)
   * 
   * 설명: 선택한 종목을 기반으로 포트폴리오를 생성하는 핸들러
   *       - 실제로는 Django API 호출 예정
   */
  const handleGeneratePortfolio = async (selectedStocks: Stock[]) => {
    setIsLoading(true);
    setPortfolioType('custom');
    
    try {
      // 실제로는 Django API 호출:
      // const response = await fetch('/api/generate-portfolio', {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify({ stocks: selectedStocks })
      // });
      // const data = await response.json();
      
      // Mock 지연시간
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      const data = generatePortfolioWeights(selectedStocks);
      setPortfolioData(data);
      setLastUpdated(new Date().toLocaleString('ko-KR'));
    } catch (error) {
      console.error('포트폴리오 생성 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * handleTodayRecommendation
   * Input: 없음
   * Output: void (상태 업데이트)
   * 
   * 설명: 오늘의 추천 포트폴리오를 불러오는 핸들러
   */
  const handleTodayRecommendation = async () => {
    setIsLoading(true);
    setPortfolioType('recommendation');
    
    try {
      // Mock 지연시간
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      //API 요청으로 변경 
      const data = getTodayRecommendation();


      //name,value 를 받아오고 color는 frontend에서 할당 

      setPortfolioData(data);
      setLastUpdated(new Date().toLocaleString('ko-KR'));
    } catch (error) {
      console.error('추천 포트폴리오 로드 실패:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50/30">
      <div className="flex h-screen">
        {/* 사이드바 */}
        <PortfolioSidebar 
          onGeneratePortfolio={handleGeneratePortfolio}
          onTodayRecommendation={handleTodayRecommendation}
        />
        
        {/* 메인 콘텐츠 */}
        <div className="flex-1 p-8 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            {/* 헤더 */}
            <div className="mb-8">
              <h1 className="mb-2 text-gray-900">포트폴리오 추천 시스템</h1>
              <p className="text-gray-600">AI 기반 맞춤형 투자 포트폴리오를 생성해보세요</p>
            </div>

            {/* 상태 카드 */}
            {lastUpdated && (
              <Card className="p-4 mb-6 bg-white/80 backdrop-blur-sm border-gray-100 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-green-100 rounded-lg">
                      <TrendingUp className="h-4 w-4 text-green-600" />
                    </div>
                    <div>
                      <p className="text-sm text-gray-900">
                        {portfolioType === 'recommendation' ? '오늘의 추천 포트폴리오' : '맞춤 포트폴리오'}가 생성되었습니다
                      </p>
                      <div className="flex items-center space-x-2 mt-1">
                        <CalendarDays className="h-3 w-3 text-gray-400" />
                        <p className="text-xs text-gray-500">마지막 업데이트: {lastUpdated}</p>
                      </div>
                    </div>
                  </div>
                  <Badge variant="secondary" className="bg-green-100 text-green-700 border-green-200">
                    {portfolioType === 'recommendation' ? '추천' : '맞춤'}
                  </Badge>
                </div>
              </Card>
            )}

            {/* 포트폴리오 차트 */}
            {isLoading ? (
              <Card className="p-8 bg-white/80 backdrop-blur-sm border-gray-100 shadow-sm">
                <div className="flex flex-col items-center justify-center h-96 space-y-4">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400"></div>
                  <p className="text-gray-600">포트폴리오를 생성하고 있습니다...</p>
                </div>
              </Card>
            ) : (
              <PortfolioChart data={portfolioData} />
            )}

            {/* 안내 메시지 */}
            {!isLoading && portfolioData.length === 0 && (
              <Card className="p-8 bg-white/60 backdrop-blur-sm border-gray-100 shadow-sm">
                <div className="text-center space-y-4">
                  <div className="p-4 bg-blue-50 rounded-full w-16 h-16 mx-auto flex items-center justify-center">
                    <TrendingUp className="h-8 w-8 text-blue-500" />
                  </div>
                  <h3 className="text-gray-900">포트폴리오를 시작해보세요</h3>
                  <p className="text-gray-600 max-w-md mx-auto">
                    왼쪽에서 "오늘의 포트폴리오 추천"을 클릭하거나, 원하는 종목을 선택하여 맞춤 포트폴리오를 생성해보세요.
                  </p>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}