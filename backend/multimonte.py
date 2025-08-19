# -*- coding: utf-8 -*-
# 3개 종목 조합 + 가중치 몬테카를로
# 순차 vs 멀티프로세싱 성능 비교 (Windows 호환)

# ── (Windows) SSL 인증서 경로 고정 ─────────────────────────────────────────
import os, certifi
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["CURL_CA_BUNDLE"] = certifi.where()

# ── 기본 임포트 ────────────────────────────────────────────────────────────
import numpy as np
import pandas as pd
import yfinance as yf
from itertools import combinations
from time import perf_counter
from concurrent.futures import ProcessPoolExecutor

# ── 실험용 티커 리스트 (필요시 수정) ───────────────────────────────────────
TICKERS = [
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

# ── 가격 다운로드: 조정된 Close 사용, 결측/중복 정리 ─────────────────────────
def download_prices(tickers, start, end):
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        px = raw["Close"]
    else:
        px = raw["Close"] if "Close" in raw.columns else raw.squeeze().to_frame(name=tickers[0])
    px = px.dropna(axis=1, how="all").dropna(how="any")
    px = px.loc[:, ~px.columns.duplicated()]
    cols = [t for t in tickers if t in px.columns]
    return px[cols]

# ── 배치(여러 조합) 평가: 각 조합의 최고 샤프만 추림(벡터화) ───────────────
def _eval_batch(idx_batch, mu, cov, rf_annual, n_weights, seed):
    rng = np.random.default_rng(seed)
    B = len(idx_batch)
    idx = np.array(idx_batch, dtype=int)                     # (B,3)
    mu3  = mu[idx]                                           # (B,3)
    cov3 = cov[idx[:,:,None], idx[:,None,:]]                 # (B,3,3)
    W = rng.dirichlet(np.ones(3), size=(B, n_weights))       # (B,K,3)

    R   = (W * mu3[:, None, :]).sum(axis=2)                  # (B,K)
    V   = np.einsum('bki,bij,bkj->bk', W, cov3, W)           # (B,K)
    vol = np.sqrt(np.maximum(V, 1e-12))                      # (B,K)
    sharpe = (R - rf_annual) / vol                           # (B,K)

    kbest = sharpe.argmax(axis=1)                            # (B,)
    rows  = np.arange(B)
    bestS = sharpe[rows, kbest]
    bestR = R[rows, kbest]
    bestV = vol[rows, kbest]
    bestW = W[rows, kbest, :]

    # 배치 내 상위 5개만 반환 → IPC 비용 절감
    topk = 5 if B >= 5 else B
    top_idx = np.argpartition(bestS, -topk)[-topk:]
    top_idx = top_idx[np.argsort(-bestS[top_idx])]

    out = []
    for bi in top_idx:
        i,j,k = idx[bi].tolist()
        out.append((
            float(bestS[bi]), float(bestR[bi]), float(bestV[bi]),
            (i,j,k), bestW[bi].tolist()
        ))
    return out

# ── 순차 실행 ──────────────────────────────────────────────────────────────
def evaluate_seq(prices, rf_annual=0.015, n_weights=2000,
                 batch_combos=2000, topn=20, max_combos=20000, random_sample=True, seed=42):
    TRADING_DAYS = 252
    rets = prices.pct_change().dropna()
    mu  = (rets.mean() * TRADING_DAYS).values
    cov = (rets.cov()   * TRADING_DAYS).values
    tickers = prices.columns.tolist()
    A = len(tickers)

    combos_all = list(combinations(range(A), 3))
    total = len(combos_all)

    rng = np.random.default_rng(seed)
    if max_combos is not None and max_combos < total:
        if random_sample:
            pick = rng.choice(total, size=max_combos, replace=False)
            combos = [combos_all[i] for i in sorted(pick)]
        else:
            combos = combos_all[:max_combos]
    else:
        combos = combos_all

    results = []
    for b_id, s in enumerate(range(0, len(combos), batch_combos)):
        batch = combos[s:s+batch_combos]
        seed_b = seed + b_id
        results.extend(_eval_batch(batch, mu, cov, rf_annual, n_weights, seed_b))

    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:topn]

    nice = []
    for sharpe, ret, vol, (i,j,k), w in results:
        nice.append({
            "tickers": [tickers[i], tickers[j], tickers[k]],
            "weights": [float(w[0]), float(w[1]), float(w[2])],
            "best_sharpe": float(sharpe),
            "best_return": float(ret),
            "best_risk": float(vol),
        })
    return nice

# ── (중요) 멀티프로세싱: 워커 전역/초기화 함수 (모듈 최상위에 있어야 피클링 가능) ──
_G_MU = None
_G_COV = None
_G_RF = 0.0
_G_NW = 0

