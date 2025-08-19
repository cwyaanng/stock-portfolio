from datetime import date, timedelta
from rest_framework.decorators import api_view , renderer_classes
from rest_framework.response import Response
from .utils import download_prices, evaluate_gpu_by_score , get_optimal_portfolio
import os
from rest_framework.renderers import JSONRenderer
from .universe import NASDAQ100
from datetime import date
from dateutil.relativedelta import relativedelta

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
  
@api_view(["GET"])
def nasdaq100_topk_preview(request):
    k = int(request.GET.get("k") or 3)
    rp = request.GET.get("risk_profile") or "balanced"
    start = request.GET.get("start") or "2024-01-01"
    end   = request.GET.get("end")   or "2025-01-01"

    # 
    prices = download_prices(NASDAQ100, start, end)

    rows = evaluate_gpu_by_score(
        prices,
        k=k,
        risk_profile=rp,
        n_weights=800,          # 프리뷰: 작게
        batch_combos=20_000,    # VRAM 맞춰 조절
        topn=1,                 # 프리뷰는 1개만
    )
    return Response({"k": k, "risk_profile": rp, "period": [start, end], "results": rows})
  

@api_view(["GET"])
@renderer_classes([JSONRenderer])
def nasdaq100_portfolio(request):
    try:
        k = int(request.GET.get("k", "3"))
        risk = request.GET.get("risk_profile", "balanced").lower()
        start = request.GET.get("start") or (date.today() - relativedelta(years=1)).strftime("%Y-%m-%d")
        end   = request.GET.get("end") or date.today().strftime("%Y-%m-%d")
        topn  = int(request.GET.get("topn", "1"))
        if k < 2:
            return HttpResponseBadRequest("k must be >= 2")

        rows = get_optimal_portfolio(
            k=k,
            risk_profile=risk,
            start=start,
            end=end,
            topn=topn
        )
        return Response({
            "k": k,
            "risk_profile": risk,
            "period": [start, end],
            "results": rows
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=500)