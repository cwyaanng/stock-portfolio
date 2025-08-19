# portfolio/utils.py
# -*- coding: utf-8 -*-
"""
Monte Carlo 기반 3종목 조합 최적화 유틸리티 (순차/멀티프로세싱 지원)

- download_prices: 야후 파이낸스에서 조정종가 다운로드
- evaluate_seq    : 순차 실행으로 최적 Sharpe 조합 탐색
- evaluate_mp     : 멀티프로세싱으로 병렬 탐색 (API로 감싸 사용 권장)

주의사항
- Windows 환경에서 SSL 인증서 문제를 피하기 위해 certifi 경로를 환경변수에 지정.
- Django 뷰에서 호출 시, 긴 작업은 요청 타임아웃/워커 수를 고려하세요.
"""

from __future__ import annotations

import os
import certifi
from typing import Iterable, List, Sequence, Tuple, Dict, Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from itertools import combinations
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta

# ── 공개 API ────────────────────────────────────────────────────────────────
__all__ = [
    "download_prices",
    "evaluate_mp",
]

# ── 내부 전역 (멀티프로세싱 워커에서 사용할 공유 파라미터) ────────────────────

_G_MU: Optional[np.ndarray] = None # 종목별 연간 기대수익률 벡터
_G_COV: Optional[np.ndarray] = None # 종목별 공분산 행렬
_G_RF: float = 0.0 # 무위험 수익률 ( 0%로 가정 )
_G_NW: int = 0 # 각 조합에서 시도할 가중치 샘플 수


# ── 데이터 다운로드: 조정된 Close 사용, 결측/중복 정리 ─────────────────────────
def download_prices(
    tickers: Sequence[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    auto_adjust: bool = True,
) -> pd.DataFrame: # 리턴 타입 
    """
    야후 파이낸스에서 종가(Adjusted Close)를 다운로드하여 정리.
    -------
    pd.DataFrame
        index=날짜, columns=티커, values=조정종가(float)
    """
    if not tickers:
        raise ValueError("tickers 리스트가 비어 있습니다.")
    
    today = datetime.today().date()
    
    if end is None or start is None:
        end = today.strftime("%Y-%m-%d")
        one_year_ago = today - timedelta(days=365)
        start = one_year_ago.strftime("%Y-%m-%d")
        
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        progress=False,
    )
    
    # yfinance는 여러 종목의 경우 멀티인덱스로 들어와서 처리 
    if isinstance(raw.columns, pd.MultiIndex):
        px = raw["Close"]
    else:
        if "Close" in raw.columns:
            px = raw["Close"]
        else:
            # Series로 리턴되는 경우-> to_frame으로 데이터프레임으로 바꾸어줌 
            if isinstance(raw, pd.Series):
                px = raw.to_frame(name=tickers[0])
            else:
                # yfinance 응답 형식이 달라졌거나 데이터 없음
                raise RuntimeError("yfinance 응답에서 'Close' 컬럼을 찾지 못했습니다.")

    # 행/열에 NaN값이 하나라도 있으면 제거
    px = px.dropna(axis=1, how="all").dropna(how="any")
    # 중복 컬럼 제거
    px = px.loc[:, ~px.columns.duplicated()]

    # 요청한 순서대로 컬럼 재정렬
    cols = [t for t in tickers if t in px.columns]
    if not cols:
        raise RuntimeError("다운로드된 데이터에 유효한 티커가 없습니다.")
    return px[cols]


def _eval_batch_by_score(
    idx_batch: Sequence[Tuple[int, ...]],  # 종목 k 개 조합
    mu: np.ndarray,                             # 종목의 연 기대수익률 벡터
    cov: np.ndarray,                            # 종목간 공분산 행렬 
    rf_annual: float,                           # 연간 무위험수익률
    n_weights: int,                             # 한 조합당 시뮬레이션할 개수 
    seed: int,                                  # 난수 시드
    *,
    risk_profile : str = "balanced",
    alpha: float = 1.0,
    beta: float = 1.0,
    min_return: Optional[float] = None,
    max_vol: Optional[float] = None,
) -> List[Tuple[float, float, float, Tuple[int, int, int], List[float]]]:

    rng = np.random.default_rng(seed)

    B = len(idx_batch)
    idx = np.array(idx_batch, dtype=int)    
    k = idx.shape[1]            
        
    mu_k  = mu[idx]                                           
    cov_k = cov[idx[:, :, None], idx[:, None, :]]             

    W = rng.dirichlet(np.ones(k), size=(B, n_weights))

    # 기대수익/변동성 계산
    R   = (W * mu_k[:, None, :]).sum(axis=2)                  # (B,K)
    V   = np.einsum("bki,bij,bkj->bk", W, cov_k, W)           # (B,K)
    vol = np.sqrt(np.maximum(V, 1e-12))                      # (B,K)

    # 목적함수 점수 + 제약 마스크
    score, mask = _compute_score_and_mask_numpy(
        R, vol,
        rf_annual=rf_annual,
        risk_profile=risk_profile,
        alpha=alpha, beta=beta,
        min_return=min_return, max_vol=max_vol
    )
    # 제약 위반 샘플은 아주 작은 점수로 대체하여 선택에서 제외
    score = np.where(mask, score, -1e30)

    # 각 조합(best of K) 선택은 “점수” 기준
    kbest = score.argmax(axis=1)
    rows  = np.arange(B)

    bestScore = score[rows, kbest]
    bestR     = R[rows, kbest]
    bestV     = vol[rows, kbest]
    bestW     = W[rows, kbest, :]

    # 배치 내 상위 5개 (점수 기준)
    topk = 5 if B >= 5 else B
    top_idx = np.argpartition(bestScore, -topk)[-topk:]
    top_idx = top_idx[np.argsort(-bestScore[top_idx])]

    out: List[Tuple[float, float, float, Tuple[int, ...], List[float]]] = []
    for bi in top_idx:
        i, j, k = idx[bi].tolist()
        out.append((
            float(bestScore[bi]),
            float(bestR[bi]),
            float(bestV[bi]),
            (i, j, k),
            bestW[bi].tolist(),
        ))
    return out

