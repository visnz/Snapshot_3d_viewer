import bpy
import random
import os
import subprocess
import platform
from bpy.props import FloatProperty, EnumProperty
from bpy.types import Operator
import json

### 面板类函数 ###


class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "SomeTools"
    bl_idname = "VIEW3D_PT_snapshot_panel_SomeTools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.separator()
        layout.label(text="父子级")
        layout.operator("object.parent_to_empty_visn")
        layout.operator("object.parent_to_empty_visn_individual")
        layout.operator("object.parent_to_empty_collection_visn")
        layout.operator("object.select_parent_visn")
        layout.operator("object.release_all_children_to_world_visn")
        layout.operator("object.release_all_children_to_subparent_visn")
        layout.operator("object.solo_pick_visn")

        layout.separator()
        layout.label(text="搭建类")
        layout.operator("object.fast_camera_visn")
        layout.operator("object.add_light_with_constraint")
        layout.operator("wm.open_project_folder_visn")
        layout.operator("object.save_selection_visn")
        layout.operator("object.load_selection_visn")
        layout.operator("object.remove_unused_material_slots_visn")

        layout.separator()
        layout.label(text="动画类")
        layout.operator("object.add_noise_anim", text="Wiggle（添加/更新Noise）")
        layout.operator("object.add_noise_anim_r",
                        text="旋转Wiggle（添加/更新Noise动画）")
        layout.operator("object.remove_all_animations_visn")

### STOOL 插件的类和操作 ###


def centro(sel):
    x = sum(obj.location[0] for obj in sel) / len(sel)
    y = sum(obj.location[1] for obj in sel) / len(sel)
    z = sum(obj.location[2] for obj in sel) / len(sel)
    return (x, y, z)


def centro_global(sel):
    x = sum(obj.matrix_world.translation[0] for obj in sel) / len(sel)
    y = sum(obj.matrix_world.translation[1] for obj in sel) / len(sel)
    z = sum(obj.matrix_world.translation[2] for obj in sel) / len(sel)
    return (x, y, z)


def get_children(my_object):
    return [ob for ob in bpy.data.objects if ob.parent == my_object]


