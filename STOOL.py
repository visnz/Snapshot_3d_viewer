import bpy  # type: ignore
from .STOOL_part.ParentsOps import SoloPick, SoloPick_delete, P2E, P2E_individual, SelectParent, RAQtoSubparent
from .STOOL_part.StageOps import ToggleChildrenSelectability, RemoveUnusedMaterialSlots, FastCentreCamera, CSPZT_Camera, AddLightWithConstraint, OpenProjectFolderOperator, SaveSelection, LoadSelection
from .STOOL_part.AnimeOps import OBJECT_OT_add_noise_anim, NoiseAnimSettings, RemoveAllAnimations
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


### 注册类函数 ###
allClass = [
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
]


def register():
    for cls in allClass:
        bpy.utils.register_class(cls)


def unregister():
    for cls in allClass:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
