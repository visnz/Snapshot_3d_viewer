
import bpy  # type: ignore
import os
import json
from .ParentsOps import centro_global  # type: ignore

import subprocess
import platform


class FastCentreCamera(bpy.types.Operator):
    bl_idname = "object.fast_camera_visn"
    bl_label = "C-P摄像机组"
    bl_description = "创建一个以选择物体为目标点的，中心点+PSR锁定的的摄像机"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 获取创建点
        objs = context.selected_objects
        loc = centro_global(objs) if objs else (0, 0, 0)

        # 创建摄像机
        bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(
            0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1))
        bpy.context.active_object.name = 'Camera'
        cams = context.selected_objects
        bpy.context.space_data.camera = cams[0]
        bpy.ops.view3d.camera_to_view()
        bpy.ops.object.add(
            type='EMPTY', location=cams[0].location, rotation=cams[0].rotation_euler)
        bpy.context.active_object.name = 'Camera Protection'
        bpy.ops.object.constraint_add(type='DAMPED_TRACK')
        camP = context.selected_objects
        cams[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        cams[0].lock_location[:] = [True, True, True]
        cams[0].lock_rotation[:] = [True, True, True]

        # 创建原点的空物体
        bpy.ops.object.add(type='EMPTY', location=loc)
        bpy.context.active_object.name = 'Camera Central'
        camC = context.selected_objects
        camP[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        camP[0].select_set(False)
        cams[0].select_set(False)
        camP[0].constraints["Damped Track"].target = bpy.data.objects[camC[0].name]
        camP[0].constraints["Damped Track"].track_axis = 'TRACK_NEGATIVE_Z'

        return {'FINISHED'}


class CSPZT_Camera(bpy.types.Operator):
    bl_idname = "object.cspzt_camera_visn"
    bl_label = "C-SP-ZT朝向摄像机组"
    bl_description = "创建包含Central、Stare、Protection、Target和Zup的复杂摄像机组"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 获取创建点
        objs = context.selected_objects
        loc = centro_global(objs) if objs else (0, 0, 0)
        # 获取当前视图的摄像机位置和旋转
        view_matrix = context.space_data.region_3d.view_matrix
        cam_location = view_matrix.inverted().translation
        cam_rotation = view_matrix.to_3x3().inverted().to_euler()

        # 创建Cam_Central--↑ (根空物体)
        bpy.ops.object.add(type='EMPTY', location=loc)
        central = context.active_object
        central.name = 'Cam_Central--↑（向上添加目标点运动）'
        central.rotation_euler = cam_rotation

        # 创建Cam_Zup (世界空间，不设为任何物体的子级)
        bpy.ops.object.add(type='EMPTY', location=(0, 0, 100000))
        zup = context.active_object
        zup.name = 'Cam_Zup'

        # 创建Cam_Stare (作为Central的子对象)
        bpy.ops.object.add(type='EMPTY', location=cam_location)
        stare = context.active_object
        stare.name = 'Cam_Stare--↑（向上添加摄像机运动）'
        stare.parent = central
        # stare.location = (0, 0, 0)  # PSR=0

        # 添加约束到Stare
        # Damped Track指向Central, 轴为-Z
        damped_track = stare.constraints.new('DAMPED_TRACK')
        damped_track.target = central
        damped_track.track_axis = 'TRACK_NEGATIVE_Z'

        # Locked Track指向Zup, 跟踪Y轴, 锁定Z轴
        locked_track = stare.constraints.new('LOCKED_TRACK')
        locked_track.target = zup
        locked_track.track_axis = 'TRACK_Y'
        locked_track.lock_axis = 'LOCK_Z'

        # 创建Cam_Protection--↑ (作为Stare的子对象)
        bpy.ops.object.add(type='EMPTY', location=(0, 0, 0))
        protection = context.active_object
        protection.name = 'Cam_Protection--↑（向上添加局部空间运动）'
        protection.parent = stare
        protection.location = (0, 0, 0)  # PSR=0
        protection.rotation_euler = (0, 0, 0)
        protection.scale = (1, 1, 1)

        # 创建Cam_DOFTarget (作为Protection的子对象)
        bpy.ops.object.add(type='EMPTY', location=(0, 0, -1))  # 初始Z=-1
        dof_target = context.active_object
        dof_target.name = 'Cam_DOFTarget'
        dof_target.parent = protection
        dof_target.lock_location = (True, True, False)  # 仅Z轴可移动
        dof_target.lock_rotation = (True, True, True)  # 全锁定
        dof_target.lock_scale = (True, True, True)  # 全锁定

        # 创建摄像机 (作为Protection的子对象)
        bpy.ops.object.camera_add(enter_editmode=False, location=(0, 0, 0))
        cam = context.active_object
        cam.name = 'Cam'
        cam.parent = protection
        cam.location = (0, 0, 0)  # PSR=0
        cam.rotation_euler = (0, 0, 0)
        cam.lock_location = (True, True, True)
        cam.lock_rotation = (True, True, True)
        cam.lock_scale = (True, True, True)

        # 启用景深并设置焦点目标
        cam.data.dof.use_dof = True
        cam.data.dof.focus_object = dof_target

        # 设置当前视图的相机并进入摄像机视图
        context.space_data.camera = cam
        bpy.ops.view3d.view_camera()

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


# 使用Blender的属性系统来持久化存储状态
bpy.types.Scene.children_select_state = bpy.props.BoolProperty(
    name="Children Select State",
    default=False
)


class ToggleChildrenSelectability(bpy.types.Operator):
    bl_idname = "object.toggle_children_selectability_visn"
    bl_label = "子对象 封包/解包"
    bl_description = "将对象的子级内容全部可选性切换（开启或关闭）"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        current_state = context.scene.children_select_state
        selected_objs = context.selected_objects.copy()  # 复制当前选择

        # 递归设置所有子级的可选性
        def set_children_selectability(obj, state):
            for child in obj.children:
                child.hide_select = state
                set_children_selectability(child, state)

        # 处理每个选中的对象
        for obj in selected_objs:
            set_children_selectability(obj, not current_state)

        # 切换并存储新状态
        context.scene.children_select_state = not current_state

        if current_state:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in selected_objs:
                obj.select_set(True)
                self.select_hierarchy(obj)

        # 操作反馈
        state = "关闭" if current_state else "开启"
        self.report({'INFO'}, f"子级选择性已{state}")

        # 刷新界面
        context.area.tag_redraw()

        return {'FINISHED'}

    def select_hierarchy(self, obj):
        """递归选择对象及其所有子级"""
        for child in obj.children:
            child.select_set(True)
            self.select_hierarchy(child)
