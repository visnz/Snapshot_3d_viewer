import bpy, os, gpu, webbrowser
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader
import webbrowser

snapshot_image, snapshot_texture, draw_handler, display_snapshot_state, visibility_state = {}, {}, {}, {}, {}
addon_directory = os.path.dirname(__file__)
snapshot_dir = os.path.join(addon_directory, "snapshots")
os.makedirs(snapshot_dir, exist_ok=True)

vertex_shader = '''
    uniform mat4 ModelViewProjectionMatrix;
    in vec2 pos;
    in vec2 texCoord;
    out vec2 texCoord_interp;
    void main() {
        gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0, 1.0);
        texCoord_interp = texCoord;
    }
'''

fragment_shader = '''
    uniform sampler2D image;
    uniform float opacity;
    in vec2 texCoord_interp;
    out vec4 fragColor;
    void main() {
        vec4 color = texture(image, texCoord_interp);
        fragColor = vec4(color.rgb*0.996, color.a * opacity);
    }
'''

shader = GPUShader(vertex_shader, fragment_shader)

class SnapshotItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    filepath: bpy.props.StringProperty() # type: ignore
    area_id: bpy.props.StringProperty() # type: ignore

def render_snapshot(filepath, time_limit):
    scene = bpy.context.scene
    area = bpy.context.area
    region = next(region for region in area.regions if region.type == 'WINDOW')
    original_engine = scene.render.engine
    original_time_limit = scene.cycles.time_limit if original_engine == 'CYCLES' else None
    original_camera = scene.camera
    original_view = bpy.context.space_data.region_3d.view_matrix.copy()
    original_view_camera = bpy.context.space_data.region_3d.view_perspective == 'CAMERA'
    temp_camera = None

    if not original_view_camera:
        bpy.ops.object.camera_add()
        temp_camera = bpy.context.object
        scene.camera = temp_camera
        override = bpy.context.copy()
        override['area'] = area
        override['region'] = region
        override['space_data'] = next(space for space in area.spaces if space.type == 'VIEW_3D')
        with bpy.context.temp_override(**override):
            bpy.ops.view3d.camera_to_view()

    scene.render.engine = original_engine
    if original_engine == 'CYCLES':
        scene.cycles.time_limit = time_limit
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    if original_engine == 'CYCLES':
        scene.cycles.time_limit = original_time_limit
    scene.camera = original_camera
    bpy.context.space_data.region_3d.view_matrix = original_view
    bpy.context.space_data.region_3d.view_perspective = 'CAMERA' if original_view_camera else 'PERSP'
    if temp_camera:
        bpy.data.objects.remove(temp_camera, do_unlink=True)
    return region.width, region.height

class OBJECT_OT_TakeSnapshot(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "拍摄"
    bl_description = "拍摄3D viewer区域部分快照"
    
    def execute(self, context):
        global snapshot_texture, snapshot_image, display_snapshot_state
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        display_snapshot_state[area_id], visibility_state[area_id] = False, False
        if draw_handler.get(area_id):
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler[area_id], 'WINDOW')
        if snapshot_image.get(area_id):
            bpy.data.images.remove(snapshot_image[area_id])
        snapshot_texture[area_id], snapshot_image[area_id], draw_handler[area_id] = None, None, None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        region = next(region for region in context.area.regions if region.type == 'WINDOW')
        if context.scene.use_full_render and context.space_data.shading.type == 'RENDERED':
            filename = f"渲染_{area_id}_{len(context.scene.snapshot_list)}_{region.width}x{region.height}.png"
        else:
            filename = f"快照_{area_id}_{len(context.scene.snapshot_list)}_{region.width}x{region.height}.png"
        filepath = os.path.join(snapshot_dir, filename)
        if context.scene.use_full_render and context.space_data.shading.type == 'RENDERED':
            time_limit = context.scene.render_time_limit
            region_width, region_height = render_snapshot(filepath, time_limit)
        else:
            bpy.ops.screen.screenshot_area(filepath=filepath)
            region_width, region_height = region.width, region.height
        item = context.scene.snapshot_list.add()
        item.name, item.filepath, item.area_id = filename, filepath, area_id
        context.scene.snapshot_list_index = len(context.scene.snapshot_list) - 1
        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        display_snapshot_state[area_id], visibility_state[area_id] = True, True
        snapshot_image[area_id] = bpy.data.images.load(filepath)
        snapshot_texture[area_id] = gpu.texture.from_image(snapshot_image[area_id])
        context.scene['snapshot_filepath'] = filepath
        if not draw_handler.get(area_id):
            draw_handler[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id, None, None, region_width, region_height), 'WINDOW', 'POST_PIXEL')
        for region in context.area.regions:
            if region.type == 'WINDOW':
                region.tag_redraw()
        return {'FINISHED'}

