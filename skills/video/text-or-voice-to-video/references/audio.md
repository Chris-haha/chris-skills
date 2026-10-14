# Optional music and caption-anchored sound effects

The canonical voice remains the timing authority. Mixing adds other stems at sample zero without trimming, moving, resampling, normalizing, compressing, or changing the gain of that canonical voice. The mix is mono PCM16 with exactly the canonical sample rate and sample count. Existing commands without `--mix` retain the pure-voice workflow.

## `audio-plan.json` contract (schema version 1)

```json
{
  "schemaVersion": 1,
  "voiceSha256": "SHA256_OF_CANONICAL_WAV",
  "timelineSha256": "SHA256_OF_CURRENT_TIMELINE_JSON",
  "bgm": {
    "path": "assets/music.wav",
    "sha256": "SHA256_OF_MUSIC_FILE",
    "volume": 0.12,
    "fadeInMs": 300,
    "fadeOutMs": 600,
    "loop": true,
    "ducking": {
      "thresholdDbfs": -35,
      "gain": 0.25,
      "attackMs": 20,
      "releaseMs": 250
    }
  },
  "sfx": [
    {
      "id": "reveal-accent",
      "path": "assets/accent.wav",
      "sha256": "SHA256_OF_EFFECT_FILE",
      "anchorUnit": "unit-004",
      "offsetMs": 40,
      "volume": 0.4
    }
  ]
}
```

Paths are relative to the plan file; absolute paths also work. Hashes are file SHA-256 hashes, not decoded PCM hashes. Compute them with `shasum -a 256 <file>` or `common.sha256`. The plan requires both voice and timeline hashes. When narration, reviewed caption timings, caption IDs, or the timeline changes, refresh the plan hashes only after checking the anchors again. The timeline itself must pass the existing ASR provenance validation.

`bgm` may be omitted or `null`; `sfx` may be omitted or `[]`. Every source needs a path and matching hash. Unknown fields are rejected, including absolute SFX timing fields such as `startMs`. Each effect needs a unique nonempty `id` and an `anchorUnit` matching a **current timeline caption `id`**. Its start sample is `round((caption.startMs + offsetMs) * sampleRate / 1000)`; negative offsets are allowed only when the complete event still fits inside the voice. Effects play once at their original decoded length, after mono decoding/resampling to the voice rate. They cannot extend beyond the voice end and are never silently trimmed.

Volumes are linear gains (0–100, finite). BGM volume defaults to `0.1`; effect volume defaults to `1`. Fade values default to zero, must be finite and nonnegative, and together must fit within the voice duration. Music starts at zero, is cropped to the voice length if longer, and repeats if shorter with `loop: true` (the default). `loop: false` pads a short music file with silence. Choose a seamless source when looping; the mixer does not crossfade loop joins.

Ducking is always applied to included BGM. It measures voice RMS in 10 ms windows against `thresholdDbfs` (-120–0, default -35), approaches the speech gain (`gain`: 0–1, default 0.25) with an exponential attack, and returns toward gain 1 with an exponential release. The window gains are interpolated across samples. Attack/release times must be positive and finite (defaults 20/250 ms, maximum 60000 ms). This is an energy envelope, not linguistic speech detection: pauses release music, while loud non-speech sounds in the voice can also duck it. BGM fades apply to the whole composition, after looping/cropping.

The mixer rejects any combined sample outside PCM16 range (-1 to 32767/32768). It does not normalize the voice or silently limit peaks. Reduce BGM/effect gains if rejected. PCM addition requires ordinary final PCM16 rounding; the voice stem itself remains at gain 1 and offset 0. Voice-only output samples are bit exact. AAC encoding can create overshoot; the final verification separately rejects decoded peaks above its existing full-scale tolerance.

## Commands

Run from a project directory with a current canonical voice and validated timeline:

```sh
python <skill>/scripts/mix_audio.py \
  --voice out/audio/canonical.wav --timeline timeline.json \
  --plan audio-plan.json --output out/audio/mix.wav --dry-run

python <skill>/scripts/mix_audio.py \
  --voice out/audio/canonical.wav --timeline timeline.json \
  --plan audio-plan.json --output out/audio/mix.wav \
  --no-bgm-output out/audio/mix-no-bgm.wav

python <skill>/scripts/mux_audio.py \
  --video out/silent.mp4 --voice out/audio/canonical.wav \
  --mix out/audio/mix.wav --timeline timeline.json --output out/final.mp4

python <skill>/scripts/verify_media.py \
  --video out/final.mp4 --voice out/audio/canonical.wav \
  --mix out/audio/mix.wav --output-dir out/verification
```

`--dry-run` fully validates provenance, decodes sources, resolves anchors, computes the envelopes/mix and checks peaks, but writes no audio or sidecars. Its JSON output describes the proposed mix. This avoids accepting plans that only fail when actually mixed.

`--no-bgm-output` writes a second mix that retains the same voice and all SFX, with the BGM excluded. All variants are checked before any output is written. Outputs and their manifests may not collide with each other, voice, plan, timeline, BGM/SFX or the timeline's recorded provenance inputs; existing hard links and symlinks are checked too.

Each mix gets an adjacent `.mix.json` sidecar (for example `mix.wav` → `mix.mix.json`, `mix-no-bgm.wav` → `mix-no-bgm.mix.json`). It records voice/hash/sample rate/sample count, unchanged stem/gain 1/zero sample offset, plan and timeline paths/hashes, source hashes, gains, fades, ducking parameters and observed range, each caption anchor and resolved sample range, the omission variant, peak, and output hash.

Muxing with `--mix` requires that sidecar and verifies every recorded hash and voice field. It rebuilds the expected mix from the pinned plan and sources and compares PCM exactly; updating an output hash alone cannot bless altered voice or shifted audio. The voice still determines video frame count and the permitted trailing silence padding. When `--timeline` is supplied alongside `--mix`, its file hash must match the timeline pinned by the mix manifest; a different valid timeline cannot reuse effects placed against old captions. Omitting `--timeline` intentionally uses the pinned mix timeline. Identical timeline bytes at another path are accepted. Mux metadata also records the selected mix and manifest hashes.

Verification with `--mix` independently repeats the same provenance/rebuild check and compares encoded AAC against the **mix PCM**, using the existing beginning/middle/end correlation, lag, drift, decoded tail, peak, full audio decode and full video decode checks. It separately reports `voiceValidated`, `pcmRebuildValidated`, voice gain 1 and voice offset 0. The verifier uses the timeline pinned in the mix manifest; it does not accept a separate caller timeline. To check a current caller timeline, supply it to mux with `--timeline` before verifying the resulting file. Without `--mix`, both the Python API (`mux(..., timeline_path=None)`, `verify(video, voice)`) and CLI continue to compare/mux pure voice.

Keep the pinned plan, timeline, ASR binding and source files available for mux/verification. Deterministic rebuild uses the installed ffmpeg decoder, so use the same ffmpeg build throughout a project. The mixer works in memory, uses mono downmixing, and does not synthesize music/effects, acquire licenses, perform LUFS mastering, or perform perceptual listening QA. Listen to the final mix and the no-BGM variant before delivery.
