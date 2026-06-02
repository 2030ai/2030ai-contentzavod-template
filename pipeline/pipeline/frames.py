"""Extract frames from video with automatic resize for Claude analysis.

Usage:
    python -m pipeline.frames video.mp4                    # 5 frames, max 1600px
    python -m pipeline.frames video.mp4 -n 10              # 10 frames
    python -m pipeline.frames video.mp4 -n 10 --max 1200   # 10 frames, max 1200px
    python -m pipeline.frames video.mp4 -t 0:15 1:30 2:45  # frames at specific timestamps
    python -m pipeline.frames video.mp4 -o ./my-frames     # custom output dir
"""

import argparse
import subprocess
from pathlib import Path


MAX_DIMENSION = 1600  # safe margin under 2000px API limit


def get_duration(video: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def extract_frame(video: Path, timestamp: str, output: Path, max_dim: int) -> Path:
    vf = (
        f"scale='if(gt(iw,ih),min({max_dim},iw),-2)'"
        f":'if(gt(ih,iw),min({max_dim},ih),-2)'"
    )
    subprocess.run(
        ["ffmpeg", "-y", "-ss", timestamp, "-i", str(video),
         "-vf", vf, "-frames:v", "1", "-q:v", "2", str(output)],
        capture_output=True, check=True,
    )
    return output


def seconds_to_timestamp(s: float) -> str:
    m, sec = divmod(s, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{int(m):02d}:{sec:05.2f}"


def extract_frames(
    video: Path,
    n: int = 5,
    timestamps: list[str] | None = None,
    max_dim: int = MAX_DIMENSION,
    output_dir: Path | None = None,
) -> list[Path]:
    video = Path(video).resolve()
    if not video.exists():
        raise FileNotFoundError(f"Video not found: {video}")

    if output_dir is None:
        output_dir = video.parent / f"{video.stem}-frames"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if timestamps:
        times = timestamps
    else:
        duration = get_duration(video)
        # evenly spaced, skip first/last 1 second
        start = min(1.0, duration * 0.02)
        end = max(duration - 1.0, duration * 0.98)
        step = (end - start) / max(n - 1, 1)
        times = [seconds_to_timestamp(start + i * step) for i in range(n)]

    frames = []
    for i, ts in enumerate(times):
        out = output_dir / f"frame_{i + 1:03d}.jpg"
        extract_frame(video, ts, out, max_dim)
        frames.append(out)
        print(f"  [{i + 1}/{len(times)}] {ts} -> {out.name}")

    print(f"\n{len(frames)} frames saved to {output_dir}")
    return frames


def main():
    parser = argparse.ArgumentParser(description="Extract frames for Claude analysis")
    parser.add_argument("video", type=Path, help="Path to video file")
    parser.add_argument("-n", type=int, default=5, help="Number of frames (default: 5)")
    parser.add_argument("-t", nargs="+", metavar="TS", help="Specific timestamps (e.g. 0:15 1:30)")
    parser.add_argument("--max", type=int, default=MAX_DIMENSION, help=f"Max dimension in px (default: {MAX_DIMENSION})")
    parser.add_argument("-o", type=Path, default=None, help="Output directory")

    args = parser.parse_args()
    extract_frames(args.video, n=args.n, timestamps=args.t, max_dim=args.max, output_dir=args.o)


if __name__ == "__main__":
    main()
