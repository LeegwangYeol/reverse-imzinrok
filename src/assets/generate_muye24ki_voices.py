#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_muye24ki_voices.py
Generates authentic Korean Sageuk AI TTS voice lines + Imjinrok 2+ battlefield DSP post-processing
+ authentic weapon/armor Foley layering for the 5 Muye24ki Joseon infantry units (0x7A..0x7E).

Outputs:
1. 20 .YAV files in YM/dawn/tempeft/ (select_*, die_*, move_*, attack_*)
2. Registers EffectSound IDs 485..504 in YM/dawn/EffectSound.dat (preserving backup EffectSound.dat.orig)
3. Exports standard .wav preview files and a combined showcase .wav into the artifact directory.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import stat
import struct
import sys
import wave
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DAWN_DIR = PROJECT_ROOT / "YM" / "dawn"
TEMPEFT_DIR = DAWN_DIR / "tempeft"
EFT_DIR = DAWN_DIR / "eft"
EFFECT_SOUND_DAT = DAWN_DIR / "EffectSound.dat"
EFFECT_SOUND_ORIG = DAWN_DIR / "EffectSound.dat.orig"

TARGET_SR = 22050

# 5 Units x 4 Voice States = 20 EffectSound Entries (IDs 485..504)
# Mapped to unused SoundGroup IDs:
#   등패수 (0x7A): SoundGroups 202..205 -> EffectSound 485..488
#   쌍수도병 (0x7B): SoundGroups 206..209 -> EffectSound 489..492
#   장창수 (0x7C): SoundGroups 210..213 -> EffectSound 493..496
#   월도병 (0x7D): SoundGroups 214..217 -> EffectSound 497..500
#   낭선병 (0x7E): SoundGroups 238..241 -> EffectSound 501..504
UNIT_VOICE_SPECS = [
    {
        "unit_key": "dengpaesu",
        "kor_name": "등패수",
        "kind_id": 0x7A,
        "base_sound_group": 202,
        "base_effect_id": 485,
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-14Hz",
        "rate": "+8%",
        "dsp_pitch_ratio": 0.95,  # Solid frontline shield defender
        "lines": {
            "select": (
                "EFFECT_SELECT_DENGPAESU",
                "select_dengpaesu.yav",
                "등패수! 방패를 굳게 세웠습니다!",
                [("eft/sword2.yav", 0.02, 0.28)],
            ),
            "die": (
                "EFFECT_DIE_DENGPAESU",
                "die_dengpaesu.yav",
                "으억! 방패가...",
                [("tempeft/die_swordk1.yav", 0.18, 0.65)],
            ),
            "move": (
                "EFFECT_MOVE_DENGPAESU",
                "move_dengpaesu.yav",
                "방패 진형으로 전진하라!",
                [],
            ),
            "attack": (
                "EFFECT_ATTACK_DENGPAESU",
                "attack_dengpaesu.yav",
                "막고 베어라! 이얍!",
                [("eft/sword2.yav", 0.05, 0.45), ("eft/sword1.yav", 0.45, 0.45)],
            ),
        },
    },
    {
        "unit_key": "ssangsudo",
        "kor_name": "쌍수도병",
        "kind_id": 0x7B,
        "base_sound_group": 206,
        "base_effect_id": 489,
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-18Hz",
        "rate": "+12%",
        "dsp_pitch_ratio": 0.90,  # Fierce heavy greatsword shock trooper
        "lines": {
            "select": (
                "EFFECT_SELECT_SSANGSUDO",
                "select_ssangsudo.yav",
                "쌍수도병! 대검을 뽑았습니다!",
                [("eft/bigsword1.yav", 0.02, 0.35)],
            ),
            "die": (
                "EFFECT_DIE_SSANGSUDO",
                "die_ssangsudo.yav",
                "크아악! 내 칼이...",
                [("tempeft/die_swordk2.yav", 0.15, 0.68)],
            ),
            "move": (
                "EFFECT_MOVE_SSANGSUDO",
                "move_ssangsudo.yav",
                "비켜라! 선봉으로 나간다!",
                [],
            ),
            "attack": (
                "EFFECT_ATTACK_SSANGSUDO",
                "attack_ssangsudo.yav",
                "두 동강을 내주마! 핫!",
                [("eft/bigsword1.yav", 0.08, 0.55), ("eft/sword3.yav", 0.50, 0.45)],
            ),
        },
    },
    {
        "unit_key": "jangchangsu",
        "kor_name": "장창수",
        "kind_id": 0x7C,
        "base_sound_group": 210,
        "base_effect_id": 493,
        "voice": "ko-KR-InJoonNeural",
        "pitch": "+4Hz",
        "rate": "+15%",
        "dsp_pitch_ratio": 1.02,  # Sharp, disciplined formation pikeman
        "lines": {
            "select": (
                "EFFECT_SELECT_JANGCHANGSU",
                "select_jangchangsu.yav",
                "장창수! 창끝을 정렬했습니다!",
                [("eft/sword1.yav", 0.02, 0.25)],
            ),
            "die": (
                "EFFECT_DIE_JANGCHANGSU",
                "die_jangchangsu.yav",
                "으아악! 대열을 지켜라!",
                [("tempeft/die_archerk1.yav", 0.15, 0.65)],
            ),
            "move": (
                "EFFECT_MOVE_JANGCHANGSU",
                "move_jangchangsu.yav",
                "장창 대열을 맞춰 전진하라!",
                [],
            ),
            "attack": (
                "EFFECT_ATTACK_JANGCHANGSU",
                "attack_jangchangsu.yav",
                "장창으로 꿰뚫어라! 얏!",
                [("eft/sword1.yav", 0.05, 0.45), ("eft/arrow2.yav", 0.42, 0.40)],
            ),
        },
    },
    {
        "unit_key": "woldo",
        "kor_name": "월도병",
        "kind_id": 0x7D,
        "base_sound_group": 214,
        "base_effect_id": 497,
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-24Hz",
        "rate": "+4%",
        "dsp_pitch_ratio": 0.87,  # Deep, booming veteran halberdier
        "lines": {
            "select": (
                "EFFECT_SELECT_WOLDO",
                "select_woldo.yav",
                "월도병! 언월도의 날이 번뜩인다!",
                [("eft/bigsword1.yav", 0.02, 0.32)],
            ),
            "die": (
                "EFFECT_DIE_WOLDO",
                "die_woldo.yav",
                "크으윽... 원통하다!",
                [("tempeft/die_swordk1.yav", 0.20, 0.65)],
            ),
            "move": (
                "EFFECT_MOVE_WOLDO",
                "move_woldo.yav",
                "묵직하게 진군하라!",
                [],
            ),
            "attack": (
                "EFFECT_ATTACK_WOLDO",
                "attack_woldo.yav",
                "언월도로 쓸어버려라! 이얏!",
                [("eft/bigsword1.yav", 0.06, 0.52), ("eft/sword2.yav", 0.48, 0.45)],
            ),
        },
    },
    {
        "unit_key": "nangseon",
        "kor_name": "낭선병",
        "kind_id": 0x7E,
        "base_sound_group": 238,
        "base_effect_id": 501,
        "voice": "ko-KR-InJoonNeural",
        "pitch": "-6Hz",
        "rate": "+12%",
        "dsp_pitch_ratio": 0.98,  # Agile bamboo vanguard
        "lines": {
            "select": (
                "EFFECT_SELECT_NANGSEON",
                "select_nangseon.yav",
                "낭선병! 가시창 진형을 갖췄습니다!",
                [("eft/arrow1.yav", 0.02, 0.30)],
            ),
            "die": (
                "EFFECT_DIE_NANGSEON",
                "die_nangseon.yav",
                "으윽! 진형이 무너진다...",
                [("tempeft/die_archerk2.yav", 0.16, 0.65)],
            ),
            "move": (
                "EFFECT_MOVE_NANGSEON",
                "move_nangseon.yav",
                "낭선을 앞세워 진격하라!",
                [],
            ),
            "attack": (
                "EFFECT_ATTACK_NANGSEON",
                "attack_nangseon.yav",
                "가시창으로 밀어내라! 핫!",
                [("eft/arrow1.yav", 0.04, 0.45), ("eft/sword2.yav", 0.42, 0.45)],
            ),
        },
    },
]


