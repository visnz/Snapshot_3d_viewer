from bpy.props import FloatProperty, EnumProperty  # type: ignore
import bpy  # type: ignore
import random  # type: ignore


class NoiseAnimSettings(bpy.types.Operator):
    bl_idname = "object.noise_anim_settings"
    bl_label = "Noise Animation Settings"
    bl_description = "存储Noise动画参数"
    # 这些参数会在插件运行时被更新
    scale_min = 20.0
    scale_max = 60.0
    strength_min = 0.1
    strength_max = 0.5
    phase_min = 0.0
    phase_max = 100.0
    target_property: str = "LOCATION"  # 默认目标属性


class OBJECT_OT_add_noise_anim(bpy.types.Operator):
    bl_idname = "object.add_noise_anim"
    bl_label = "Add/Update Noise Animation"
    bl_description = "为选中对象的Location/Rotation/Scale添加/更新Noise动画"
    bl_options = {'REGISTER', 'UNDO'}

    # 定义UI参数
    scale_min: FloatProperty(name="缩放", default=20.0,
                             min=0.1, max=1000.0)  # type: ignore
    scale_max: FloatProperty(name="缩放", default=60.0,
                             min=0.1, max=1000.0)  # type: ignore
    strength_min: FloatProperty(
        name="强度", default=0.1, min=0.0, max=10.0)  # type: ignore
    strength_max: FloatProperty(
        name="强度", default=0.5, min=0.0, max=10.0)  # type: ignore
    phase_min: FloatProperty(name="错位", default=0.0,
                             min=0.0, max=1000.0)  # type: ignore
    phase_max: FloatProperty(name="错位", default=100.0,
                             min=0.0, max=1000.0)  # type: ignore

    target_property: EnumProperty(
        name="目标属性",
        items=[
            ('LOCATION', "位置 (Location)", "在物体的位置 (XYZ) 上添加 Noise"),
            ('ROTATION', "旋转 (Rotation)", "在物体的旋转 (XYZ) 上添加 Noise"),
            ('SCALE', "缩放 (Scale)", "在物体的缩放 (XYZ) 上添加 Noise"),
        ],
        default='LOCATION'
    )  # type: ignore

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