class FastCentreCamera(Operator):
    bl_idname = "object.fast_camera_visn"
    bl_label = "中心约束摄像机"
    bl_description = "创建一个以选择物体为目标点的，中心点+PSR锁定的的摄像机"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 获取创建点
        objs = context.selected_objects
        loc = centro_global(objs) if objs else (0, 0, 0)

        # 创建摄像机
        bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(
            0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1))
        bpy.context.active_object.name = 'NewCamera'
        cams = context.selected_objects
        bpy.context.space_data.camera = cams[0]
        bpy.ops.view3d.camera_to_view()
        bpy.ops.object.add(
            type='EMPTY', location=cams[0].location, rotation=cams[0].rotation_euler)
        bpy.context.active_object.name = 'CameraProtection'
        bpy.ops.object.constraint_add(type='DAMPED_TRACK')
        camP = context.selected_objects
        cams[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        cams[0].lock_location[:] = [True, True, True]
        cams[0].lock_rotation[:] = [True, True, True]

        # 创建原点的空物体
        bpy.ops.object.add(type='EMPTY', location=loc)
        bpy.context.active_object.name = 'CameraCentre'
        camC = context.selected_objects
        camP[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        camP[0].select_set(False)
        cams[0].select_set(False)
        camP[0].constraints["Damped Track"].target = bpy.data.objects[camC[0].name]
        camP[0].constraints["Damped Track"].track_axis = 'TRACK_NEGATIVE_Z'

        return {'FINISHED'}


class SoloPick(Operator):
    # 断开所选物体的所有父子级关系，捡出来放在世界层级，子级归更上一层父级管。
    bl_idname = "object.solo_pick_visn"
    bl_label = "拎出（断开父子级）"
    bl_description = "断开所有选择物体的父子级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass

        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if not obj.parent:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    children.select_set(False)
            else:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    bpy.context.view_layer.objects.active = obj.parent
                    bpy.ops.object.parent_no_inverse_set(keep_transform=True)
                    children.select_set(False)
        for obj in objs:
            obj.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            obj.select_set(False)
        for obj in objs:
            obj.select_set(True)
        return {'FINISHED'}


class SelectParent(Operator):
    bl_idname = "object.select_parent_visn"
    bl_label = "选择所有父级"
    bl_description = "选择被选中对象的所有父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if obj.parent:
                obj.parent.select_set(True)
        return {'FINISHED'}


class RAQ(Operator):
    bl_idname = "object.release_all_children_to_world_visn"
    bl_label = "释放子对象（到世界）"
    bl_description = "释放子对象（到世界）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            for children in get_children(obj):
                children.select_set(True)
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                children.select_set(False)
        return {'FINISHED'}


class RAQtoSubparent(Operator):
    bl_idname = "object.release_all_children_to_subparent_visn"
    bl_label = "释放子对象（到上级）"
    bl_description = "释放子对象（到上级）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        NOParent = False
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if not obj.parent:
                NOParent = True
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    children.select_set(False)
            else:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    bpy.context.view_layer.objects.active = obj.parent
                    bpy.ops.object.parent_no_inverse_set(keep_transform=True)
                    children.select_set(False)
        if not NOParent:
            for obj in objs:
                bpy.context.view_layer.objects.active = obj.parent
                obj.parent.select_set(True)
        return {'FINISHED'}


class P2E_Collection(Operator):
    bl_idname = "object.parent_to_empty_collection_visn"
    bl_label = "所选物体 到新集合"
    bl_description = "所有选择的物体到新父级，并送入新集合"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        def move_to_collection(obj, collection):
            # 递归地将对象及其所有子对象移动到指定集合中
            # 首先将对象从其所有集合中移除
            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            # 将对象添加到新集合中
            collection.objects.link(obj)
            # 递归地处理子对象
            for child in obj.children:
                move_to_collection(child, collection)

        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        # 获取所有选中对象的中心位置
        loc = centro(objs)
        same_parent = all(o.parent == objs[0].parent for o in objs)

        # 创建一个新的集合
        new_collection = bpy.data.collections.new(name="New Collection")
        context.scene.collection.children.link(new_collection)

        # 将新集合设置为活跃集合
        layer_collection = context.view_layer.layer_collection
        for layer in layer_collection.children:
            if layer.collection == new_collection:
                context.view_layer.active_layer_collection = layer

        # 创建一个新的空对象并设置位置
        bpy.ops.object.select_all(action='DESELECT')
        if len(objs) == 1:
            bpy.ops.object.add(type='EMPTY', location=loc,
                               rotation=objs[0].rotation_euler)
        else:
            bpy.ops.object.add(type='EMPTY', location=loc)

        new_empty = context.object

        # 如果所有选中对象有相同的父级，则将新空对象设置为该父级的子级
        if same_parent:
            new_empty.parent = objs[0].parent

        # 将新空对象添加到新集合中
        try:
            new_collection.objects.link(new_empty)
        except:
            pass

        # 确保新空对象在当前视图层中
        context.view_layer.objects.active = new_empty

        # 遍历所有选中对象并递归地将它们及其子对象移动到新集合中
        for o in objs:
            move_to_collection(o, new_collection)
            # 设置父级
            o.select_set(True)
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            o.select_set(False)

        return {'FINISHED'}


class P2E_individual(Operator):
    bl_idname = "object.parent_to_empty_visn_individual"
    bl_label = "所选物体 单独每个到父级"
    bl_description = "所有所选物体，每个对象都创建一个保护父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        last_active_obj = context.view_layer.objects.active  # 获取最后一次选中的活跃对象

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        # 为每个选中的物体创建一个独立的父级空物体
        for obj in objs:
            # 计算当前物体的位置
            loc = obj.location.copy()

            # 创建空物体
            bpy.ops.object.add(type='EMPTY', location=loc,
                               rotation=obj.rotation_euler)
            new_empty = context.object  # 获取新创建的空物体

            # 获取当前物体的集合
            obj_collections = obj.users_collection

            # 将新创建的空物体添加到当前物体的集合中
            try:
                for collection in obj_collections:
                    collection.objects.link(new_empty)
                # 从当前活跃集合中移除新创建的空物体
                context.collection.objects.unlink(new_empty)
            except:
                pass

            # 设置父级关系
            new_empty.parent = obj.parent  # 继承原始物体的父级

            # 设置当前物体为新空物体的子物体
            obj.select_set(True)
            context.view_layer.objects.active = new_empty
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            obj.select_set(False)

        # 恢复原始选择状态
        for obj in objs:
            obj.select_set(True)
        if last_active_obj:
            context.view_layer.objects.active = last_active_obj

        return {'FINISHED'}


class P2E(Operator):
    bl_idname = "object.parent_to_empty_visn"
    bl_label = "所选物体 到父级"
    bl_description = "所有所选物体到父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        last_active_obj = context.view_layer.objects.active  # 获取最后一次选中的活跃对象

        try:
            bpy.ops.object.mode_set()
        except:
            pass

        loc = centro(objs)
        same_parent = all(o.parent == objs[0].parent for o in objs)

        if len(objs) == 1:
            bpy.ops.object.add(type='EMPTY', location=loc,
                               rotation=objs[0].rotation_euler)
        else:
            bpy.ops.object.add(type='EMPTY', location=loc)

        new_empty = context.object  # 获取新创建的空物体

        # 获取最后一次选中的活跃对象的集合
        if last_active_obj is not None:
            last_active_collections = last_active_obj.users_collection

            # 将新创建的空物体添加到活跃对象的集合中
            try:
                for collection in last_active_collections:
                    collection.objects.link(new_empty)

                # 从当前活跃集合中移除新创建的空物体
                context.collection.objects.unlink(new_empty)
            except:
                pass
            # 将子对象从原来的集合中移除，并添加到新的集合中
            for o in objs:
                for collection in o.users_collection:
                    collection.objects.unlink(o)
                for collection in last_active_collections:
                    collection.objects.link(o)

        if same_parent:
            new_empty.parent = objs[0].parent

        for o in objs:
            o.select_set(True)
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            o.select_set(False)

        return {'FINISHED'}


class OpenProjectFolderOperator(bpy.types.Operator):
    # 打开当前工程所在的文件夹
    bl_idname = "wm.open_project_folder_visn"
    bl_label = "打开工程文件夹"
    bl_options = {'REGISTER'}

    def execute(self, context):
        blend_filepath = bpy.data.filepath
        if not blend_filepath:
            self.report({'ERROR'}, "当前没有打开的工程文件")
            return {'CANCELLED'}

        project_folder = os.path.dirname(blend_filepath)

        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', project_folder])
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', project_folder])
        else:  # Linux and other OS
            subprocess.Popen(['xdg-open', project_folder])

        return {'FINISHED'}


class AddLightWithConstraint(bpy.types.Operator):
    bl_idname = "object.add_light_with_constraint"
    bl_label = "中心约束灯光"
    bl_description = "在所选物体的位置创建一个空对象，并在其子级创建一个灯光，设置 Damped Track 约束"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects

        if not objs:
            self.report({'WARNING'}, "没有选中的物体")
            return {'CANCELLED'}

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except Exception as e:
            self.report({'WARNING'}, f"无法切换模式: {e}")
            pass

        # 计算选中对象的中心位置
        loc = centro_global(objs)

        # 保存当前活跃集合
        original_active_collection = context.view_layer.active_layer_collection

        # 设置 Scene Collection 为活跃集合
        scene_collection = context.view_layer.layer_collection
        context.view_layer.active_layer_collection = scene_collection

        # 创建一个新的空对象
        bpy.ops.object.add(type='EMPTY', location=loc)
        empty_obj = context.object  # 获取新创建的空物体
        empty_obj.name = "约束灯光组"  # 设置名称

        # 在空对象的子级创建一个Spot灯光对象
        bpy.ops.object.light_add(type='SPOT', location=loc)
        light_obj = context.object  # 获取新创建的灯光对象
        light_obj.parent = empty_obj  # 设置灯光对象的父级为空对象
        light_obj.name = "约束灯光"  # 设置灯光名称
        light_obj.location = (0, 0, 0)  # 将灯光对象位置归零

        # 添加 Damped Track 约束到灯光对象
        constraint = light_obj.constraints.new(type='DAMPED_TRACK')
        constraint.target = empty_obj
        constraint.track_axis = 'TRACK_NEGATIVE_Z'

        # 恢复原来的活跃集合
        context.view_layer.active_layer_collection = original_active_collection

        # 设置新创建的灯光对象为活跃对象并选中
        bpy.context.view_layer.objects.active = light_obj
        bpy.ops.object.select_all(action='DESELECT')
        light_obj.select_set(True)

        self.report({'INFO'}, "灯光和约束已成功创建")
        return {'FINISHED'}

# ======= Wiggle的效果 =====================
# 存储插件参数的类（不依赖Scene）


class NoiseAnimSettings:
    scale_min = 20.0
    scale_max = 60.0
    strength_min = 0.1
    strength_max = 0.5
    phase_min = 0.0
    phase_max = 100.0
    target_property: str = "LOCATION"  # 默认目标属性


class OBJECT_OT_add_noise_anim(Operator):
    bl_idname = "object.add_noise_anim"
    bl_label = "Add/Update Noise Animation"
    bl_description = "为选中对象的Location/Rotation/Scale添加/更新Noise动画"
    bl_options = {'REGISTER', 'UNDO'}

    # 定义UI参数
    scale_min: FloatProperty(name="缩放", default=20.0, min=0.1, max=1000.0)
    scale_max: FloatProperty(name="缩放", default=60.0, min=0.1, max=1000.0)
    strength_min: FloatProperty(name="强度", default=0.1, min=0.0, max=10.0)
    strength_max: FloatProperty(name="强度", default=0.5, min=0.0, max=10.0)
    phase_min: FloatProperty(name="错位", default=0.0, min=0.0, max=1000.0)
    phase_max: FloatProperty(name="错位", default=100.0, min=0.0, max=1000.0)

    target_property: EnumProperty(
        name="目标属性",
        items=[
            ('LOCATION', "位置 (Location)", "在物体的位置 (XYZ) 上添加 Noise"),
            ('ROTATION', "旋转 (Rotation)", "在物体的旋转 (XYZ) 上添加 Noise"),
            ('SCALE', "缩放 (Scale)", "在物体的缩放 (XYZ) 上添加 Noise"),
        ],
        default='LOCATION'
    )

    def execute(self, context):
        # 检查参数合法性
        if self.scale_min > self.scale_max:
            self.report({'ERROR'}, "Scale Min 必须 ≤ Scale Max")
            return {'CANCELLED'}
        if self.strength_min > self.strength_max:
            self.report({'ERROR'}, "Strength Min 必须 ≤ Strength Max")
            return {'CANCELLED'}
        if self.phase_min > self.phase_max:
            self.report({'ERROR'}, "Phase Min 必须 ≤ Phase Max")
            return {'CANCELLED'}

        # 更新全局设置（保存参数到类变量）
        NoiseAnimSettings.scale_min = self.scale_min
        NoiseAnimSettings.scale_max = self.scale_max
        NoiseAnimSettings.strength_min = self.strength_min
        NoiseAnimSettings.strength_max = self.strength_max
        NoiseAnimSettings.phase_min = self.phase_min
        NoiseAnimSettings.phase_max = self.phase_max
        NoiseAnimSettings.target_property = self.target_property

        # 处理选中的对象
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'WARNING'}, "未选中任何对象")
            return {'CANCELLED'}

        for obj in selected_objects:
            if not obj.animation_data:
                obj.animation_data_create()

            # 根据目标属性选择 data_path
            if self.target_property == 'LOCATION':
                data_path = "location"
            elif self.target_property == 'ROTATION':
                data_path = "rotation_euler"  # 使用欧拉角（默认）
            elif self.target_property == 'SCALE':
                data_path = "scale"
            else:
                self.report({'ERROR'}, "未知的目标属性")
                return {'CANCELLED'}

            # 插入关键帧（确保 F-Curve 存在）
            obj.keyframe_insert(data_path=data_path, frame=0)

            fcurves = obj.animation_data.action.fcurves
            for axis in range(3):  # X/Y/Z
                fcurve = fcurves.find(data_path, index=axis)
                if not fcurve:
                    fcurve = fcurves.new(data_path, index=axis)

                # 删除旧的NOISE修改器
                for mod in fcurve.modifiers:
                    if mod.type == 'NOISE':
                        fcurve.modifiers.remove(mod)

                # 添加新的NOISE修改器
                noise_mod = fcurve.modifiers.new('NOISE')
                noise_mod.scale = random.uniform(
                    self.scale_min, self.scale_max)
                noise_mod.strength = random.uniform(
                    self.strength_min, self.strength_max)
                noise_mod.phase = random.uniform(
                    self.phase_min, self.phase_max)
                noise_mod.blend_in = 0
                noise_mod.blend_out = 0

        self.report(
            {'INFO'}, f"已为 {len(selected_objects)} 个对象的 {self.target_property} 添加Noise动画")
        return {'FINISHED'}

    def invoke(self, context, event):
        # 初始化对话框参数（从类变量加载上次的值）
        self.scale_min = NoiseAnimSettings.scale_min
        self.scale_max = NoiseAnimSettings.scale_max
        self.strength_min = NoiseAnimSettings.strength_min
        self.strength_max = NoiseAnimSettings.strength_max
        self.phase_min = NoiseAnimSettings.phase_min
        self.phase_max = NoiseAnimSettings.phase_max
        self.target_property = NoiseAnimSettings.target_property
        return context.window_manager.invoke_props_dialog(self, width=300)