class OBJECT_OT_ToggleSnapshotDisplay(bpy.types.Operator):
    bl_idname = "object.toggle_snapshot_display"
    bl_label = "快照开关"
    bl_description = "控制是否显示快照，眼睛图形睁开为启用"
    def execute(self, context):
        global snapshot_texture, snapshot_image, draw_handler, display_snapshot_state, visibility_state
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        display_snapshot_state[area_id] = not display_snapshot_state.get(area_id, False)
        if display_snapshot_state[area_id]:
            selected_index = context.scene.snapshot_list_index
            if 0 <= selected_index < len(context.scene.snapshot_list):
                selected_item = context.scene.snapshot_list[selected_index]
                filepath = selected_item.filepath
                if os.path.exists(filepath) and selected_item.area_id == area_id:
                    snapshot_image[area_id] = bpy.data.images.load(filepath)
                    snapshot_texture[area_id] = gpu.texture.from_image(snapshot_image[area_id])
                    context.scene['snapshot_filepath'] = filepath
                    if not draw_handler.get(area_id):
                        # 从文件名中提取宽度和高度
                        name_parts = selected_item.name.split('_')
                        region_width, region_height = map(int, name_parts[-1].split('x'))
                        draw_handler[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id, None, None, region_width, region_height), 'WINDOW', 'POST_PIXEL')
                    visibility_state[area_id] = True
                    self.report({'INFO'}, f"Snapshot displayed from {filepath}")
                else:
                    self.report({'WARNING'}, "Snapshot file not found or does not belong to this area")
            else:
                self.report({'WARNING'}, "No snapshot selected")
        else:
            visibility_state[area_id] = False
        bpy.context.window_manager.update_tag()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        return {'FINISHED'}

class OBJECT_OT_SelectSnapshot(bpy.types.Operator):
    bl_idname = "object.select_snapshot"
    bl_label = "选择快照"
    bl_description = "选择用于展示的快照"

    def execute(self, context):
        global snapshot_texture, snapshot_image, draw_handler, display_snapshot_state, visibility_state
        selected_index = context.scene.snapshot_list_index
        selected_item = context.scene.snapshot_list[selected_index]
        filepath, original_area_id = selected_item.filepath, selected_item.area_id
        if os.path.exists(filepath):
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if display_snapshot_state.get(area_id, False):
                        display_snapshot_state[area_id], visibility_state[area_id] = False, False
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if area_id == original_area_id:
                        display_snapshot_state[original_area_id], visibility_state[original_area_id] = True, True
                        snapshot_image[original_area_id] = bpy.data.images.load(filepath)
                        snapshot_texture[original_area_id] = gpu.texture.from_image(snapshot_image[original_area_id])
                        context.scene['snapshot_filepath'] = filepath
                        if not draw_handler.get(original_area_id):
                            # 从文件名中提取宽度和高度
                            name_parts = selected_item.name.split('_')
                            region_width, region_height = map(int, name_parts[-1].split('x'))
                            draw_handler[original_area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (original_area_id, None, None, region_width, region_height), 'WINDOW', 'POST_PIXEL')
                        self.report({'INFO'}, f"Snapshot displayed from {filepath} in its original area")
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()
                        break
        else:
            self.report({'WARNING'}, "Snapshot file not found")
        return {'FINISHED'}

