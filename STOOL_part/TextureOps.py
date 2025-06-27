import bpy
from bpy.props import StringProperty  # type: ignore
from bpy.types import Operator, PropertyGroup  # type: ignore


class INDEX_OT_select_objects_with_texture(Operator):
    bl_idname = "index.select_objects_with_texture"
    bl_label = "选中该贴图的材质对象"
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

        # 遍历所有对象
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


class TextureSearchProperties(PropertyGroup):
    texture_search_image: StringProperty(
        name="贴图",
        description="选择要查找的贴图",
        default=""
    )  # type: ignore


# 全局变量存储索引结果
texture_material_index = {}


class INDEX_OT_build_texture_index(Operator):
    bl_idname = "index.build_texture_index"
    bl_label = "建立or刷新 贴图-材质 索引"
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
    bl_idname = "index.find_materials"
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
