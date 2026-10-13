from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InboxSet:
    """One isolated batch/set of locally copied template source images."""

    batch_id: str
    set_id: str
    platform: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class TemplateMetadata:
    """Product-neutral structural and transfer-boundary tags for one module."""

    role: str
    aspect_ratio: str
    output_size: str
    layout: str
    copy_safe_zone: str
    style: str
    scene: str
    suitable_for: tuple[str, ...]
    avoid_for: tuple[str, ...]
    product_position: str
    copy_density: str
    card_count: int
    scene_type: str
    non_transferable_elements: tuple[str, ...]


@dataclass(frozen=True)
class ModuleDraft:
    """One reviewable module candidate from one isolated inbox set."""

    module_id: str
    source_images: tuple[str, ...]
    metadata: TemplateMetadata


@dataclass(frozen=True)
class TemplateSetDraft:
    """The user-reviewable classification draft for one inbox set."""

    template_set_id: str
    platform: str
    modules: tuple[ModuleDraft, ...]
    overall_style: str = ""
    merge_suggestions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class TemplateRecord:
    template_id: str
    platform: str
    role: str
    aspect_ratio: str
    output_size: str
    layout: str
    copy_safe_zone: str
    style: str
    scene: str
    suitable_for: list[str]
    avoid_for: list[str]
    references: list[str]
    template_set_id: str | None = None
    module_id: str | None = None
    metadata: TemplateMetadata | None = None


@dataclass(frozen=True)
class DisplayCopy:
    """Approved text for the layout outside the protected product package."""

    language: str
    headline: str
    subheadline: str | None = None
    labels: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProductIdentity:
    """User-approved product source, surface, inventory, geometry, and use-state lock."""

    truth_sources: tuple[str, ...]
    surface_graphics: tuple[str, ...]
    physical_constraints: tuple[str, ...]
    human_interaction_constraints: tuple[str, ...]
    components: tuple[str, ...]
    relationships: tuple[str, ...]
    visible_connection_evidence: tuple[str, ...]
    functional_features: tuple[str, ...]
    required_use_states: tuple[str, ...]
    assembly_state_evidence: tuple[str, ...]
    visible_component_instances: tuple[str, ...]
    forbidden_inventions: tuple[str, ...]
    unknowns: tuple[str, ...] = ()
    approved: bool = False