# ======= Wiggle的效果 =====================


# ======= 选择组的效果 =====================
class SaveSelection(bpy.types.Operator):
    bl_idname = "object.save_selection_visn"
    bl_label = "保存【选择组】"
    bl_description = "将当前选择的对象保存为序列，创建一个空对象：选择组"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected_objs = context.selected_objects
        selection_data = []

        # 收集当前选择的对象及其数据
        for obj in selected_objs:
            obj_data = {
                'name': obj.name,
                'type': obj.type,
                'data': obj.data.name if obj.data else None
            }
            selection_data.append(obj_data)

        # 生成选择组的名称
        group_name_parts = [obj.name if len(
            obj.name) <= 8 else obj.name[:8] + "..." for obj in selected_objs]
        group_name = "选择组_" + ",".join(group_name_parts)

        # 将选择的数据保存为JSON字符串
        selection_json = json.dumps(selection_data, indent=4)

        # 在SceneCollection下创建一个空对象叫做“选择组”
        scene_collection = context.scene.collection
        index = 1
        base_name = group_name
        while bpy.data.objects.get(f"{base_name}_{index}"):
            index += 1
        selection_group = bpy.data.objects.new(f"{base_name}_{index}", None)
        scene_collection.objects.link(selection_group)

        # 创建一个新的text block来存储选择数据
        text_block_name = f"选择组数据_{index}"
        text_block = bpy.data.texts.new(name=text_block_name)
        text_block.write(selection_json)

        # 将text block链接到选择组对象的自定义属性
        selection_group["selection_data"] = text_block.name

        self.report({'INFO'}, "当前选择已保存")
        return {'FINISHED'}