def read_yav_float(rel_path: str) -> np.ndarray:
    """Read an existing Imjinrok 2+ .YAV file as float64 mono in [-1.0, 1.0] at 22050 Hz."""
    full_path = DAWN_DIR / rel_path.replace("/", os.sep)
    if not full_path.exists():
        return np.zeros(0, dtype=np.float64)
    b = full_path.read_bytes()
    fmt_sz, tag, ch, sr, bps, align, bits, cb, data_sz = struct.unpack("<IHHIIHHHI", b[:26])
    raw = b[26 : 26 + data_sz]
    if bits == 16:
        raw = raw[: (len(raw) // 2) * 2]
        arr = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
    else:
        arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    if ch == 2 and len(arr) >= 2:
        arr = arr.reshape(-1, 2).mean(axis=1)
    if sr != TARGET_SR and len(arr) > 1:
        new_len = int(len(arr) * TARGET_SR / sr)
        x_old = np.linspace(0.0, 1.0, len(arr))
        x_new = np.linspace(0.0, 1.0, new_len)
        arr = np.interp(x_new, x_old, arr)
    return arr


def encode_yav_bytes(pcm_int16: np.ndarray, sample_rate: int = TARGET_SR) -> bytes:
    """Pack 16-bit mono PCM samples into Imjinrok 2+ .YAV binary format (26-byte header + PCM)."""
    raw_bytes = pcm_int16.astype("<i2").tobytes()
    data_sz = len(raw_bytes)
    header = struct.pack(
        "<IHHIIHHHI",
        18,               # sizeof(WAVEFORMATEX)
        1,                # WAVE_FORMAT_PCM
        1,                # nChannels = 1 (Mono)
        sample_rate,      # nSamplesPerSec = 22050
        sample_rate * 2,  # nAvgBytesPerSec = 44100
        2,                # nBlockAlign = 2
        16,               # wBitsPerSample = 16
        0,                # cbSize = 0
        data_sz,          # data chunk byte length
    )
    return header + raw_bytes


def apply_battlefield_dsp(
    voice_f64: np.ndarray,
    pitch_ratio: float,
    foley_layers: List[Tuple[str, float, float]],
    is_die: bool = False,
) -> np.ndarray:
    """
    Apply authentic 1999 Imjinrok 2+ battlefield vocal DSP:
    1. Trim leading/trailing silence (< 10ms response time).
    2. Subtle pitch/formant resample (`pitch_ratio`) for warrior chest resonance.
    3. Warm vintage bandpass & presence boost (120Hz HPF + 1.8kHz mid presence + 6.5kHz LPF).
    4. Analog tape saturation (`tanh`) + 34ms open-field slapback ambience.
    5. Layer authentic Imjinrok 2+ weapon/shield Foley and death groans.
    6. Normalize RMS (~5200) and peak (~30500) to match native `tempeft/*.yav`.
    """
    # 1. Trim silence
    abs_v = np.abs(voice_f64)
    thresh = max(0.015, np.max(abs_v) * 0.03)
    nz = np.where(abs_v > thresh)[0]
    if len(nz) > 0:
        start = max(0, nz[0] - int(0.012 * TARGET_SR))
        end = min(len(voice_f64), nz[-1] + int(0.06 * TARGET_SR))
        voice_f64 = voice_f64[start:end]

    # 2. Subtle DSP pitch/formant shift for warrior timbre
    if abs(pitch_ratio - 1.0) > 0.005 and len(voice_f64) > 10:
        new_len = int(len(voice_f64) / pitch_ratio)
        x_old = np.linspace(0.0, 1.0, len(voice_f64))
        x_new = np.linspace(0.0, 1.0, new_len)
        voice_f64 = np.interp(x_new, x_old, voice_f64)

    # 3. Frequency-domain vintage RTS EQ (120Hz high-pass, 1.4-2.8kHz presence boost, 6.8kHz rolloff)
    n = len(voice_f64)
    if n > 64:
        spec = np.fft.rfft(voice_f64)
        freqs = np.fft.rfftfreq(n, d=1.0 / TARGET_SR)
        eq = np.ones_like(freqs)
        # High-pass below 120 Hz
        eq *= np.clip((freqs - 60.0) / 80.0, 0.0, 1.0)
        # Chest resonance boost around 220-450 Hz (+2.5 dB)
        eq += 0.32 * np.exp(-0.5 * ((freqs - 310.0) / 110.0) ** 2)
        # Battlefield command presence around 1850 Hz (+3.5 dB)
        eq += 0.48 * np.exp(-0.5 * ((freqs - 1850.0) / 650.0) ** 2)
        # Vintage 22kHz anti-harshness roll-off above 6500 Hz
        eq *= 1.0 / (1.0 + (freqs / 6800.0) ** 4)
        voice_f64 = np.fft.irfft(spec * eq, n=n)

    # 4. Soft tape saturation & short battlefield slapback reflection (33ms + 68ms)
    peak_in = np.max(np.abs(voice_f64)) + 1e-8
    voice_f64 = voice_f64 / peak_in
    voice_f64 = np.tanh(1.65 * voice_f64) / np.tanh(1.65)

    delay1 = int(0.033 * TARGET_SR)
    delay2 = int(0.068 * TARGET_SR)
    out_len = len(voice_f64) + delay2 + int(0.08 * TARGET_SR)
    mix = np.zeros(out_len, dtype=np.float64)
    mix[: len(voice_f64)] += voice_f64
    mix[delay1 : delay1 + len(voice_f64)] += 0.16 * voice_f64
    mix[delay2 : delay2 + len(voice_f64)] += 0.06 * voice_f64

    # 5. Mix authentic Imjinrok 2+ Foley / battle grunts
    for rel_foley, offset_sec, gain in foley_layers:
        foley = read_yav_float(rel_foley)
        if len(foley) == 0:
            continue
        pos = int(offset_sec * TARGET_SR)
        req_len = pos + len(foley)
        if req_len > len(mix):
            mix = np.pad(mix, (0, req_len - len(mix)))
        if is_die:
            # Blend death voice into authentic Korean soldier death groan
            mix[pos : pos + len(foley)] += gain * foley
        else:
            mix[pos : pos + len(foley)] += gain * foley

    # 6. Normalize to match native Imjinrok 2+ unit voice levels (RMS ~5200, Peak ~30200)
    peak = np.max(np.abs(mix)) + 1e-8
    mix = mix / peak
    # Apply gentle limiter so RMS is strong and clear over battlefield BGM
    mix = np.tanh(1.35 * mix) / np.tanh(1.35)
    pcm_int16 = np.clip(mix * 30200.0, -32767, 32767).astype(np.int16)
    return pcm_int16


async def synthesize_tts_float(text: str, voice: str, pitch: str, rate: str) -> np.ndarray:
    """Synthesize Korean speech via edge-tts and decode to 22050 Hz float64 mono."""
    import edge_tts
    import miniaudio

    comm = edge_tts.Communicate(text=text, voice=voice, pitch=pitch, rate=rate)
    mp3_bytes = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            mp3_bytes.extend(chunk["data"])
    decoded = miniaudio.decode(
        bytes(mp3_bytes),
        output_format=miniaudio.SampleFormat.SIGNED16,
        nchannels=1,
        sample_rate=TARGET_SR,
    )
    samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float64) / 32768.0
    return samples


async def generate_all_voices(artifact_dir: Path | None = None) -> List[Dict]:
    """Generate all 20 .YAV files, update EffectSound.dat, and export WAV previews."""
    TEMPEFT_DIR.mkdir(parents=True, exist_ok=True)
    if artifact_dir:
        artifact_dir.mkdir(parents=True, exist_ok=True)

    # Backup original EffectSound.dat once
    if not EFFECT_SOUND_ORIG.exists() and EFFECT_SOUND_DAT.exists():
        shutil.copy2(EFFECT_SOUND_DAT, EFFECT_SOUND_ORIG)

    generated_meta = []
    combined_showcase_pcm = []
    silence_gap = np.zeros(int(0.35 * TARGET_SR), dtype=np.int16)

    state_order = ["select", "die", "move", "attack"]
    for u in UNIT_VOICE_SPECS:
        for idx, st in enumerate(state_order):
            eff_id = u["base_effect_id"] + idx
            grp_id = u["base_sound_group"] + idx
            desc_name, yav_filename, line_text, foley_list = u["lines"][st]

            raw_voice = await synthesize_tts_float(
                text=line_text,
                voice=u["voice"],
                pitch=u["pitch"],
                rate=u["rate"],
            )
            pcm16 = apply_battlefield_dsp(
                voice_f64=raw_voice,
                pitch_ratio=u["dsp_pitch_ratio"],
                foley_layers=foley_list,
                is_die=(st == "die"),
            )

            # Write .YAV to YM/dawn/tempeft/
            yav_path = TEMPEFT_DIR / yav_filename
            yav_bytes = encode_yav_bytes(pcm16, TARGET_SR)
            yav_path.write_bytes(yav_bytes)

            dur = len(pcm16) / TARGET_SR
            rms = float(np.sqrt(np.mean(pcm16.astype(np.float64) ** 2)))
            peak = int(np.max(np.abs(pcm16)))

            combined_showcase_pcm.append(pcm16)
            combined_showcase_pcm.append(silence_gap)

            wav_preview_path = None
            if artifact_dir:
                wav_preview_path = artifact_dir / yav_filename.replace(".yav", ".wav")
                with wave.open(str(wav_preview_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(TARGET_SR)
                    wf.writeframes(pcm16.tobytes())

            info = {
                "unit_key": u["unit_key"],
                "kor_name": u["kor_name"],
                "kind_id": u["kind_id"],
                "state": st,
                "effect_id": eff_id,
                "sound_group_id": grp_id,
                "desc_name": desc_name,
                "yav_filename": yav_filename,
                "line_text": line_text,
                "duration_sec": round(dur, 2),
                "rms": round(rms, 1),
                "peak": peak,
                "yav_size": len(yav_bytes),
                "wav_preview": str(wav_preview_path) if wav_preview_path else "",
            }
            generated_meta.append(info)
            print(
                f"[OK] {u['kor_name']} ({st:6s}) -> ID={eff_id}, Grp={grp_id}, "
                f"File=tempeft\\{yav_filename} ({dur:.2f}s, RMS={rms:.0f}, Peak={peak}) | \"{line_text}\""
            )

    # Save combined showcase WAV in artifact_dir
    if artifact_dir and combined_showcase_pcm:
        all_pcm = np.concatenate(combined_showcase_pcm)
        showcase_wav = artifact_dir / "muye24ki_5_units_all_voices_showcase.wav"
        with wave.open(str(showcase_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_SR)
            wf.writeframes(all_pcm.tobytes())
        print(f"[OK] Saved combined 20-line voice showcase WAV: {showcase_wav}")

    # Update YM/dawn/EffectSound.dat from pristine backup + 20 new lines
    sync_effect_sound_dat()
    return generated_meta


def sync_effect_sound_dat() -> None:
    """Append EffectSound IDs 485..504 to YM/dawn/EffectSound.dat and mark Read-Only so UnpackHQ/DeleteFileA preserve it."""
    if not EFFECT_SOUND_ORIG.exists() and EFFECT_SOUND_DAT.exists():
        shutil.copy2(EFFECT_SOUND_DAT, EFFECT_SOUND_ORIG)
    base_bytes = EFFECT_SOUND_ORIG.read_bytes() if EFFECT_SOUND_ORIG.exists() else EFFECT_SOUND_DAT.read_bytes()
    base_text = base_bytes.decode("cp949", errors="replace")
    clean_lines = []
    for line in base_text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip().isdigit():
            if int(parts[1].strip()) >= 485:
                continue
        clean_lines.append(line)

    state_order = ["select", "die", "move", "attack"]
    for u in UNIT_VOICE_SPECS:
        for idx, st in enumerate(state_order):
            eff_id = u["base_effect_id"] + idx
            desc_name, yav_filename, _, _ = u["lines"][st]
            new_line = (
                f"{desc_name}\t{eff_id}\t"
                f"tempeft\\\\{yav_filename}\t1\t0\t0\t0\t0\t5\t0\t0\t0\t0"
            )
            clean_lines.append(new_line)

    updated_text = "\r\n".join(clean_lines) + "\r\n"
    if EFFECT_SOUND_DAT.exists():
        os.chmod(EFFECT_SOUND_DAT, stat.S_IWRITE | stat.S_IREAD)
    EFFECT_SOUND_DAT.write_bytes(updated_text.encode("cp949"))
    os.chmod(EFFECT_SOUND_DAT, stat.S_IREAD)
    print(f"[OK] Updated {EFFECT_SOUND_DAT} (Read-Only protected) with 20 new EffectSound entries (IDs 485..504).")


if __name__ == "__main__":
    art_dir = Path(r"C:\Users\bpsco_93p6pse\.gemini\antigravity\brain\012fe533-910e-484f-9444-ed8db88cb5d7")
    asyncio.run(generate_all_voices(art_dir))
