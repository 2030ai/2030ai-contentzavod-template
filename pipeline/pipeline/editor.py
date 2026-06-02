"""Video editor engine: cut, speed, TTS, freeze-frame, branding, watermark, concat.

Each МК provides only data (segments, freeze segments, paths).
This module handles all ffmpeg logic.

Usage from edit.py:
    from pipeline.pipeline.editor import EditConfig, VideoSegment, FreezeSegment, build
    config = EditConfig(mk_dir=..., segments=[...], freeze_segments=[...])
    build(config)
"""

import asyncio
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.pipeline.text_prep import preprocess_for_tts, validate_tts_text
from pipeline.pipeline.tts import generate_voice, resolve_engine
from pipeline.pipeline.tts_verify import verify_tts

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "pipeline" / "assets"


@dataclass
class VideoSegment:
    """A segment cut from the raw recording."""
    name: str
    start: float
    end: float
    speed: float = 1.0
    text: str | None = None       # TTS text (will generate audio)
    audio_file: str | None = None  # pre-made audio filename (relative to audio_dir)


@dataclass
class FreezeSegment:
    """Voiceover over the last frame of the video."""
    name: str
    text: str


@dataclass
class EditConfig:
    mk_dir: Path
    segments: list[VideoSegment]
    freeze_segments: list[FreezeSegment] = field(default_factory=list)
    raw_video: str = "raw-recording.mov"
    audio_dir: str = "audio"  # subdir for pre-made audio files
    tts_engine: str = "auto"
    tts_voice_id: str | None = None
    scale_filter: str = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black"
    )


def _run(cmd: list[str], desc: str = "") -> str:
    """Run command as list of args (no shell), exit on error."""
    print(f"  {desc}..." if desc else f"  {' '.join(str(c) for c in cmd[:6])}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:500]}")
        sys.exit(1)
    return result.stdout.strip()


def _get_duration(path: Path) -> float:
    """Get media file duration in seconds."""
    out = _run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        f"probe {path.name}",
    )
    return float(out)


def _tts_cache_key(processed_text: str, engine: str, voice_id: str | None) -> str:
    """Build cache key from processed (post-override) text, engine, and voice."""
    return f"{engine}|{voice_id or ''}|{processed_text}"


def _tts_cache_valid(processed_text: str, output_path: Path, engine: str = "elevenlabs", voice_id: str | None = None) -> bool:
    """Check if cached TTS audio matches the current processed text, engine, and voice."""
    marker = output_path.with_suffix(".txt")
    if not output_path.exists() or not marker.exists():
        return False
    stored = marker.read_text(encoding="utf-8")
    expected = _tts_cache_key(processed_text, engine, voice_id)
    return stored == expected


_TTS_MAX_RETRIES = 3


def _generate_tts(
    text: str, output_path: Path, engine: str = "elevenlabs", voice_id: str | None = None,
) -> None:
    """Generate TTS audio (with cache and Whisper verification for ElevenLabs)."""
    effective_engine = resolve_engine(engine, voice_id)
    warnings = validate_tts_text(text, effective_engine)
    for w in warnings:
        print(f"    {w}")
    processed = preprocess_for_tts(text, engine=effective_engine)
    if _tts_cache_valid(processed, output_path, effective_engine, voice_id):
        print("    (cached)")
        return

    for attempt in range(1, _TTS_MAX_RETRIES + 1):
        asyncio.run(generate_voice(
            text=text,
            output_path=output_path,
            language="ru",
            speaker="male",
            engine=effective_engine,
            voice_id=voice_id,
        ))

        # Verify only ElevenLabs (hallucination-prone)
        if effective_engine != "elevenlabs":
            break

        passed, score, transcript = verify_tts(output_path, text)
        if passed:
            print(f"    TTS verified (score={score:.0%})")
            break

        print(f"    TTS verification FAILED attempt {attempt}/{_TTS_MAX_RETRIES} "
              f"(score={score:.0%})")
        print(f"    Expected: {text[:80]}...")
        print(f"    Got:      {transcript[:80]}...")
        if attempt < _TTS_MAX_RETRIES:
            output_path.unlink(missing_ok=True)
    else:
        print(f"\n    FATAL: TTS verification failed after {_TTS_MAX_RETRIES} attempts.")
        print(f"    Segment audio: {output_path}")
        print(f"    Expected text: {text}")
        print(f"    Whisper heard:  {transcript}")
        print(f"    Score: {score:.0%} (threshold: 70%)")
        print("\n    Fix: rephrase the text to avoid ElevenLabs hallucination.")
        sys.exit(1)

    output_path.with_suffix(".txt").write_text(
        _tts_cache_key(processed, effective_engine, voice_id), encoding="utf-8",
    )