class LoadSelection(bpy.types.Operator):
    bl_idname = "object.load_selection_visn"
    bl_label = "读取【选择组】"
    bl_description = "通过选择“选择组”对象，还原之前保存的选择状态"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active_obj = context.view_layer.objects.active
        if not active_obj or not active_obj.name.startswith("选择组_"):
            self.report({'WARNING'}, "请先选择一个“选择组”对象")
            return {'CANCELLED'}

        # 获取选择组对象的自定义属性中的text block名称
        text_block_name = active_obj.get("selection_data")
        if not text_block_name or text_block_name not in bpy.data.texts:
            self.report({'WARNING'}, "未找到选择数据")
            return {'CANCELLED'}

        # 获取选择数据JSON字符串
        selection_json = bpy.data.texts[text_block_name].as_string()
        selection_data = json.loads(selection_json)

        # 还原选择状态
        bpy.ops.object.select_all(action='DESELECT')
        for obj_data in selection_data:
            obj = bpy.data.objects.get(obj_data['name'])
            if obj:
                obj.select_set(True)
                context.view_layer.objects.active = obj

        self.report({'INFO'}, "选择状态已还原")
        return {'FINISHED'}
# ======= 选择组的效果 =====================


# ======= remove_unused_slots的效果 =====================
class RemoveUnusedMaterialSlots(bpy.types.Operator):
    """Remove unused material slots for all selected objects"""
    bl_idname = "object.remove_unused_material_slots_visn"
    bl_label = "移除未使用材质槽"
    bl_description = "移除未使用的材质槽"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        # 保存当前活动对象
        active_obj = context.active_object

        # 统计处理的物体数量
        processed_objects = 0

        for obj in context.selected_objects:
            if obj.type in {'MESH', 'CURVE', 'SURFACE', 'FONT', 'META', 'GPENCIL'}:
                # 临时将当前物体设为活动对象
                context.view_layer.objects.active = obj
                # 执行移除未使用材质槽的操作
                bpy.ops.object.material_slot_remove_unused()
                processed_objects += 1

        # 恢复原来的活动对象
        if active_obj:
            context.view_layer.objects.active = active_obj

        self.report({'INFO'}, f"Processed {processed_objects} objects")
        return {'FINISHED'}

# ======= remove_unused_slots的效果 =====================

# ======= 删除动画 =====================


class RemoveAllAnimations(bpy.types.Operator):
    """Remove all animations from selected objects"""
    bl_idname = "object.remove_all_animations_visn"
    bl_label = "删除所选对象的动画"
    bl_description = "删除所选对象的所有动画数据"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        processed_objects = 0

        for obj in context.selected_objects:
            # Remove animation data
            if obj.animation_data:
                obj.animation_data_clear()
                processed_objects += 1

            # Remove shape key animations if exists
            if obj.data and hasattr(obj.data, 'shape_keys') and obj.data.shape_keys:
                if obj.data.shape_keys.animation_data:
                    obj.data.shape_keys.animation_data_clear()
                    processed_objects += 1

        self.report(
            {'INFO'}, f"Removed animations from {processed_objects} objects")
        return {'FINISHED'}
# ======= 删除动画 =====================


### 注册类函数 ###
allClass = [
    RemoveAllAnimations,
    RemoveUnusedMaterialSlots,
    VIEW3D_PT_SnapshotPanel,
    FastCentreCamera,
    SoloPick,
    SelectParent,
    RAQ,
    RAQtoSubparent,
    P2E_Collection,
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
