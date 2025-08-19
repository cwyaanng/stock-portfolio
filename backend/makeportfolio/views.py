from datetime import date, timedelta
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .utils import download_prices, evaluate_mp_by_score
import os

@api_view(["POST"])
def run_montecarlo(request):
    data = request.data

    prices = download_prices(
        data.get("tickers"),
        data.get("start_date"),
        data.get("end_date")
    )

    results = evaluate_mp_by_score(
        prices,
        rf_annual=data.get("rf", 0.015),
        n_weights=data.get("n_weights", 2000),
        batch_combos=data.get("batch", 2000),
        topn=data.get("topn", 5),
        random_sample=True,
        seed=data.get("seed", 42)
    )

    return Response(results)

# 고정 혹은 환경변수/DB에서 받아도 됨
NASDAQ100 = [
    "NVDA","MSFT","AAPL","GOOG","GOOGL","AMZN","META","AVGO","TSLA","NFLX",
    "COST","PLTR","ASML","AMD","TMUS","CSCO","AZN","LIN","PEP","INTU",
    "SHOP","TXN","BKNG","ISRG","QCOM","PDD","AMGN","ADBE","APP","ARM",
    "GILD","HON","MU","AMAT","LRCX","CMCSA","ADP","MELI","PANW","KLAC",
    "ADI","SNPS","INTC","CRWD","DASH","MSTR","SBUX","VRTX","CEG","CDNS",
    "CTAS","ORLY","MDLZ","TRI","ABNB","MAR","CSX","PYPL","MRVL","MNST",
    "REGN","ADSK","FTNT","WDAY","AEP","AXON","NXPI","ROP","FAST","IDXX",
    "PCAR","PAYX","ROST","KDP","CPRT","EXC","DDOG","TEAM","EA","TTWO",
    "ZS","XEL","BKR","CCEP","FANG","CSGP","VRSK","CHTR","MCHP","CTSH",
    "GEHC","KHC","ODFL","DXCM","WBD","TTD","LULU","CDW","ON","BIIB","GFS"
]

@api_view(["GET"])
def top3_nasdaq100(request):
    """
    GET /api/nasdaq100/top3/?start=2024-01-01&end=2025-01-01&topn=15&max_combos=80000&n_weights=2000
    """
    start = request.GET.get("start") or (date.today().replace(day=1) - timedelta(days=365)).isoformat()
    end   = request.GET.get("end")   or date.today().isoformat()
    topn  = int(request.GET.get("topn") or 15)
    n_weights  = int(request.GET.get("n_weights") or 2000)
    batch      = int(request.GET.get("batch") or 4000)
   

    # 1) 가격(캐시) 로드
    prices = download_prices(NASDAQ100, start, end)

    # 2) 병렬 탐색
    results = evaluate_mp_by_score(
        prices,
        rf_annual=0.015,
        n_weights=n_weights,
        batch_combos=batch,
        topn=topn
    )
    return Response({"universe": "NASDAQ-100", "period": [start, end], "results": results})