# ── 멀티프로세싱 워커 초기화  ────────────────
def _init_worker_globals(mu: np.ndarray, cov: np.ndarray, rf_annual: float, n_weights: int) -> None:
    """
    각 워커 프로세스에서 공유할 파라미터 세팅.
    BLAS/OMP 과다 스레딩 방지를 위해 스레드 수 1로 제한.
    """
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["OMP_NUM_THREADS"] = "1"

    global _G_MU, _G_COV, _G_RF, _G_NW
    _G_MU = mu
    _G_COV = cov
    _G_RF = rf_annual
    _G_NW = n_weights

def evaluate_mp_by_score(
    prices: pd.DataFrame,
    rf_annual: float = 0.015,
    n_weights: int = 2000,
    batch_combos: int = 2000,
    topn: int = 5,
    seed: int = 42,
    *,
    k:int=3,
    risk_profile: str = "balanced",
    alpha: float = 1.0,
    beta: float = 1.0,
    min_return: Optional[float] = None,
    max_vol: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    멀티프로세싱으로 3종목 조합을 병렬 탐색하여 '목적함수 점수' 상위 topn 결과 반환.
    """
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")

    TRADING_DAYS = 252
    rets = prices.pct_change().dropna()
    mu = (rets.mean() * TRADING_DAYS).values
    cov = (rets.cov() * TRADING_DAYS).values
    tickers = prices.columns.tolist()
    A = len(tickers)

    combos_all = list(combinations(range(A), 3))

    batches: List[Tuple[Sequence[Tuple[int, int, int]], int]] = []
    for b_id, s in enumerate(range(0, len(combos_all), batch_combos)):
        batch = combos_all[s : s + batch_combos]
        seed_b = seed + b_id
        batches.append((batch, seed_b))

    workers = max(1, os.cpu_count() // 2)

    results: List[Tuple[float, float, float, Tuple[int, int, int], List[float]]] = []
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker_globals,
        initargs=(mu, cov, rf_annual, n_weights),
    ) as pool:
        # 각 배치마다 추가 파라미터를 넘길 수 있도록 래핑
        def task(args):
            batch, seed_b = args
            return _eval_batch_by_score(
                batch, mu, cov, rf_annual, n_weights, seed_b,
                risk_profile=risk_profile, alpha=alpha, beta=beta,
                min_return=min_return, max_vol=max_vol
            )
        for part in pool.map(task, batches, chunksize=10):  # ← chunksize 약간 키우면 통신부하↓
            results.extend(part)

    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:topn]

    nice: List[Dict[str, Any]] = []
    for score, ret, vol, (i, j, k), w in results:
        nice.append({
            "tickers": [tickers[i], tickers[j], tickers[k]],
            "weights": [float(w[0]), float(w[1]), float(w[2])],
            "score": float(score),
            "best_return": float(ret),
            "best_risk": float(vol),
            "risk_profile": risk_profile,
            "constraints": {"min_return": min_return, "max_vol": max_vol},
        })
    return nice

def _compute_score_and_mask_numpy(
    exp_ret: np.ndarray,     # 기대수익
    vol: np.ndarray,         # 변동성
    *,
    rf_annual: float = 0.015,
    risk_profile: str = "balanced",   # "aggressive" | "balanced" | "conservative"
    min_return: Optional[float] = None,
    max_vol: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    위험 성향(risk_profile)에 따라 점수를 계산하고
    제약조건을 만족하는 마스크를 반환.
    """
    
    if risk_profile == "aggressive":     
        alpha, beta, sharpe_gamma = 1.0, 0.5, 0.8
    elif risk_profile == "conservative": 
        alpha, beta, sharpe_gamma = 1.0, 2.0, 1.3
    elif risk_profile == "balanced":
        pass 
    else:
        raise ValueError(f"unknown risk_profile: {risk_profile}")

    if risk_profile == "balanced":
        score = (exp_ret - rf_annual) / np.power(vol, sharpe_gamma)
    else:
        score = alpha * exp_ret - beta * vol

    mask = np.ones_like(score, dtype=bool)
    if min_return is not None:
        mask &= (exp_ret >= float(min_return))
    if max_vol is not None:
        mask &= (vol <= float(max_vol))

    return score, mask
