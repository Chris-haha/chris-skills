# Audio subsystem red/green evidence

Work took place only in the staged `candidate-skill` scripts and these reference documents. No installed skill was modified.

Test command, run from `/Volumes/Samsung_T5/code/test-video/work/visual-story-upgrade-20261013/candidate-skill`:

```sh
PATH=/Volumes/Samsung_T5/code/test-video/work/text-video-skill-upgrade/bin:$PATH \
DYLD_LIBRARY_PATH=/Volumes/Samsung_T5/code/test-video/work/manuscript-motion/node_modules/@remotion/compositor-darwin-arm64 \
/Volumes/Samsung_T5/code/test-video/work/text-video-skill-upgrade/.venv/bin/python \
-m unittest discover -s scripts/tests -p test_mix_audio.py -v
```

The initial test-first run failed four positive behavior tests because `mix_audio.py` did not exist. After implementing the mixer, five of six tests passed, and the real mux integration failed because `mux_audio.py` did not yet recognize `--mix`. After adding the optional mix argument to mux and verifier, all six passed. Additional negative/provenance tests expanded the audio suite to nine passing tests. A final test-first malformed-manifest check reproduced four type errors and one incorrectly accepted boolean schema version; adding explicit object/path/version validation made all nine audio tests pass (4.010 seconds). These use real WAV decoding/resampling, mono PCM output, ffmpeg H.264/AAC muxing and ffprobe/full output decoding; audio tools are not mocked.

Covered behaviors: voice-only bit-exact samples; dry-run writing nothing; exact voice-driven sample rate/count; anchored SFX; no-BGM output retaining SFX; energy envelope ducking and endpoint fades; stale voice/timeline/source hashes; stale anchors; retiming requiring plan refresh then moving the effect; nonfinite numbers and invalid gains/fades; arbitrary absolute timing; events before zero or after the voice end; clipping rejection; output/sidecar/hard-link collisions; changed source files; altered mix PCM with a forged updated output hash; incorrect mix rate/count; forged voice gain/offset; malformed manifest objects and schema versions; real mux and encoded mix verification.

Full regression command:

```sh
PATH=/Volumes/Samsung_T5/code/test-video/work/text-video-skill-upgrade/bin:$PATH \
DYLD_LIBRARY_PATH=/Volumes/Samsung_T5/code/test-video/work/manuscript-motion/node_modules/@remotion/compositor-darwin-arm64 \
/Volumes/Samsung_T5/code/test-video/work/text-video-skill-upgrade/.venv/bin/python \
-m unittest discover -s scripts/tests -v
```

Full run result at the audio subsystem verification checkpoint: **77 tests passed in 10.878 seconds**. This includes the existing long pure-voice mux/alignment tests, known 80 ms shift rejection and real corrupt AAC-tail rejection. Other parallel work can add more tests after this checkpoint; rerun the same command for the current staged skill.

Python syntax verification also passed:

```sh
/Volumes/Samsung_T5/code/test-video/work/text-video-skill-upgrade/.venv/bin/python \
-m py_compile scripts/mix_audio.py scripts/mux_audio.py scripts/verify_media.py scripts/tests/test_mix_audio.py
```

## Supplied current timeline regression

Review found that a valid separately supplied timeline could differ from the mix's pinned timeline. The new real ffmpeg regression shifts a caption start by 50 ms in a second valid timeline, retains the old mix/manifest/plan, and attempts muxing with that current timeline. The test first failed because mux returned exit 0 and wrote the stale-timed result. The fix checks the supplied timeline hash against the mix manifest before any mux output. Matching timeline bytes at another path and omission of an explicit timeline are also checked and accepted.

The same audio command above now passes **10 tests in 4.749 seconds**. Full regression was rerun with the same environment and `-m unittest discover -s scripts/tests -q`: **78 tests passed in 12.517 seconds**. Verification remains manifest-only; the contract documents that a caller's current timeline should be supplied to mux for the explicit current-timing check.
