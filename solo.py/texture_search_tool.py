import bpy
from bpy.props import StringProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup

bl_info = {
    "name": "Texture Search Tool",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > UI > Texture Search",
    "description": "贴图搜索和材质查找工具",
    "category": "3D View",
}


class TextureSearchProperties(PropertyGroup):
    texture_search_image: StringProperty(
        name="贴图",
        description="选择要查找的贴图",
        default=""
    )


# 全局变量存储索引结果
texture_material_index = {}


class INDEX_OT_build_texture_index(Operator):
    bl_idname = "texture_search.build_texture_index"
    bl_label = "建立/刷新贴图索引"
    bl_description = "扫描所有材质并建立贴图与材质的对应关系索引"

    def execute(self, context):
        global texture_material_index
        texture_material_index = {}

        # 遍历所有材质
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                continue

            # 遍历材质节点
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    image_name = node.image.name

                    # 添加到索引
                    if image_name not in texture_material_index:
                        texture_material_index[image_name] = []

                    if mat.name not in texture_material_index[image_name]:
                        texture_material_index[image_name].append(mat.name)

        self.report({'INFO'}, f"索引建立完成，共索引 {len(texture_material_index)} 张贴图")
        return {'FINISHED'}


class INDEX_OT_find_materials(Operator):
    bl_idname = "texture_search.find_materials"
    bl_label = "查找使用贴图的材质"
    bl_description = "查找使用选定贴图的所有材质"

    def execute(self, context):
        props = context.scene.texture_search_props
        selected_image = props.texture_search_image
        global texture_material_index

        if not texture_material_index:
            self.report({'WARNING'}, "请先建立贴图索引!")
            return {'CANCELLED'}

        if not selected_image:
            self.report({'WARNING'}, "请选择一张贴图!")
            return {'CANCELLED'}

        if selected_image not in texture_material_index:
            self.report({'INFO'}, f"贴图 '{selected_image}' 未被任何材质使用")
            return {'FINISHED'}

        materials = texture_material_index[selected_image]
        self.report(
            {'INFO'}, f"贴图 '{selected_image}' 被以下材质使用: {', '.join(materials)}")

        # 打印到控制台
        print(f"\n贴图 '{selected_image}' 使用情况:")
        for mat in materials:
            print(f"- {mat}")

        return {'FINISHED'}


class INDEX_OT_select_objects_with_texture(Operator):
    bl_idname = "texture_search.select_objects_with_texture"
    bl_label = "选中使用贴图的物体"
    bl_description = "选中所有使用该贴图的物体"

    def execute(self, context):
        props = context.scene.texture_search_props
        selected_image = props.texture_search_image
        global texture_material_index

        if not texture_material_index:
            self.report({'WARNING'}, "请先建立贴图索引!")
            return {'CANCELLED'}

        if not selected_image:
            self.report({'WARNING'}, "请选择一张贴图!")
            return {'CANCELLED'}

        if selected_image not in texture_material_index:
            self.report({'INFO'}, f"贴图 '{selected_image}' 未被任何材质使用")
            return {'FINISHED'}

        # 取消所有当前选择
        bpy.ops.object.select_all(action='DESELECT')

        # 获取使用该贴图的材质列表
        material_names = texture_material_index[selected_image]
        selected_count = 0

        try:
            for obj in bpy.data.objects:
                if hasattr(obj.data, 'materials'):
                    for mat_slot in obj.material_slots:
                        if mat_slot.material and mat_slot.material.name in material_names:
                            obj.select_set(True)
                            selected_count += 1
                            break  # 如果物体有多个材质，找到一个匹配的就可以停止
        except Exception as e:
            self.report({'ERROR'}, f"发生错误: 物体可能不在当前场景中 {str(e)}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"已选中 {selected_count} 个使用该贴图的物体")
        return {'FINISHED'}


class TEXTURE_SEARCH_PT_main_panel(Panel):
    bl_label = "Texture Search"
    bl_idname = "TEXTURE_SEARCH_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = "objectmode"

    def draw(self, context):
        layout = self.layout
        props = context.scene.texture_search_props

        # 建立索引按钮
        layout.operator("texture_search.build_texture_index")

        # 图片选择下拉菜单
        layout.label(text="选择要查找的贴图:")
        layout.prop_search(props, "texture_search_image",
                           bpy.data, "images", text="")

        # 操作按钮
        row = layout.row()
        row.operator("texture_search.find_materials")
        row.operator("texture_search.select_objects_with_texture")


classes = (
    TextureSearchProperties,
    INDEX_OT_build_texture_index,
    INDEX_OT_find_materials,
    INDEX_OT_select_objects_with_texture,
    TEXTURE_SEARCH_PT_main_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.texture_search_props = PointerProperty(
        type=TextureSearchProperties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.texture_search_props


if __name__ == "__main__":
    register()
