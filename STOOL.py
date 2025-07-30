import bpy  # type: ignore
from .STOOL_part.ParentsOps import SoloPick, SoloPick_delete, P2E, P2E_individual, SelectParent, RAQtoSubparent
from .STOOL_part.StageOps import ToggleChildrenSelectability, FastCentreCamera, CSPZT_Camera, AddLightWithConstraint, OpenProjectFolderOperator, SaveSelection, LoadSelection
from .STOOL_part.AnimeOps import OBJECT_OT_add_noise_anim, NoiseAnimSettings, RemoveAllAnimations
from .STOOL_part.RenderOps import RenderPresetSettings, RENDER_OT_create_presets, RENDER_OT_apply_preset, RENDER_OT_open_output_folder
from .STOOL_part.TextureOps import TextureSearchProperties, INDEX_OT_build_texture_index, INDEX_OT_find_materials, INDEX_OT_select_objects_with_texture
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
        props = context.scene.texture_search_props

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
        layout.operator("object.toggle_children_selectability_visn")

        layout.separator()
        layout.label(text="灯光类")
        # 建立索引按钮
        layout.operator("index.build_texture_index")
        # 图片选择下拉菜单
        layout.label(text="选择要查找的贴图:")
        layout.prop_search(props, "texture_search_image",
                           bpy.data, "images", text="")
        # 查找按钮
        layout.operator("index.find_materials")
        # 新增的选择物体按钮
        layout.operator("index.select_objects_with_texture",
                        text="选中该贴图的材质对象", icon='OBJECT_DATA')

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
        layout.operator("render.open_output_folder",
                        text="打开输出文件夹", icon='FILE_FOLDER')


### 注册类函数 ###
allClass = [
    RenderPresetSettings,
    ToggleChildrenSelectability,
    RemoveAllAnimations,
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
    RENDER_OT_open_output_folder,
    # ----------
    TextureSearchProperties,
    INDEX_OT_build_texture_index,
    INDEX_OT_find_materials,
    INDEX_OT_select_objects_with_texture,
]


def register():
    for cls in allClass:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_preset_settings = PointerProperty(
        type=RenderPresetSettings)
    bpy.types.Scene.texture_search_props = PointerProperty(
        type=TextureSearchProperties)


def unregister():
    for cls in allClass:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.render_preset_settings
    del bpy.types.Scene.texture_search_props


if __name__ == "__main__":
    register()
