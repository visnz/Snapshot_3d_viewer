import os
from bpy.props import (StringProperty, IntProperty,  # type: ignore
                       BoolProperty)
from bpy.types import Operator, PropertyGroup  # type: ignore
import re
import bpy  # type: ignore

# --------------------------
# 工具函数
# --------------------------


class RenderPresetSettings(PropertyGroup):
    resolution_x: IntProperty(
        name="Resolution X", default=1920, min=4)  # type: ignore
    resolution_y: IntProperty(
        name="Resolution Y", default=1080, min=4)  # type: ignore
    samples: IntProperty(name="Samples", default=1536, min=1)  # type: ignore
    frame_start: IntProperty(
        name="Frame Start", default=0, min=0)  # type: ignore
    frame_end: IntProperty(name="Frame End", default=100,
                           min=0)  # type: ignore
    relative_path: StringProperty(  # type: ignore
        name="Relative Path", subtype='DIR_PATH', default="\\__Cache__\\")
    absolute_path: StringProperty(  # type: ignore
        name="Absolute Path", subtype='DIR_PATH', default="F:\\__Cache__\\")
    use_absolute_path: BoolProperty(  # type: ignore
        name="Use Absolute Path",
        description="Toggle between absolute and relative paths",
        default=False
    )


class RENDER_OT_create_presets(Operator):
    """创建预设对象"""
    bl_idname = "render.create_presets"
    bl_label = "创建预设"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "不存在活跃摄像机")
            return {'CANCELLED'}

        # 获取摄像机所在的集合
        cam_coll = None
        for collection in bpy.data.collections:
            if cam.name in collection.objects:
                cam_coll = collection
                break

        if not cam_coll:
            cam_coll = context.scene.collection  # 如果摄像机不在任何集合中，使用主场景集合

        # 删除旧的预设对象
        for child in cam.children:
            if re.match(r'^\d+\..+', child.name) or child.name == "Current":
                # 从所有集合中移除对象
                for coll in bpy.data.collections:
                    if child.name in coll.objects:
                        coll.objects.unlink(child)
                bpy.data.objects.remove(child, do_unlink=True)

        # 获取当前设置
        props = context.scene.render_preset_settings
        render = context.scene.render

        # 创建预设对象（按数字顺序）
        presets = [
            ('1. HD    ',
             f"[xy={props.resolution_x}x{props.resolution_y}, sp={props.samples}, Rng={props.frame_start}-{props.frame_end}]"),
            ('2. Style ', f"[xy=100%, sp=100%, Rng=50]"),
            ('3. prev  ', f"[xy=100%, sp=10%, Rng=0-100]"),
            ('4. demo  ', f"[xy=50%, sp=30%, Rng=100%]"),
            ('5. folder',
             f"[\"{props.relative_path}\",\"{props.absolute_path}\"]")
        ]

        # 创建空对象
        for preset_name, params in presets:
            empty = bpy.data.objects.new(preset_name, None)  # 直接创建空对象
            if cam_coll:
                cam_coll.objects.link(empty)
            else:
                context.scene.collection.objects.link(empty)

            # 设置父级（确保不是设置自身为父级）
            if empty != cam:
                empty.parent = cam
            empty.name = f"{preset_name}:{params}"

        # 创建当前设置显示对象
        current_empty = bpy.data.objects.new("Current", None)
        if cam_coll:
            cam_coll.objects.link(current_empty)
        else:
            context.scene.collection.objects.link(current_empty)

        # 设置父级（确保不是设置自身为父级）
        if current_empty != cam:
            current_empty.parent = cam

        # 立即更新显示
            bpy.ops.render.apply_preset(preset_type='HD')
        update_current_settings_display(cam, context.scene)

        self.report({'INFO'}, "预设对象已创建")
        return {'FINISHED'}

    def invoke(self, context, event):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "不存在活跃摄像机")
            return {'CANCELLED'}

        # 初始化设置
        props = context.scene.render_preset_settings
        render = context.scene.render

        # 使用当前渲染设置初始化值
        props.resolution_x = render.resolution_x
        props.resolution_y = render.resolution_y

        if hasattr(render, 'cycles'):
            props.samples = render.cycles.samples
        elif hasattr(render, 'eevee'):
            props.samples = render.eevee.taa_render_samples

        props.frame_start = context.scene.frame_start
        props.frame_end = context.scene.frame_end

        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        props = context.scene.render_preset_settings

        # 分辨率设置
        col = layout.column(align=True)
        col.label(text="最终渲染设置 (Final):")
        row = col.row(align=True)
        row.prop(props, "resolution_x", text="X")
        row.prop(props, "resolution_y", text="Y")

        # 采样设置
        layout.separator()
        layout.prop(props, "samples", text="采样数")

        # 帧范围设置
        layout.separator()
        col = layout.column(align=True)
        col.label(text="帧范围:")
        row = col.row(align=True)
        row.prop(props, "frame_start", text="开始")
        row.prop(props, "frame_end", text="结束")

        # 路径设置 - 修改后的版本
        layout.separator()
        layout.prop(props, "absolute_path", text="绝对路径")
        layout.prop(props, "relative_path", text="相对路径")


