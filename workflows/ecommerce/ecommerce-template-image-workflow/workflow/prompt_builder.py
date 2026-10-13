from __future__ import annotations

from typing import Sequence
from pathlib import Path
from typing import Any

from workflow.geometry import geometry_prompt_section, validate_geometry_preflight
from workflow.models import DisplayCopy, ProductIdentity, TemplateRecord
from workflow.projects import ProjectError, validate_product_identity, validate_truth_sources
from workflow.templates import template_reference_paths


def _list_items(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- 无"


def build_direct_image_prompt(
    template: TemplateRecord,
    product_references: Sequence[str],
    objective: str,
    display_copy: DisplayCopy | None = None,
    product_identity: ProductIdentity | None = None,
    geometry_preflight: dict[str, Any] | None = None,
) -> str:
    """Build a final Chinese instruction for an image model, not a meta prompt."""
    if product_identity is None:
        raise ProjectError("缺少产品一致性清单，禁止生成直接生图提示词")
    validate_product_identity(product_identity)
    validate_truth_sources(product_identity, product_references)
    validate_geometry_preflight(geometry_preflight, product_identity, objective)
    geometry_section = geometry_prompt_section(geometry_preflight)
    identity_section = f"""## 产品一致性硬约束

唯一事实依据（最高优先级）：
{_list_items(product_identity.truth_sources)}

只允许从上述原始产品图读取产品外形、结构、材质、颜色、表面图案和印刷等事实。模板图只负责版式与视觉语言；历史生成图不得作为产品事实依据，也不得补充、覆盖或纠正原始产品图。

表面图案与印刷：
{_list_items(product_identity.surface_graphics)}

逐项保持图案元素、可见文字、数量、顺序、位置、朝向、相对比例和线条造型；不得增删、替换、重排或风格化改写。无法从原始产品图确认时必须停止，不得近似复刻或猜测。

物理与支撑关系：
{_list_items(product_identity.physical_constraints)}

所有物体必须遵循重力并由真实接触面稳定支撑，不得无支撑悬空、违反重力、穿透实体或处于明显会滑落、倾倒的姿态。手持或运动中的部件必须有明确施力与支撑来源；无人接触的静置部件必须由桌面、容器壁、杯盖、卡槽或清单指定的真实接触面承重。构图美观不能覆盖物理真实性。

人物与动作可行性：
{_list_items(product_identity.human_interaction_constraints)}

画面中的人物或手必须属于清单指定数量的真实操作者。左右手身份、拇指方向、手掌朝向、手腕旋转、手臂进场方向、握持点、关节活动范围和动作时序必须解剖合理，并且同一人可独立完成。不得生成镜像手、重复手、两个同侧手、错接手腕、反关节、不可能抓握、跨越不可达路径或互相冲突的同步动作。单手可以完成时优先只展示一只手；若清单声明无人物，则禁止生成任何手部或人体。

部件与精确数量：
{_list_items(product_identity.components)}

连接与从属关系：
{_list_items(product_identity.relationships)}

可见连接证据：
{_list_items(product_identity.visible_connection_evidence)}

每条关键连接必须在最终画面中留下可追踪的视觉证据。逐条从可见端点追踪到连接件、连续段、遮挡边界和所属主体；连接头、套环、铰链、接缝或清单指定的证据必须清晰可见。遮挡可以隐藏中段，但遮挡前后必须出现方向一致的入口与出口，且连接段不能在边界前凭空终止。相邻、相切或叠放不能冒充固定连接；不得让固定部件看起来像可独立移动的摆件。若当前机位无法证明连接，必须调整角度或增加同一产品的局部特写，不得用遮挡掩盖、猜测或批准。

功能结构（孔、槽、缺口、卡扣、铰链、通道及其位置和用途）：
{_list_items(product_identity.functional_features)}

必须呈现的使用状态与部件交互：
{_list_items(product_identity.required_use_states)}

装配状态证据：
{_list_items(product_identity.assembly_state_evidence)}

同一功能交互中的主体与参与部件必须处于同一个真实装配状态。已拆卸部件不能同时演示只有安装后才成立的使用关系。功能通道必须保持原始开放边界，不得生成封闭孔洞、桥状假结构或实体穿透。进入容器的部件必须从容器开口或已经确认的功能通道进入，遮挡方向必须与进入路径一致。无法同时证明装配状态和交互路径时，必须调整机位或取消该交互演示。

可见部件实例（同一物理部件每次出现在画面中都必须单独登记）：
{_list_items(product_identity.visible_component_instances)}

每个可见部件实例必须独立验收；其他实例正确不能抵消当前实例失败。逐段检查起点、连续结构、连接件、终点、遮挡边界、所属主体与支撑来源。断口、残端、两截错位、凭空终止、穿透、错误归属或用相切叠放冒充连接，任一出现即整图失败。

对每个实例建立完整路径与占用空间：先追踪端点、连续段和连接件，再标记允许接触面与沿途禁止相交实体。整条路径必须保持可见净空（路径净空），不得与其他固体重叠、裁切、穿透或用相切伪装连接。遮挡只有在入口、出口、方向和前后层级一致时才成立；无法区分正常遮挡与实体穿透时直接判定失败。必须调整机位或路径来证明净空，装饰性构图不能覆盖物理可行性。

画框填充与安全裁切：产品画面必须填满预定媒体框，不得暴露占位底色、上下或左右空白带，也不得拉伸产品来强行填充。关键主体、部件、表面图案和功能结构必须完整保留；如果原图比例与画框比例无法同时满足填满和主体完整，必须先调整画框比例或版式，不得用留白、变形或危险裁切掩盖比例冲突。

明确不存在、严禁生成：
{_list_items(product_identity.forbidden_inventions)}

严格按以上清单生成；不得拆分、复制、合并或新增任何产品部件。不得省略、封闭、平滑或改变功能结构，不得把部件改成另一种看似合理但未经确认的装配状态。参考图角度、摆放或遮挡造成歧义时，以本清单为准，不得猜测。
"""
    copy_section = ""
    text_rule = "不要生成可读文字或乱码文字；"
    if display_copy is not None:
        copy_lines = [
            "## 必须准确呈现的详情图展示文案",
            "",
            f"- 文案语言：{display_copy.language}",
            f"- 主标题：{display_copy.headline}",
        ]
        if display_copy.subheadline:
            copy_lines.append(f"- 副标题：{display_copy.subheadline}")
        copy_lines.extend(f"- 卖点短标签：{label}" for label in display_copy.labels)
        copy_section = "\n".join(copy_lines) + "\n\n"
        text_rule = (
            "将以上展示文案逐字清晰排版在模板指定的文案安全区；"
            "不要翻译、改写、遗漏、添加其他可读文字或生成乱码；"
        )
    return f"""直接生成一张图片，不要分析过程，不要输出提示词。

图片目标：{objective}
图片用途：{template.role}
画幅比例：{template.aspect_ratio}（建议输出尺寸 {template.output_size}）

必须参考的产品图：
{_list_items(product_references)}

必须参考的模板图：
{_list_items([str(path) for path in template_reference_paths(Path("template-library"), template)])}

按模板保持以下视觉结构：
- 版式：{template.layout}
- 文案安全区：{template.copy_safe_zone}
- 风格：{template.style}
- 场景：{template.scene}

{identity_section}

{geometry_section}

{copy_section}

仅复用模板的版式和视觉语言，按当前产品类别替换参考图中的场景、关联物和配色；不得照搬模板参考图中的产品、品类或道具。

锁定唯一事实依据中的外形、比例、材质、颜色、部件、表面图案、印刷与可见细节。不要让产品变形；不要重绘或生成包装上的 Logo、包装文字、营养成分表、条码或法规标签。{text_rule}不要添加无关道具、水印或界面；不要加入没有依据的功效、对比或其他视觉宣称。"""
