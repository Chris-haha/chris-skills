# Product Functional Lock Design

## Problem

The current identity lock records component counts, ownership relationships, forbidden inventions, and unknowns. It cannot explicitly record functional geometry such as notches, holes, slots, hinges, channels, or the intended assembled/use state. A generation can therefore contain the right parts but still remove a critical feature or arrange those parts incorrectly.

For the puppy mug, the missing fact is not another component: the lid rim has a spoon-rest notch. In the correct closed-lid state, the spoon shaft passes through that notch, the spoon bowl remains inside the mug, and the connected brown rounded handle end stays outside the lid.

## Chosen Design

Extend `ProductIdentity` with two required collections:

- `functional_features`: product geometry whose purpose must be preserved, including its location and the part it serves.
- `required_use_states`: approved assembly or use-state relationships that the generated image must show.

The Markdown identity file gains `功能结构` and `必须呈现的使用状态` sections. Both must contain at least one explicit entry. If a product has no special mechanism, the entry must say that this was checked (for example, `无特殊孔槽或活动结构；按参考图保持标准外形`) rather than leaving the section empty.

The CLI gains repeatable `--functional-feature` and `--use-state` arguments. Handoff and generation remain blocked when the file is missing, unapproved, unresolved, or missing either new category.

## Prompt and Review Behavior

The direct image prompt lists functional geometry and required use states as hard constraints beside component counts. It explicitly forbids smoothing over a notch, changing its location, or arranging interacting parts in another plausible-looking state.

The handoff review checklist independently checks:

1. component counts;
2. ownership/connection relationships;
3. functional geometry and location;
4. required assembled/use state;
5. forbidden inventions.

Any failure blocks approval of the current image.

## Compatibility

Older identity files without the two new sections are intentionally rejected at generation time. This is a safety migration: the operator must re-inspect the reference views and explicitly record whether special functional geometry exists.

## Puppy Mug Acceptance Criteria

- The lid rim visibly retains the dedicated spoon-rest notch.
- The lid is seated on the mug.
- The one complete spoon is installed through the notch: bowl inside, continuous shaft through the notch, one brown rounded handle end outside.
- The brown rounded end is visibly connected to the shaft and is not presented as a lid ornament.
- The puppy knob remains the lid's only fixed decorative knob.
- No second spoon, detached sphere, duplicated shaft, or invented lid ornament appears.