class RENDER_OT_apply_preset(Operator):
    """应用预设设置"""
    bl_idname = "render.apply_preset"
    bl_label = "应用预设"
    bl_options = {'REGISTER', 'UNDO'}

    preset_type: StringProperty(  # type: ignore
        name="Preset Type",
        description="Type of preset to apply",
        default="Style"
    )

    # all_scenes: BoolProperty(
    #     name="All Scenes",
    #     description="Apply to all scenes",
    #     default=False
    # )

    def update_current_settings_display(self, cam, scene):
        """现在调用独立函数"""
        update_current_settings_display(cam, scene)

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "不存在活跃摄像机")
            return {'CANCELLED'}

        # 获取所有预设
        presets = {}
        hd_params = {}
        folder_params = {}

        for child in cam.children:
            if ':' in child.name:
                # 移除数字前缀和空格
                preset_name = re.sub(
                    r'^\d+\.\s*', '', child.name.split(':', 1)[0].strip().lower())
                params = self.parse_preset_params(child.name.split(':', 1)[1])

                if preset_name == 'folder':
                    folder_params = params
                elif preset_name == 'hd':
                    hd_params = params
                else:
                    presets[preset_name] = params

        if self.preset_type.lower() not in presets and self.preset_type.lower() != 'hd':
            self.report({'ERROR'}, f"找不到 {self.preset_type} 预设")
            return {'CANCELLED'}

        scenes = [context.scene]  # if not self.all_scenes else bpy.data.scenes

        for scene in scenes:
            render = scene.render
            cycles = scene.cycles if hasattr(scene, 'cycles') else None
            eevee = scene.eevee if hasattr(scene, 'eevee') else None

            # 更新输出路径
            if folder_params:
                use_absolute = scene.render_preset_settings.absolute_path.strip() != ""
                self.update_output_path(
                    render, scene, folder_params, self.preset_type.lower())

            # 应用预设设置
            if self.preset_type.lower() == 'hd':
                self.apply_hd_settings(render, scene, cycles, eevee, hd_params)
            else:
                self.apply_preset_settings(
                    render, scene, cycles, eevee, presets[self.preset_type.lower()], hd_params)

            # 更新当前设置显示对象
            update_current_settings_display(
                cam, context.scene, self.preset_type.lower())

        self.report({'INFO'}, f"已应用 {self.preset_type} 预设")
        return {'FINISHED'}

    def update_output_path(self, render, scene, folder_params, preset_type):
        """更新输出路径"""
        props = scene.render_preset_settings
        path_key = "absolute" if props.use_absolute_path else "relative"
        base_path = folder_params.get(path_key, "").strip(
            '"').replace('\\', '/').rstrip('/')

        if not base_path:
            return

        # 构建标准路径结构
        render_dir = f"Render_{preset_type}"
        scene_dir = f"{scene.name}_{preset_type}"
        filename = f"{scene.name}_{preset_type}"

        render.filepath = f"{base_path}/{render_dir}/{scene_dir}/{filename}".replace(
            '//', '/')

    def apply_hd_settings(self, render, scene, cycles, eevee, params):
        """应用HD预设设置"""
        if 'xy' in params:
            size = params['xy'].lower()
            if 'x' in size:
                try:
                    w, h = size.split('x')
                    render.resolution_x = int(w)
                    render.resolution_y = int(h)
                    render.resolution_percentage = 100
                except ValueError:
                    pass

        if 'sp' in params:
            try:
                samples = int(params['sp'])
                if cycles:
                    cycles.samples = samples
                if eevee:
                    eevee.taa_render_samples = samples
            except ValueError:
                pass

        if 'rng' in params:
            if '-' in params['rng']:
                try:
                    start, end = map(int, params['rng'].split('-'))
                    scene.frame_start = start
                    scene.frame_end = end
                except ValueError:
                    pass

    def apply_preset_settings(self, render, scene, cycles, eevee, params, hd_params):
        """应用其他预设设置"""
        # 分辨率设置
        if 'xy' in params:
            size = params['xy'].lower()
            if '%' in size:
                try:
                    percent = int(size.replace('%', ''))
                    render.resolution_percentage = percent
                except ValueError:
                    pass

        # 采样设置
        if 'sp' in params:
            sample = params['sp'].lower()
            try:
                if '%' in sample:
                    percent = float(sample.replace('%', '')) / 100.0
                    base_samples = int(hd_params.get('sp', 1536))
                    samples = int(base_samples * percent)
                else:
                    samples = int(sample)

                if cycles:
                    cycles.samples = samples
                if eevee:
                    eevee.taa_render_samples = samples
            except ValueError:
                pass

        # 帧范围设置
        if 'rng' in params:
            range_val = params['rng']
            if '%' in range_val:  # 使用HD的范围
                if '-' in hd_params.get('rng', '0-100'):
                    start, end = map(int, hd_params['rng'].split('-'))
                    scene.frame_start = start
                    scene.frame_end = end
            elif '-' in range_val:  # 自定义范围
                try:
                    start, end = map(int, range_val.split('-'))
                    scene.frame_start = start
                    scene.frame_end = end
                except ValueError:
                    pass
            else:  # 单帧
                try:
                    frame = int(range_val)
                    scene.frame_start = frame
                    scene.frame_end = frame
                except ValueError:
                    pass

    def parse_preset_params(self, param_str):
        """解析预设参数"""
        params = {}
        bracket_content = param_str.split(']')[0].split('[')[-1].strip()

        # 特别处理folder对象的路径格式
        if bracket_content.startswith('"') and bracket_content.endswith('"'):
            bracket_content = bracket_content[1:-1]  # 移除外部的双引号

        if '"' in bracket_content:  # 处理路径格式
            paths = [p.strip().strip('"') for p in bracket_content.split(',')]
            if len(paths) >= 2:
                params["relative"] = paths[0]
                params["absolute"] = paths[1]
                return params

        # 普通参数解析
        for param in bracket_content.split(','):
            param = param.strip()
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip().lower()] = value.strip().strip('"')

        return params


