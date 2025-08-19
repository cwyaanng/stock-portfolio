
"""
GPU(CUDA) 가속 Monte Carlo k-종목 조합 최적화 유틸

- evaluate_gpu_by_score : PyTorch(CUDA)로 k-종목 조합 탐색 (risk_profile 3단계)
- download_prices       : yfinance 가격 다운로드 (동일)
- warmup_gpu            : 서버 기동 시 1회 호출로 JIT/캐시 워밍업

주의
- n_weights, batch_combos, max_combos를 통해 속도/정확도/VRAM 밸런스 조절
- CUDA 미존재 시 CPU로 자동 폴백(그래도 torch 연산이므로 numpy보다 느릴 수 있음)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
import torch
from itertools import combinations
from datetime import datetime, timedelta
from .prices_db import load_prices_from_db
from .universe import NASDAQ100

__all__ = [
    "download_prices",
    "evaluate_gpu_by_score",
    "warmup_gpu",
]


# ─────────────────────────────────────────────────────────────────────────────
# 공용: 가격 다운로드 (네 기존 코드와 동일 로직)
def download_prices(
    tickers: Sequence[str],
    start: Optional[str] = None,
    end: Optional[str] = None,
    auto_adjust: bool = True,
) -> pd.DataFrame:
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

    if isinstance(raw.columns, pd.MultiIndex):
        px = raw["Close"]
    else:
        if "Close" in raw.columns:
            px = raw["Close"]
        else:
            if isinstance(raw, pd.Series):
                px = raw.to_frame(name=tickers[0])
            else:
                raise RuntimeError("yfinance 응답에서 'Close' 컬럼을 찾지 못했습니다.")

    px = px.dropna(axis=1, how="all").dropna(how="any")
    px = px.loc[:, ~px.columns.duplicated()]

    cols = [t for t in tickers if t in px.columns]
    if not cols:
        raise RuntimeError("다운로드된 데이터에 유효한 티커가 없습니다.")
    return px[cols]


# ─────────────────────────────────────────────────────────────────────────────
# 내부: 위험성향별 파라미터
def _profile_params(risk_profile: str) -> Tuple[float, float, float]:
    """
    return: (alpha, beta, sharpe_gamma)
    """
    rp = risk_profile.lower()
    if rp == "aggressive":      # 공격형: 위험 패널티 완화
        return 1.0, 0.5, 0.8
    elif rp == "balanced":      # 중립형: 기본 샤프
        return 1.0, 1.0, 1.0
    elif rp == "conservative":  # 안정형: 위험 패널티 강화
        return 1.0, 2.0, 1.3
    else:
        raise ValueError(f"unknown risk_profile: {risk_profile}")


@torch.no_grad()
def _score_and_mask_torch(
    exp_ret: torch.Tensor,   # (B, n)
    var: torch.Tensor,       # (B, n)
    *,
    rf_annual: float,
    risk_profile: str,
    min_return: Optional[float],
    max_vol: Optional[float],
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    목적함수 점수(score), 변동성(vol), 유효 마스크(mask)를 torch로 계산
    return: score(B,n), vol(B,n), mask(B,n)
    """
    alpha, beta, gamma = _profile_params(risk_profile)

    vol = torch.sqrt(torch.clamp(var, 1e-12))
    if risk_profile == "balanced":
        score = (exp_ret - rf_annual) / torch.clamp(vol, 1e-12) ** max(gamma, 1e-6)
    else:
        score = alpha * exp_ret - beta * vol

    mask = torch.ones_like(score, dtype=torch.bool)
    if min_return is not None:
        mask &= exp_ret >= float(min_return)
    if max_vol is not None:
        mask &= vol <= float(max_vol)

    return score, vol, mask