def _process_video_segment(
    seg: VideoSegment,
    seg_num: int,
    total: int,
    config: EditConfig,
    work_dir: Path,
    raw_video: Path,
) -> Path:
    """Process a single video segment: cut, speed, TTS/audio, mux."""
    raw_dur = seg.end - seg.start

    seg_audio = work_dir / f"{seg.name}.mp3"
    seg_video = work_dir / f"{seg.name}_v.mp4"
    seg_final = work_dir / f"{seg.name}.mp4"

    # Resolve audio: TTS text, pre-made file, or silent
    has_audio = False
    if seg.text:
        print(f"[{seg_num}/{total}] TTS: {seg.name}")
        _generate_tts(seg.text, seg_audio, config.tts_engine, config.tts_voice_id)
        has_audio = True
    elif seg.audio_file:
        audio_path = config.mk_dir / config.audio_dir / seg.audio_file
        if not audio_path.suffix:
            audio_path = audio_path.with_suffix(".mp3")
        if audio_path.exists():
            seg_audio = audio_path
            has_audio = True

    if has_audio:
        audio_dur = _get_duration(seg_audio)
    else:
        audio_dur = None

    # Calculate speed: for pre-made audio, adjust speed to match audio duration;
    # for TTS or silent, use the configured speed
    if seg.audio_file and audio_dur is not None:
        speed = raw_dur / audio_dur
    else:
        speed = seg.speed

    video_dur = raw_dur / speed
    pts_factor = 1.0 / speed

    if audio_dur is None:
        audio_dur = video_dur

    final_dur = max(video_dur, audio_dur)
    print(f"[{seg_num}/{total}] {seg.name}: {raw_dur:.1f}s raw / {seg.speed}x -> "
          f"{video_dur:.1f}s video, {audio_dur:.1f}s audio, {final_dur:.1f}s final")

    # Cut + scale + speed
    _run(
        ["ffmpeg", "-y", "-ss", str(seg.start), "-t", str(raw_dur),
         "-i", str(raw_video),
         "-vf", f"{config.scale_filter},setpts={pts_factor}*PTS",
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-r", "30", str(seg_video)],
        f"cut+speed {seg.name}",
    )

    # Extend video with last frame if audio is longer
    if has_audio and audio_dur > video_dur + 0.5:
        last_frame = work_dir / f"{seg.name}_last.png"
        _run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(seg_video),
             "-frames:v", "1", str(last_frame)],
            f"last frame {seg.name}",
        )
        pad_dur = audio_dur - video_dur + 0.5
        pad_clip = work_dir / f"{seg.name}_pad.mp4"
        _run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(last_frame),
             "-t", f"{pad_dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-r", "30", str(pad_clip)],
            f"pad clip {seg.name}",
        )
        extended = work_dir / f"{seg.name}_ext.mp4"
        pad_list = work_dir / f"{seg.name}_padlist.txt"
        with open(pad_list, "w") as f:
            f.write(f"file '{seg_video}'\nfile '{pad_clip}'\n")
        _run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(pad_list),
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-r", "30", str(extended)],
            f"extend {seg.name}",
        )
        seg_video = extended

    # Mux video + audio
    if has_audio:
        _run(
            ["ffmpeg", "-y", "-i", str(seg_video), "-i", str(seg_audio),
             "-filter_complex", "[1:a]apad[a]", "-map", "0:v", "-map", "[a]",
             "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "1",
             "-b:a", "128k", "-shortest", str(seg_final)],
            f"mux {seg.name}",
        )
    else:
        _run(
            ["ffmpeg", "-y", "-i", str(seg_video),
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
             "-c:v", "copy", "-c:a", "aac", "-shortest", str(seg_final)],
            f"silent {seg.name}",
        )

    return seg_final


