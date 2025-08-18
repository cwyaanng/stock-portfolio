import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# 종목 리스트 및 기간 설정
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']  # 관심 종목 리스트
start_date = '2021-01-01'
end_date = '2022-01-01'

# 주가 데이터 가져오기
data = yf.download(tickers, start=start_date, end=end_date)['Adj Close']

# 일간 수익률 계산
returns = data.pct_change().dropna()

# 자산 수, 기대 수익률, 공분산 행렬 계산
num_assets = len(tickers)
mean_returns = returns.mean()
cov_matrix = returns.cov()

# 시뮬레이션 파라미터 설정
num_portfolios = 20000
results = np.zeros((3, num_portfolios))

# 포트폴리오 무작위 시뮬레이션
for i in range(num_portfolios):
    weights = np.random.random(num_assets)
    weights /= np.sum(weights)  # 합이 1이 되도록 정규화

    portfolio_return = np.sum(weights * mean_returns) * 252
    portfolio_stddev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * 252, weights)))

    # 포트폴리오 수익률, 리스크(표준편차), 샤프 비율 저장
    results[0, i] = portfolio_stddev
    results[1, i] = portfolio_return
    results[2, i] = portfolio_return / portfolio_stddev  # Sharpe Ratio

# 결과를 데이터프레임으로 정리
portfolios = pd.DataFrame(results.T, columns=['Risk', 'Return', 'Sharpe Ratio'])

# 효율적 투자선 시각화
plt.scatter(portfolios['Risk'], portfolios['Return'], c=portfolios['Sharpe Ratio'], cmap='viridis')
plt.colorbar(label='Sharpe Ratio')
plt.xlabel('Risk')
plt.ylabel('Return')
plt.title('Efficient Frontier')
plt.show()