def _init_worker_globals(mu, cov, rf_annual, n_weights):
    # 워커에서 BLAS 과다 스레딩 방지
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"
    global _G_MU, _G_COV, _G_RF, _G_NW
    _G_MU = mu
    _G_COV = cov
    _G_RF = rf_annual
    _G_NW = n_weights

def _worker_eval_batch(args):
    batch, seed_b = args
    # 전역으로 세팅된 파라미터 사용
    return _eval_batch(batch, _G_MU, _G_COV, _G_RF, _G_NW, seed_b)

# ── 멀티프로세싱 실행 ──────────────────────────────────────────────────────
def evaluate_mp(prices, rf_annual=0.015, n_weights=2000,
                batch_combos=2000, topn=20, max_combos=20000, random_sample=True,
                seed=42, workers=None):
    # 부모 프로세스에서도 BLAS 스레드 제한(중첩 스레딩 방지)
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    TRADING_DAYS = 252
    rets = prices.pct_change().dropna()
    mu  = (rets.mean() * TRADING_DAYS).values
    cov = (rets.cov()   * TRADING_DAYS).values
    tickers = prices.columns.tolist()
    A = len(tickers)

    combos_all = list(combinations(range(A), 3))
    total = len(combos_all)

    rng = np.random.default_rng(seed)
    if max_combos is not None and max_combos < total:
        if random_sample:
            pick = rng.choice(total, size=max_combos, replace=False)
            combos = [combos_all[i] for i in sorted(pick)]
        else:
            combos = combos_all[:max_combos]
    else:
        combos = combos_all

    batches = []
    for b_id, s in enumerate(range(0, len(combos), batch_combos)):
        batch = combos[s:s+batch_combos]
        seed_b = seed + b_id
        batches.append((batch, seed_b))

    if workers is None:
        workers = max(1, os.cpu_count() // 2)

    results = []
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker_globals,
        initargs=(mu, cov, rf_annual, n_weights)
    ) as pool:
        for part in pool.map(_worker_eval_batch, batches, chunksize=1):
            results.extend(part)

    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:topn]

    nice = []
    for sharpe, ret, vol, (i,j,k), w in results:
        nice.append({
            "tickers": [tickers[i], tickers[j], tickers[k]],
            "weights": [float(w[0]), float(w[1]), float(w[2])],
            "best_sharpe": float(sharpe),
            "best_return": float(ret),
            "best_risk": float(vol),
        })
    return nice

# ── 메인: 데이터 다운 → 순차/병렬 비교 ─────────────────────────────────────
if __name__ == "__main__":
    start_date = "2024-01-01"
    end_date   = "2025-01-01"
    print(f"[티커 수] {len(TICKERS)}개")

    t0 = perf_counter()
    prices = download_prices(TICKERS, start_date, end_date)
    t1 = perf_counter()
    print(f"[다운로드] {prices.shape[1]}개 티커, {prices.shape[0]}개 일자  (소요 {t1 - t0:.2f}s)")

    RF = 0.015
    N_WEIGHTS  = 2000      # 조합당 가중치 샘플 수 (정밀↑ 시간↑)
    MAX_COMBOS = 100000     # 전체 조합 중 무작위 N개만 평가 (None이면 전수)
    BATCH      = 4000      # 배치당 조합 개수
    TOPN       = 15
    SEED       = 42

    # 순차
    t2 = perf_counter()
    top_seq = evaluate_seq(prices, rf_annual=RF, n_weights=N_WEIGHTS,
                           batch_combos=BATCH, topn=TOPN,
                           max_combos=MAX_COMBOS, random_sample=True, seed=SEED)
    t3 = perf_counter()

    # 멀티프로세싱
    t4 = perf_counter()
    top_mp  = evaluate_mp(prices, rf_annual=RF, n_weights=N_WEIGHTS,
                          batch_combos=BATCH, topn=TOPN,
                          max_combos=MAX_COMBOS, random_sample=True,
                          seed=SEED, workers=max(1, os.cpu_count()//2))
    t5 = perf_counter()

    print("\n[성능 비교]")
    print(f"- 순차 시간: {t3 - t2:.3f}s")
    print(f"- 병렬 시간: {t5 - t4:.3f}s")
    print(f"- Speedup   : x{(t3 - t2)/(t5 - t4 + 1e-12):.2f}")

    def show_top(title, rows):
        print(f"\n[{title} TOP {len(rows)}]")
        for i, r in enumerate(rows, 1):
            ts = ", ".join(r["tickers"])
            ws = ", ".join(f"{w:.2%}" for w in r["weights"])
            print(f"{i:2d}) {ts} | w=({ws}) | Sharpe={r['best_sharpe']:.3f}  "
                  f"Return={r['best_return']:.2%}  Risk={r['best_risk']:.2%}")

    show_top("순차", top_seq)
    show_top("병렬", top_mp)
