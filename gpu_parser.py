import os
import glob
import time
import torch
from faster_whisper import WhisperModel

# -------------------------
# CONFIG
# -------------------------
MODEL_SIZE = "medium"
TRANSCRIPTS_DIR = "./all_transcripts"
EPISODES_DIR = "history_of_rome_episodes"

# Ensure output directory exists
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

# Force GPU (CUDA), fallback to CPU if not available
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"✓ Using device: {DEVICE} ({torch.cuda.get_device_name(0) if DEVICE == 'cuda' else 'CPU'})")

# Load Faster-Whisper model
# compute_type="float16" speeds up GPU (if supported), fallback to "int8" for CPU
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="float16" if DEVICE == "cuda" else "int8")

# Gather MP3 files
mp3_files = glob.glob(os.path.join(EPISODES_DIR, "*.mp3"))
mp3_files.sort()
mp3_files.reverse()  # start from last episode

# -------------------------
# TRANSCRIBE FUNCTION
# -------------------------
def transcribe_episode(audio_file_path, output_file_path):
    """Transcribe a single episode and save with timestamps"""
    try:
        print(f"🎙️ Transcribing: {os.path.basename(audio_file_path)}")
        start_time = time.time()

        # Run transcription
        segments, info = model.transcribe(
            audio_file_path,
            beam_size=3,
            language="en"
        )

        language = info.language
        duration = info.duration

        # Write results with timestamps
        with open(output_file_path, "w", encoding="utf-8") as f:
            episode_name = os.path.basename(audio_file_path).replace('.mp3', '')
            f.write(f"# {episode_name}\n")
            f.write(f"# Detected language: {language}\n")
            f.write(f"# Duration: {duration:.2f} seconds\n")
            f.write(f"# Model: {MODEL_SIZE}, Device: {DEVICE}\n\n")

            segment_count = 0
            for segment in segments:
                start_min, start_sec = divmod(int(segment.start), 60)
                end_min, end_sec = divmod(int(segment.end), 60)
                timestamp = f"[{start_min:02d}:{start_sec:02d} --> {end_min:02d}:{end_sec:02d}]"
                line = f"{timestamp} {segment.text.strip()}"
                f.write(line + "\n")
                segment_count += 1

        elapsed_time = time.time() - start_time
        file_size = os.path.getsize(output_file_path) / 1024  # KB
        print(f"✓ Completed in {elapsed_time:.1f}s: {os.path.basename(output_file_path)} "
              f"({file_size:.1f} KB, {segment_count} segments)")
        return True

    except Exception as e:
        print(f"✗ Failed to transcribe {os.path.basename(audio_file_path)}: {str(e)}")
        if os.path.exists(output_file_path):
            os.remove(output_file_path)
        return False


# -------------------------
# MAIN LOOP
# -------------------------
if len(mp3_files) > 0:
    print(f"\nStarting transcription of {len(mp3_files)} episodes on {DEVICE.upper()}...")
    print("=" * 70)

    successful_transcriptions = 0
    failed_transcriptions = 0
    total_start_time = time.time()

    for i, mp3_file in enumerate(mp3_files, 1):
        episode_name = os.path.basename(mp3_file).replace('.mp3', '')
        output_file = os.path.join(TRANSCRIPTS_DIR, f"{episode_name}.txt")

        print(f"\n[{i}/{len(mp3_files)}] Processing: {episode_name}")

        if transcribe_episode(mp3_file, output_file):
            successful_transcriptions += 1
        else:
            failed_transcriptions += 1

        time.sleep(1)

    total_elapsed = time.time() - total_start_time

    print("\n" + "=" * 70)
    print(f"Transcription Summary:")
    print(f"✓ Successful: {successful_transcriptions}")
    print(f"✗ Failed: {failed_transcriptions}")
    print(f"⏱️ Total time: {total_elapsed/60:.1f} minutes")
    print(f"📁 Transcripts saved to: {os.path.abspath(TRANSCRIPTS_DIR)}")

    transcript_files = [f for f in os.listdir(TRANSCRIPTS_DIR) if f.endswith('.txt')]
    print(f"\nCompleted transcripts ({len(transcript_files)} files):")
    for file in sorted(transcript_files)[:10]:
        file_path = os.path.join(TRANSCRIPTS_DIR, file)
        file_size = os.path.getsize(file_path) / 1024
        print(f"  • {file} ({file_size:.1f} KB)")
    if len(transcript_files) > 10:
        print(f"  ... and {len(transcript_files) - 10} more files")
else:
    print("No MP3 files to process!")