class OBJECT_OT_OpenSnapshotsFolder(bpy.types.Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "打开快照文件夹"
    bl_description = "打开快照文件夹"
    def execute(self, context):
        webbrowser.open(snapshot_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

class OBJECT_OT_ClearSnapshotList(bpy.types.Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "清除快照列表"
    bl_description = "清除快照列表（不会清除文件，从头开始覆盖）"
    def execute(self, context):
        context.scene.snapshot_list_index = -1
        context.scene.snapshot_list.clear()
        for area_id in display_snapshot_state.keys():
            display_snapshot_state[area_id], visibility_state[area_id] = False, False
            if draw_handler.get(area_id):
                bpy.types.SpaceView3D.draw_handler_remove(draw_handler[area_id], 'WINDOW')
            if snapshot_image.get(area_id):
                bpy.data.images.remove(snapshot_image[area_id])
            snapshot_texture[area_id], snapshot_image[area_id], draw_handler[area_id] = None, None, None
        self.report({'INFO'}, "Snapshot list cleared and all snapshots disabled")
        return {'FINISHED'}

def check_snapshot_files(context):
    # 检查快照列表中的所有文件是否存在
    for item in list(context.scene.snapshot_list):
        if not os.path.exists(item.filepath):
            context.scene.snapshot_list.remove(item)

def draw_snapshot(area_id, frame_width, frame_height, region_width, region_height):
    global snapshot_texture, visibility_state
    current_area = bpy.context.area
    if current_area and str(hash(current_area.as_pointer()) % 10000).zfill(4) == area_id:
        check_snapshot_files(bpy.context)
        if visibility_state.get(area_id) and snapshot_texture.get(area_id):
            # 检查当前展示的快照文件是否存在
            filepath = bpy.context.scene['snapshot_filepath']
            if not os.path.exists(filepath):
                # 文件不存在，关闭所有快照模式开关
                display_snapshot_state[area_id], visibility_state[area_id] = False, False
                if draw_handler.get(area_id):
                    bpy.types.SpaceView3D.draw_handler_remove(draw_handler[area_id], 'WINDOW')
                return

            width, height = region_width, region_height
            draw_x, draw_y = 0, 0
            draw_width, draw_height = width, height
            opacity = bpy.context.scene.snapshot_opacity / 100.0
            slider_position = bpy.context.scene.slider_position
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": ((draw_x + draw_width * (1 - slider_position), draw_y), (draw_x + draw_width, draw_y), (draw_x + draw_width, draw_y + draw_height), (draw_x + draw_width * (1 - slider_position), draw_y + draw_height)), "texCoord": ((1 - slider_position, 0), (1, 0), (1, 1), (1 - slider_position, 1))})
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("opacity", opacity)
            shader.uniform_sampler("image", snapshot_texture[area_id])
            batch.draw(shader)
            gpu.state.blend_set('NONE')
            line_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            vertices = [(width * (1 - slider_position), 0), (width * (1 - slider_position), height)]
            line_batch = batch_for_shader(line_shader, 'LINES', {"pos": vertices})
            gpu.state.blend_set('ALPHA')
            line_shader.bind()
            line_shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
            line_batch.draw(line_shader)
            gpu.state.blend_set('NONE')

class UL_SnapshotList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

def update_snapshot_selection(self, context):
    bpy.ops.object.select_snapshot()

class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "快照"
    bl_idname = "VIEW3D_PT_snapshot_panel_Snapshot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    def draw(self, context):
        layout = self.layout
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        is_displaying_snapshot = display_snapshot_state.get(area_id, False)
        layout.label(text="渲染快照")
        layout.operator("object.take_snapshot")
        layout.operator("object.toggle_snapshot_display", icon='HIDE_OFF' if is_displaying_snapshot else 'HIDE_ON')
        # 暂时隐藏这两个按钮
        # layout.prop(context.scene, "use_full_render", text="EEVEE/Cycles模式下完全渲染")
        # layout.prop(context.scene, "render_time_limit", text="渲染时间限制（秒）")
        layout.label(text=f"快照列表（当前窗口ID: {area_id}）")
        col = layout.column()
        col.template_list("UL_SnapshotList", "snapshot_list", context.scene, "snapshot_list", context.scene, "snapshot_list_index")
        layout.prop(context.scene, "snapshot_opacity")
        layout.operator("object.open_snapshots_folder")
        layout.operator("object.clear_snapshot_list")
        layout.operator("object.drag_slider")

class OBJECT_OT_DragSlider(bpy.types.Operator):
    bl_idname = "object.drag_slider"
    bl_label = "Drag Slider"
    bl_description = "拖动滑动杆以比较快照和当前3D视图"
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            region = context.region
            context.scene.slider_position = 1 - (event.mouse_region_x / region.width)
            context.area.tag_redraw()
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        return {'RUNNING_MODAL'}
    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return {'CANCELLED'}

allClass = [SnapshotItem, OBJECT_OT_TakeSnapshot, OBJECT_OT_ToggleSnapshotDisplay, OBJECT_OT_SelectSnapshot, OBJECT_OT_OpenSnapshotsFolder, OBJECT_OT_ClearSnapshotList, UL_SnapshotList, VIEW3D_PT_SnapshotPanel, OBJECT_OT_DragSlider]

def register():
    for cls in allClass:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snapshot_opacity = bpy.props.IntProperty(
        name="不透明度",
        description="快照覆盖在画面的不透明度",
        default=100,
        min=0,
        max=100
    )
    bpy.types.Scene.snapshot_list = bpy.props.CollectionProperty(type=SnapshotItem)
    bpy.types.Scene.snapshot_list_index = bpy.props.IntProperty(name="Index for snapshot_list", default=0, update=update_snapshot_selection)
    bpy.types.Scene.use_full_render = bpy.props.BoolProperty(name="EEVEE/Cycles模式下完全渲染", description="是否在EEVEE/Cycles模式下进行完全渲染", default=False)
    bpy.types.Scene.render_time_limit = bpy.props.IntProperty(name="渲染时间限制（秒）", description="渲染时间限制（秒）", default=2, min=1, max=100)
    bpy.types.Scene.slider_position = bpy.props.FloatProperty(
        name="滑动杆位置",
        description="滑动杆在3D Viewer中的位置",
        default=0.5,
        min=0.0,
        max=1.0
    )

def unregister():
    del bpy.types.Scene.snapshot_opacity
    del bpy.types.Scene.snapshot_list
    del bpy.types.Scene.snapshot_list_index
    del bpy.types.Scene.use_full_render
    del bpy.types.Scene.render_time_limit
    del bpy.types.Scene.slider_position
    for cls in allClass:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()