def get_camera_collection(camera_obj):
    """获取摄像机所在的第一个集合"""
    for coll in bpy.data.collections:
        if camera_obj.name in coll.objects:
            return coll
    return None


def update_current_settings_display(cam, scene, preset_name="HD"):
    """更新当前设置显示对象"""
    # 获取摄像机所在的集合
    cam_coll = None
    for collection in bpy.data.collections:
        if cam.name in collection.objects:
            cam_coll = collection
            break

    if not cam_coll:
        cam_coll = scene.collection

    render = scene.render
    cycles = scene.cycles if hasattr(scene, 'cycles') else None
    eevee = scene.eevee if hasattr(scene, 'eevee') else None

    # 获取当前采样值
    current_samples = 0
    if cycles:
        current_samples = cycles.samples
    elif eevee:
        current_samples = eevee.taa_render_samples

    # 获取路径类型
    props = scene.render_preset_settings
    path_type = "Abs" if props.use_absolute_path else "Rel"

    # 查找现有的当前设置对象
    current_obj = None
    for child in cam.children:
        if child.name.startswith("Current"):
            current_obj = child
            break

    # 如果不存在则创建
    if not current_obj:
        current_obj = bpy.data.objects.new("Current", None)
        if cam_coll:
            cam_coll.objects.link(current_obj)
        else:
            scene.collection.objects.link(current_obj)

        # 设置父级（确保不是设置自身为父级）
        if current_obj != cam:
            current_obj.parent = cam

    # 如果存在多个，则删除多余的
    elif sum(1 for child in cam.children if child.name.startswith("Current")) > 1:
        # 保留第一个，删除其余的
        to_delete = [child for child in cam.children if child.name.startswith(
            "Current")][1:]
        for obj in to_delete:
            # 从所有集合中移除对象
            for coll in bpy.data.collections:
                if obj.name in coll.objects:
                    coll.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)

    # 更新对象名称显示当前设置
    current_obj.name = f"Current: {preset_name} [xy={render.resolution_x}x{render.resolution_y}@{render.resolution_percentage}%, sp={current_samples}, Rng={scene.frame_start}-{scene.frame_end}, {path_type}]"