def _process_freeze_segment(
    seg: FreezeSegment,
    seg_num: int,
    total: int,
    work_dir: Path,
    freeze_frame: Path,
    engine: str = "elevenlabs",
    voice_id: str | None = None,
) -> Path:
    """Process a freeze-frame segment: TTS over static image."""
    seg_audio = work_dir / f"{seg.name}.mp3"
    seg_final = work_dir / f"{seg.name}.mp4"

    print(f"[{seg_num}/{total}] TTS: {seg.name}")
    _generate_tts(seg.text, seg_audio, engine, voice_id)
    audio_dur = _get_duration(seg_audio)
    freeze_dur = audio_dur + 0.5

    print(f"[{seg_num}/{total}] {seg.name}: freeze {freeze_dur:.1f}s")

    freeze_video = work_dir / f"{seg.name}_v.mp4"
    _run(
        ["ffmpeg", "-y", "-loop", "1", "-i", str(freeze_frame),
         "-t", f"{freeze_dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-r", "30", str(freeze_video)],
        f"freeze video {seg.name}",
    )

    _run(
        ["ffmpeg", "-y", "-i", str(freeze_video), "-i", str(seg_audio),
         "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "1",
         "-b:a", "128k", "-shortest", str(seg_final)],
        f"mux {seg.name}",
    )

    return seg_final


def _add_branding(work_dir: Path) -> tuple[Path | None, Path | None]:
    """Create intro and outro clips from branding assets."""
    intro_img = ASSETS_DIR / "intro.png"
    outro_img = ASSETS_DIR / "outro.png"

    if not intro_img.exists():
        return None, None

    intro_clip = work_dir / "brand_intro.mp4"
    outro_clip = work_dir / "brand_outro.mp4"

    for clip, img, label in [
        (intro_clip, intro_img, "intro"),
        (outro_clip, outro_img if outro_img.exists() else intro_img, "outro"),
    ]:
        _run(
            ["ffmpeg", "-y", "-loop", "1", "-i", str(img),
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
             "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-r", "30", "-c:a", "aac", "-shortest", str(clip)],
            f"branding {label}",
        )

    return intro_clip, outro_clip


def _apply_watermark(input_path: Path, output_path: Path) -> None:
    """Apply watermark overlay if asset exists."""
    watermark = ASSETS_DIR / "watermark.png"
    if watermark.exists():
        _run(
            ["ffmpeg", "-y", "-i", str(input_path), "-i", str(watermark),
             "-filter_complex", "overlay=W-w-20:H-h-20",
             "-c:v", "libx264", "-preset", "fast", "-crf", "20",
             "-c:a", "copy", str(output_path)],
            "apply watermark",
        )
    else:
        shutil.copy2(input_path, output_path)


def build(config: EditConfig) -> None:
    """Build the final video from config."""
    work_dir = config.mk_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    raw_video = config.mk_dir / config.raw_video
    output = config.mk_dir / "final.mp4"

    if not raw_video.exists():
        print(f"ERROR: {raw_video} not found")
        sys.exit(1)

    total = len(config.segments) + len(config.freeze_segments)
    print(f"Raw video: {raw_video.name}")
    print(f"Segments: {total} ({len(config.segments)} video + {len(config.freeze_segments)} freeze)")
    print()

    segment_files: list[Path] = []
    seg_num = 0

    # Video segments
    for seg in config.segments:
        seg_num += 1
        seg_file = _process_video_segment(seg, seg_num, total, config, work_dir, raw_video)
        segment_files.append(seg_file)

    # Freeze-frame segments
    if config.freeze_segments and segment_files:
        freeze_frame = work_dir / "freeze_base.png"
        _run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(segment_files[-1]),
             "-frames:v", "1", str(freeze_frame)],
            "extract freeze frame",
        )
        for seg in config.freeze_segments:
            seg_num += 1
            seg_file = _process_freeze_segment(
                seg, seg_num, total, work_dir, freeze_frame,
                config.tts_engine, config.tts_voice_id,
            )
            segment_files.append(seg_file)

    # Branding
    intro_clip, outro_clip = _add_branding(work_dir)

    # Concat all
    all_files: list[Path] = []
    if intro_clip and intro_clip.exists():
        all_files.append(intro_clip)
    all_files.extend(segment_files)
    if outro_clip and outro_clip.exists():
        all_files.append(outro_clip)

    concat_list = work_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for p in all_files:
            f.write(f"file '{p}'\n")

    concat_raw = work_dir / "concat_raw.mp4"
    _run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-c:a", "aac", "-ar", "48000", "-ac", "1", "-b:a", "128k",
         str(concat_raw)],
        "concatenate all segments",
    )

    # Watermark
    _apply_watermark(concat_raw, output)

    # Summary
    final_dur = _get_duration(output)
    print(f"\nDone! Final video: {output}")
    print(f"Duration: {final_dur:.1f}s ({final_dur/60:.1f} min)")
    print(f"Size: {output.stat().st_size / 1024 / 1024:.1f} MB")
