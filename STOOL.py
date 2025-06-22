
import bpy  # type: ignore
from .STOOL_part.ParentsOps import SoloPick, SoloPick_delete, P2E, P2E_individual, SelectParent, RAQtoSubparent
from .STOOL_part.StageOps import ToggleChildrenSelectability, RemoveUnusedMaterialSlots, FastCentreCamera, CSPZT_Camera, AddLightWithConstraint, OpenProjectFolderOperator, SaveSelection, LoadSelection
from .STOOL_part.AnimeOps import OBJECT_OT_add_noise_anim, NoiseAnimSettings, RemoveAllAnimations
from .STOOL_part.RenderOps import RenderPresetSettings, RENDER_OT_create_presets, RENDER_OT_apply_preset
from bpy.props import PointerProperty  # type: ignore
### 面板类函数 ###


class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "SomeTools"
    bl_idname = "view_snapshot_panel_sometools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout

        layout.separator()
        layout.label(text="父子级")
        layout.operator("object.parent_to_empty_visn")
        layout.operator("object.parent_to_empty_visn_individual")
        layout.operator("object.select_parent_visn")
        layout.operator("object.release_all_children_to_subparent_visn")
        layout.operator("object.solo_pick_visn")
        layout.operator("object.solo_pick_delete_visn")

        layout.separator()
        layout.label(text="搭建类")
        layout.operator("object.fast_camera_visn")
        layout.operator("object.cspzt_camera_visn")
        layout.operator("object.add_light_with_constraint")
        layout.operator("wm.open_project_folder_visn")
        layout.operator("object.save_selection_visn")
        layout.operator("object.load_selection_visn")
        layout.operator("object.remove_unused_material_slots_visn")
        layout.operator("object.toggle_children_selectability_visn")

        layout.separator()
        layout.label(text="动画类")
        layout.operator("object.add_noise_anim", text="Wiggle（添加/更新Noise）")
        layout.operator("object.remove_all_animations_visn")

        # 新增的渲染预设管理部分
        layout.separator()
        layout.label(text="渲染预设")

        # 创建预设按钮
        layout.operator("render.create_presets", text="创建预设", icon='SETTINGS')

        # 路径类型切换按钮
        props = context.scene.render_preset_settings
        row = layout.row()
        row.prop(props, "use_absolute_path", text="使用绝对路径", toggle=True)

        # 预设应用按钮
        box = layout.box()
        row = box.row(align=True)
        row.operator("render.apply_preset", text="HD").preset_type = 'HD'
        row.operator("render.apply_preset", text="Style").preset_type = 'Style'

        row = box.row(align=True)
        row.operator("render.apply_preset", text="prev").preset_type = 'prev'
        row.operator("render.apply_preset", text="demo").preset_type = 'demo'

        # 使用提示
        # layout.label(text="按住Alt应用到所有场景", icon='INFO')


### 注册类函数 ###
allClass = [
    RenderPresetSettings,
    ToggleChildrenSelectability,
    RemoveAllAnimations,
    RemoveUnusedMaterialSlots,
    VIEW3D_PT_SnapshotPanel,
    FastCentreCamera,
    CSPZT_Camera,
    SoloPick,
    SoloPick_delete,
    SelectParent,
    RAQtoSubparent,
    OpenProjectFolderOperator,
    AddLightWithConstraint,
    SaveSelection,
    LoadSelection,
    P2E,
    P2E_individual,
    OBJECT_OT_add_noise_anim,
    NoiseAnimSettings,
    # ----------
    RENDER_OT_create_presets,
    RENDER_OT_apply_preset,
]


def register():
    for cls in allClass:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_preset_settings = PointerProperty(
        type=RenderPresetSettings)


def unregister():
    for cls in allClass:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.render_preset_settings


if __name__ == "__main__":
    register()