@torch.no_grad()
def evaluate_gpu_by_score(
    prices: pd.DataFrame,
    *,
    k: int = 3,
    risk_profile: str = "balanced",
    rf_annual: float = 0.015,
    n_weights: int = 100,
    batch_combos: int = 100_00,
    topn: int = 5,
    seed: int = 42,
    device: Optional[str] = None,       # "cuda"|"cpu"|None
    dtype: torch.dtype = torch.float32,
) -> List[Dict[str, Any]]:
    """
    CUDA 가속으로 k-종목 조합을 탐색하여 '점수' 상위 topn을 반환.

    - prices: index=날짜, columns=티커, values=조정종가
    - k: 조합 크기
    - risk_profile: "aggressive"|"balanced"|"conservative"
    - n_weights: 각 조합에서 샘플링할 가중치 수
    - batch_combos: 한 번에 평가할 조합 수(배치). VRAM에 맞게 조절
    """

    # ── 디바이스 결정
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(device)

    # ── μ, Σ 계산
    TRADING_DAYS = 252
    rets = prices.pct_change().dropna()
    mu_np = (rets.mean() * TRADING_DAYS).values.astype(np.float32)     # (A,)
    cov_np = (rets.cov() * TRADING_DAYS).values.astype(np.float32)     # (A, A)
    tickers = list(prices.columns)
    A = len(tickers)
    if k < 2 or k > A:
        raise ValueError(f"invalid k={k}; must be 2 <= k <= {A}")

    mu = torch.tensor(mu_np, device=device, dtype=dtype)                # (A,)
    cov = torch.tensor(cov_np, device=device, dtype=dtype)              # (A,A)

    # ── 조합 만들기 (+ 옵션 샘플링)
    all_combos = list(combinations(range(A), k))
    total = len(all_combos)

    rng = np.random.default_rng(seed)
  
    combos = all_combos

    results: List[Tuple[float, float, float, Tuple[int, ...], List[float]]] = []

    # ── 배치 루프
    for s in range(0, len(combos), batch_combos):
        batch = combos[s : s + batch_combos]
        B = len(batch)
        if B == 0:
            break

        idx = torch.tensor(batch, device=device, dtype=torch.long)      # (B, k)
        # (B, n, k) 합 1 가중치 샘플
        W = torch.rand((B, n_weights, k), device=device, dtype=dtype)
        W = W / (W.sum(dim=-1, keepdim=True) + 1e-12)

        mu_k  = mu[idx]                                                 # (B, k)
        cov_k = cov[idx[:, :, None], idx[:, None, :]]                   # (B, k, k)

        # 기대수익/분산
        R = (W * mu_k.unsqueeze(1)).sum(dim=-1)                         # (B, n)
        V = torch.einsum("bki,bij,bkj->bk", W, cov_k, W)                # (B, n)

        score, vol, mask = _score_and_mask_torch(
            R, V,
            rf_annual=rf_annual,
            risk_profile=risk_profile,
            min_return=None,           
            max_vol=None,
        )

        # 제약 위반에 큰 음수 부여
        score = torch.where(mask, score, torch.full_like(score, -1e30))

        # 각 조합에서 최고 샘플 선택
        best_idx = score.argmax(dim=1)                                   # (B,)
        rows = torch.arange(B, device=device)
        bestS = score[rows, best_idx]
        bestR = R[rows, best_idx]
        bestV = vol[rows, best_idx]
        bestW = W[rows, best_idx, :]                                     # (B, k)

        # Python 리스트로 수집 (topn 선별은 총합 후)
        for b in range(B):
            combo = tuple(int(x) for x in idx[b].tolist())
            results.append((
                float(bestS[b]),
                float(bestR[b]),
                float(bestV[b]),
                combo,
                [float(x) for x in bestW[b].tolist()],
            ))

        # 메모리 정리
        del idx, W, mu_k, cov_k, R, V, score, vol, mask, best_idx, rows, bestS, bestR, bestV, bestW
        if device == "cuda":
            torch.cuda.empty_cache()

    # ── 상위 topn만 반환
    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:topn]

    nice: List[Dict[str, Any]] = []
    for score, ret, vol, combo_idx, w in results:
        nice.append({
            "tickers": [tickers[i] for i in combo_idx],
            "weights": [float(x) for x in w],
            "score": float(score),
            "best_return": float(ret),
            "best_risk": float(vol),
            "risk_profile": risk_profile,
        })
    return nice


def get_optimal_portfolio(
    k: int,
    risk_profile: str = "balanced",
    start: str = "2024-01-01",
    end: str = "2025-01-01",
    n_weights: int = 100,
    batch_combos: int = 10_000,
    topn: int = 5,
) -> List[Dict[str, Any]]:
    """
    DB에서 가격 불러와 최적의 포트폴리오를 계산
    """
    # 1. DB에서 가격 불러오기
    prices = load_prices_from_db(NASDAQ100, start, end)

    if prices.empty:
        raise RuntimeError("DB에서 불러온 가격 데이터가 없습니다. DB를 먼저 채우세요.")

    # 2. GPU 최적화 실행
    results = evaluate_gpu_by_score(
        prices,
        k=k,
        risk_profile=risk_profile,
        n_weights=n_weights,
        batch_combos=batch_combos,
        topn=topn,
    )

    # 3. 반환 (이미 JSON-friendly dict)
    return results

# ─────────────────────────────────────────────────────────────────────────────
# 서버 기동 후 1회 호출 추천(첫 요청 지연 방지)
@torch.no_grad()
def warmup_gpu():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    x = torch.rand((1024, 1024), device=device)
    y = x @ x.T
    _ = y.sum().item()
    if device == "cuda":
        torch.cuda.synchronize()
