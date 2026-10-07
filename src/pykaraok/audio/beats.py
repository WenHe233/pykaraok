"""Beat grid of a song segment (numpy only).

Only for syncing decorations (pulses, sparkles) to the beat.  Syllable timing
must come from the user's \\k file: deriving \\k from audio cost an earlier
project over an hour and was then replaced by the user's own timing.

Method: spectral-flux onset strength -> autocorrelation over 60..200 BPM ->
comb search for the phase -> least-squares refinement against detected onsets.
"""
from __future__ import annotations

import subprocess

import numpy as np

from .. import config

SR = 22050
HOP = 128
NFFT = 1024


def load_audio(path, t0: float, t1: float, sr: int = SR) -> np.ndarray:
    cmd = [config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
           "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    data = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(data, np.float32).copy()


def onset_strength(y: np.ndarray, sr: int = SR) -> np.ndarray:
    if len(y) < NFFT:
        return np.zeros(1)
    win = np.hanning(NFFT).astype(np.float32)
    n = 1 + (len(y) - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = y[idx] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    # emphasise the low-mid range where kicks and snares live
    freqs = np.fft.rfftfreq(NFFT, 1 / sr)
    band = (freqs > 30) & (freqs < 6000)
    logm = np.log1p(10 * mag[:, band])
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")   # remove slow loudness changes
    return np.maximum(flux, 0)


def estimate(path, t0: float, t1: float, bpm_min: float = 60, bpm_max: float = 200) -> dict:
    y = load_audio(path, t0, t1)
    env = onset_strength(y)
    fps = SR / HOP
    if len(env) < fps * 4:
        raise ValueError("need at least a few seconds of audio")
    e = env - env.mean()
    ac = np.correlate(e, e, mode="full")[len(e) - 1:]
    lags = np.arange(len(ac))
    lo, hi = int(fps * 60 / bpm_max), int(fps * 60 / bpm_min)
    cand = np.arange(lo, min(hi, len(ac) - 1))
    # mild preference for 90..160 BPM to avoid half/double tempo picks
    bpms = 60 * fps / cand
    prior = np.exp(-0.5 * (np.log2(bpms / 120) / 0.9) ** 2)
    score = ac[cand] * prior
    best = cand[int(np.argmax(score))]
    # parabolic refinement of the lag
    if 0 < best < len(ac) - 1:
        a, b, c = ac[best - 1], ac[best], ac[best + 1]
        denom = a - 2 * b + c
        lag = best + (0.5 * (a - c) / denom if denom != 0 else 0)
    else:
        lag = float(best)
    period = lag / fps                                    # seconds per beat
    # phase: comb over one period
    steps = 200
    phases = np.linspace(0, period, steps, endpoint=False)
    # each envelope frame describes the window centred NFFT/2 samples after its start
    t_env = np.arange(len(env)) / fps
    center = NFFT / 2 / SR
    best_phase, best_val = 0.0, -1.0
    for ph in phases:
        beats = np.arange(ph, t_env[-1], period)
        idx = np.clip(np.round(beats * fps).astype(int), 0, len(env) - 1)
        v = env[idx].sum()
        if v > best_val:
            best_val, best_phase = v, ph
    # refine period and phase with a least-squares fit to local onset peaks
    beats = np.arange(best_phase, t_env[-1], period)
    fitted_k, fitted_t = [], []
    w = int(0.07 * fps)
    for k, bt in enumerate(beats):
        i = int(round(bt * fps))
        a, b = max(0, i - w), min(len(env), i + w + 1)
        if b - a < 3:
            continue
        j = a + int(np.argmax(env[a:b]))
        if env[j] > np.percentile(env, 75):
            fitted_k.append(k)
            fitted_t.append(j / fps + center)
    if len(fitted_k) >= 8:
        A = np.vstack([np.array(fitted_k, float), np.ones(len(fitted_k))]).T
        (period_f, phase_f), *_ = np.linalg.lstsq(A, np.array(fitted_t), rcond=None)
        if abs(period_f - period) / period < 0.03:
            period, best_phase = float(period_f), float(phase_f)
    resid = []
    for k, t in zip(fitted_k, fitted_t):
        resid.append(abs(t - (best_phase + k * period)))
    first = t0 + best_phase + (0 if len(fitted_k) >= 8 else center)
    bpm = 60.0 / period
    return {
        "bpm": round(bpm, 3),
        "beat_ms": round(period * 1000, 3),
        "first_beat_ms": int(round(first * 1000)),
        "range": [t0, t1],
        "matched_onsets": len(fitted_k),
        "median_error_ms": round(float(np.median(resid)) * 1000, 1) if resid else None,
        "lua": f"BEAT = px.beat({round(bpm, 3)}, {int(round(first * 1000))})",
    }
