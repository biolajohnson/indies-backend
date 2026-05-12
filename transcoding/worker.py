"""
Video transcoding pipeline for Indies.

Concepts from Havaldar & Medioni, "Multimedia Systems: Algorithms, Standards,
and Industry Practices":

  - H.264/AVC encoding (libx264): prediction → DCT → quantization → CABAC
    entropy coding. The two bitrate targets (2800k / 800k) control the
    quantisation step — lower bitrate = coarser quantisation = more loss.
    See the book's H.264 chapter on rate control.

  - GOP structure: FFmpeg defaults to a keyframe (I-frame) every 250 frames.
    I-frames are self-contained (intra-coded, no motion prediction), so they
    are what we extract for content scanning. P/B-frames depend on surrounding
    frames and would require decoding context to inspect. See the book's
    section on I/P/B frame types and Group of Pictures.

  - HLS segmentation: each .ts file is an MPEG-2 transport stream wrapping
    H.264 video + AAC audio. The 4-second segment duration is a VOD
    latency/rebuffering tradeoff — longer segments mean fewer HTTP round trips
    but slower seek response. See the book's streaming protocols section.

  - Adaptive bitrate: master.m3u8 advertises two renditions (720p, 360p).
    The client (hls.js) monitors download throughput vs. playback rate and
    switches renditions mid-stream. This is the rate adaptation model covered
    in the book's streaming chapter.
"""

import os
import shutil
import subprocess

EXPLICIT_CLASSES = {
    "EXPOSED_ANUS",
    "EXPOSED_BREAST_F",
    "EXPOSED_GENITALIA_F",
    "EXPOSED_GENITALIA_M",
    "EXPOSED_BUTTOCKS",
}
NUDENET_THRESHOLD = 0.6


def run(app, campaign_id, raw_path, hls_dir):
    """Entry point called from the background thread."""
    with app.app_context():
        from extensions import db
        from models import Campaign

        campaign = db.session.get(Campaign, campaign_id)
        try:
            os.makedirs(hls_dir, exist_ok=True)
            _transcode_to_hls(raw_path, hls_dir)

            frames_dir = os.path.join(hls_dir, "frames")
            os.makedirs(frames_dir, exist_ok=True)
            _extract_keyframes(raw_path, frames_dir)

            flagged = _scan_frames(frames_dir)
            shutil.rmtree(frames_dir)

            slug = os.path.basename(hls_dir)
            campaign.video_url = f"/api/campaigns/videos/{slug}/master.m3u8"
            campaign.video_status = Campaign.VIDEO_STATUS_FLAGGED if flagged else Campaign.VIDEO_STATUS_READY
            db.session.commit()

        except Exception:
            campaign.video_status = Campaign.VIDEO_STATUS_ERROR
            db.session.commit()
            raise

        finally:
            if os.path.exists(raw_path):
                os.remove(raw_path)


def _has_audio(raw_path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            raw_path,
        ],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _transcode_to_hls(raw_path, hls_dir):
    """
    Two-rendition HLS encode using a single decode pass (split filter).

    The filter graph forks the decoded video into two scaled copies:
      [v720] → 1280×720 @ 2800 kbps  (HD, ~2.8 Mbps)
      [v360] → 640×360  @  800 kbps  (SD, ~0.8 Mbps)

    libx264 encodes each with H.264 baseline-compatible settings.
    AAC audio at 48 kHz is muxed into both renditions.

    Output layout:
      hls_dir/master.m3u8
      hls_dir/stream_0.m3u8   (360p playlist)
      hls_dir/stream_1.m3u8   (720p playlist)
      hls_dir/stream_0_000.ts … (360p segments)
      hls_dir/stream_1_000.ts … (720p segments)
    """
    audio = _has_audio(raw_path)
    var_stream_map = "v:0,a:0 v:1,a:1" if audio else "v:0 v:1"

    cmd = [
        "ffmpeg", "-y", "-i", raw_path,
        "-filter_complex",
        "[0:v]split=2[v1][v2];[v1]scale=1280:720[v720];[v2]scale=640:360[v360]",
        "-map", "[v720]",
        "-c:v:0", "libx264", "-b:v:0", "2800k",
        "-map", "[v360]",
        "-c:v:1", "libx264", "-b:v:1", "800k",
    ]

    if audio:
        cmd += [
            "-map", "0:a", "-c:a:0", "aac", "-ar", "48000",
            "-map", "0:a", "-c:a:1", "aac", "-ar", "48000",
        ]

    cmd += [
        "-f", "hls",
        "-hls_time", "4",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", os.path.join(hls_dir, "stream_%v_%03d.ts"),
        "-master_pl_name", "master.m3u8",
        "-var_stream_map", var_stream_map,
        os.path.join(hls_dir, "stream_%v.m3u8"),
    ]

    subprocess.run(cmd, check=True, capture_output=True)


def _extract_keyframes(raw_path, frames_dir):
    """
    Extract one frame every 10 seconds for content scanning.

    fps=1/10 produces approximately one frame per 10-second interval.
    These tend to land on or near I-frames because FFmpeg must fully decode
    the nearest preceding keyframe to reconstruct any given frame. For
    content moderation purposes, one frame per 10 seconds is sufficient to
    catch explicit material without scanning thousands of frames.
    """
    cmd = [
        "ffmpeg", "-y", "-i", raw_path,
        "-vf", "fps=1/10",
        "-q:v", "2",
        os.path.join(frames_dir, "frame_%04d.jpg"),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _scan_frames(frames_dir):
    """
    Run NudeNet on each extracted frame. Returns True if any frame is flagged.

    NudeNet uses an ONNX model to detect explicit body-part classes.
    We only flag on classes that are unambiguously explicit (no partial/covered
    classes) and require a confidence score above NUDENET_THRESHOLD (0.6) to
    reduce false positives on e.g. nude art or partially clothed subjects.
    """
    from nudenet import NudeDetector
    detector = NudeDetector()

    for fname in sorted(os.listdir(frames_dir)):
        if not fname.lower().endswith(".jpg"):
            continue
        detections = detector.detect(os.path.join(frames_dir, fname))
        for det in detections:
            if det["class"] in EXPLICIT_CLASSES and det["score"] > NUDENET_THRESHOLD:
                return True
    return False
