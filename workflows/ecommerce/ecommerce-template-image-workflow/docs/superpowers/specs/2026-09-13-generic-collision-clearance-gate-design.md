# Generic Collision-Clearance Gate Design

## Goal

Prevent a visually continuous component from passing QA when its path intersects, penetrates, or impossibly overlaps another solid object. The rule must apply to arbitrary products, including cables, straps, handles, hinges, zippers, hoses, chains, legs, rods, and accessories.

## Confirmed failure

The rejected mug candidate contains a continuous spoon, but the metal shaft occupies the same apparent space as the fixed puppy lid knob/body. The current report records only one overall `pass` or `fail` plus a free-form trace. It therefore proved endpoint continuity and support while silently omitting collision clearance along the middle of the path.

The two earlier candidates and the current candidate are all failed records. No image is currently approved.

## Design principles

1. Connection continuity is necessary but not sufficient.
2. Every visible instance is independently evaluated; a passing instance cannot compensate for a failing one.
3. Every instance is evaluated locally and in full-scene context.
4. Occlusion is not proof of clearance. If the image cannot distinguish ordinary front/back occlusion from solid penetration, the result fails.
5. QA status is derived from structured subchecks and cannot be asserted manually.
6. A manual `brief.md` edit cannot bypass approval or unlock the next image.

## Evidence model

Each registered visible component instance requires two distinct task-local evidence images:

- `detail_crop`: a close crop that proves endpoints, continuous segments, connectors, seams, and local geometry.
- `context_crop`: a wider crop that proves ownership, support, surrounding solids, travel direction, and the complete installed state. It may be the full candidate image, but it cannot be the same path as `detail_crop`.

Each instance also requires four structured dimensions, each with an independent `pass` or `fail` and a nonempty evidence trace:

- `topology`: endpoints, continuous body, connector sequence, ownership, and absence of breaks or residual ends.
- `support`: gravity, load path, contact shadow, bearing surface, and absence of floating or impossible cantilever states.
- `clearance`: the full path and occupied volume avoid all forbidden solid objects; only explicitly allowed contacts are present; no penetration, overlap, clipping, or fake tangent contact.
- `assembly`: the instance and surrounding components form one reconstructable, mutually compatible product state with a physically possible interaction path.

The overall instance result is derived: it passes only when all four dimensions pass. The report passes only when every required instance passes.

## CLI contract

Replace the single coarse check value with a structured per-instance record:

```text
record-visual-qa \
  --instance-check "ID|DETAIL_CROP|CONTEXT_CROP|topology=pass:TRACE|support=pass:TRACE|clearance=pass:TRACE|assembly=pass:TRACE"
```

Parsing rules:

- The instance ID must match exactly one ID in `product-identity.md`.
- Detail and context paths must be distinct, relative to the task directory, and point to nonempty files.
- All four dimensions must appear exactly once.
- Results may only be `pass` or `fail`.
- Every trace must be nonempty and dimension-specific.
- Missing, repeated, unknown, or malformed dimensions reject the report.

The Markdown report format is schema-versioned so legacy coarse reports cannot silently satisfy the stronger gate:

```markdown
# 可见部件实例质检

- 版本: 2
- 候选图: generated-image.png
- 状态: failed

## instance-id

- 细节裁图: qa/instance-detail.png
- 上下文图: qa/instance-context.png
- topology: pass | ...
- support: pass | ...
- clearance: fail | 路径与固定主体发生实体重叠
- assembly: pass | ...
- 实例结果: fail
```

## Prompt and handoff rules

The direct image prompt and web handoff add a generic occupied-volume check for every registered instance:

1. Trace endpoint A through every continuous segment and connector to endpoint B.
2. Identify the instance's support/contact surfaces.
3. Identify surrounding solid objects along the entire path.
4. Preserve visible clearance from every forbidden solid; allowed contact must be explicitly justified.
5. Treat ambiguous overlap, missing clearance, clipping, penetration, and a path hidden behind a solid without consistent entry/exit evidence as hard failures.
6. Adjust the camera or component route when clearance cannot be proven; decorative composition cannot override physical feasibility.

These rules contain no mug-, spoon-, or category-specific logic.

## Approval and sequencing

`approve-image` reloads the candidate, identity, report, detail crops, and context crops. It requires schema version 2, exact instance coverage, all four dimensions passing for every instance, and a matching candidate filename before it can set `brief.md` to `approved`.

`prepare-image` repeats the same validation for the previous task. An `approved` string without a valid version-2 report remains insufficient.

## Current image 05 application

The current candidate is recorded as failed because `notch-spoon.clearance=fail`: the spoon shaft overlaps the occupied volume of the fixed puppy knob/body. The next candidate must route the shaft through a visibly clear lane on the lid with a positive gap from the knob/body across the whole path. The candidate must be generated from the original product references only, then receive separate detail and context evidence for `center-spoon`, `notch-spoon`, and `detail-spoon`.

## Tests

Automated tests must cover:

- Missing or duplicate dimensions.
- Invalid results and empty traces.
- Same detail/context path.
- Missing, empty, or path-escaping evidence files.
- A single clearance failure forcing the instance and report to fail.
- Legacy version-1 reports being rejected by approval and sequencing.
- Candidate mismatch and instance-set mismatch.
- A fully passing four-dimension report approving the candidate and unlocking the next image.
- Prompt and handoff language requiring occupied-volume and collision-clearance checks.

The existing regression suite must remain green.
