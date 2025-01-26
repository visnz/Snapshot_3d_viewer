
import bpy, os, gpu, webbrowser
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader

snap_img, snap_tex, draw_hdl, disp_snap, vis_state = {}, {}, {}, {}, {}
addon_dir = os.path.dirname(__file__)
snap_dir = os.path.join(addon_dir, "snapshots")
os.makedirs(snap_dir, exist_ok=True)

vert_shader = '''
    uniform mat4 ModelViewProjectionMatrix;
    in vec2 pos;
    in vec2 texCoord;
    out vec2 texCoord_interp;
    void main() {
        gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0, 1.0);
        texCoord_interp = texCoord;
    }
'''

frag_shader = '''
    uniform sampler2D image;
    uniform float opacity;
    in vec2 texCoord_interp;
    out vec4 fragColor;
    void main() {
        vec4 color = texture(image, texCoord_interp);
        fragColor = vec4(color.rgb*0.996, color.a * opacity);
    }
'''

shader = GPUShader(vert_shader, frag_shader)

class SnapItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()
    area_id: bpy.props.StringProperty()

def render_snap(filepath, time_limit):
    scene = bpy.context.scene
    area = bpy.context.area
    region = next(region for region in area.regions if region.type == 'WINDOW')
    orig_engine = scene.render.engine
    orig_time_limit = scene.cycles.time_limit if orig_engine == 'CYCLES' else None
    orig_camera = scene.camera
    orig_view = bpy.context.space_data.region_3d.view_matrix.copy()
    orig_view_camera = bpy.context.space_data.region_3d.view_perspective == 'CAMERA'
    temp_camera = None

    if not orig_view_camera:
        bpy.ops.object.camera_add()
        temp_camera = bpy.context.object
        scene.camera = temp_camera
        override = bpy.context.copy()
        override['area'] = area
        override['region'] = region
        override['space_data'] = next(space for space in area.spaces if space.type == 'VIEW_3D')
        with bpy.context.temp_override(**override):
            bpy.ops.view3d.camera_to_view()

    scene.render.engine = orig_engine
    if orig_engine == 'CYCLES':
        scene.cycles.time_limit = time_limit
    bpy.context.scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    if orig_engine == 'CYCLES':
        scene.cycles.time_limit = orig_time_limit
    scene.camera = orig_camera
    bpy.context.space_data.region_3d.view_matrix = orig_view
    bpy.context.space_data.region_3d.view_perspective = 'CAMERA' if orig_view_camera else 'PERSP'
    if temp_camera:
        bpy.data.objects.remove(temp_camera, do_unlink=True)
    return region.width, region.height

class TakeSnap(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "拍摄"
    bl_description = "拍摄3D viewer区域部分快照"
    
    def execute(self, context):
        global snap_tex, snap_img, draw_hdl, disp_snap
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        disp_snap[area_id], vis_state[area_id] = False, False
        if draw_hdl.get(area_id):
            bpy.types.SpaceView3D.draw_handler_remove(draw_hdl[area_id], 'WINDOW')
        if snap_img.get(area_id):
            bpy.data.images.remove(snap_img[area_id])
        snap_tex[area_id], snap_img[area_id], draw_hdl[area_id] = None, None, None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        region = next(region for region in context.area.regions if region.type == 'WINDOW')
        filename = f"Snapshot_{area_id}_{len(context.scene.snapshot_list)}.png"
        filepath = os.path.join(snap_dir, filename)
        if context.scene.use_full_render and context.space_data.shading.type == 'RENDERED':
            time_limit = context.scene.render_time_limit
            region_width, region_height = render_snap(filepath, time_limit)
        else:
            bpy.ops.screen.screenshot_area(filepath=filepath)
            region_width, region_height = region.width, region.height
        item = context.scene.snapshot_list.add()
        item.name, item.filepath, item.area_id = filename, filepath, area_id
        context.scene.snapshot_list_index = len(context.scene.snapshot_list) - 1
        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        disp_snap[area_id], vis_state[area_id] = True, True
        snap_img[area_id] = bpy.data.images.load(filepath)
        snap_tex[area_id] = gpu.texture.from_image(snap_img[area_id])
        context.scene['snapshot_filepath'] = filepath
        if not draw_hdl.get(area_id):
            draw_hdl[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snap, (area_id, region_width, region_height), 'WINDOW', 'POST_PIXEL')
        for region in context.area.regions:
            if region.type == 'WINDOW':
                region.tag_redraw()
        return {'FINISHED'}

class ToggleSnapDisplay(bpy.types.Operator):
    bl_idname = "object.toggle_snapshot_display"
    bl_label = "快照开关"
    bl_description = "控制是否显示快照，眼睛图形睁开为启用"
    def execute(self, context):
        global snap_tex, snap_img, draw_hdl, disp_snap, vis_state
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        disp_snap[area_id] = not disp_snap.get(area_id, False)
        if disp_snap[area_id]:
            sel_idx = context.scene.snapshot_list_index
            if 0 <= sel_idx < len(context.scene.snapshot_list):
                sel_item = context.scene.snapshot_list[sel_idx]
                filepath = sel_item.filepath
                if os.path.exists(filepath) and sel_item.area_id == area_id:
                    snap_img[area_id] = bpy.data.images.load(filepath)
                    snap_tex[area_id] = gpu.texture.from_image(snap_img[area_id])
                    context.scene['snapshot_filepath'] = filepath
                    if not draw_hdl.get(area_id):
                        region = next(region for region in context.area.regions if region.type == 'WINDOW')
                        region_width, region_height = region.width, region.height
                        draw_hdl[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snap, (area_id, region_width, region_height), 'WINDOW', 'POST_PIXEL')
                    vis_state[area_id] = True
                    self.report({'INFO'}, f"Snapshot displayed from {filepath}")
                else:
                    self.report({'WARNING'}, "Snapshot file not found or does not belong to this area")
            else:
                self.report({'WARNING'}, "No snapshot selected")
        else:
            vis_state[area_id] = False
        bpy.context.window_manager.update_tag()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        return {'FINISHED'}

class SelectSnap(bpy.types.Operator):
    bl_idname = "object.select_snapshot"
    bl_label = "选择快照"
    bl_description = "选择用于展示的快照"

    def execute(self, context):
        global snap_tex, snap_img, draw_hdl, disp_snap, vis_state
        sel_idx = context.scene.snapshot_list_index
        sel_item = context.scene.snapshot_list[sel_idx]
        filepath, orig_area_id = sel_item.filepath, sel_item.area_id
        if os.path.exists(filepath):
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if disp_snap.get(area_id, False):
                        disp_snap[area_id], vis_state[area_id] = False, False
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if area_id == orig_area_id:
                        disp_snap[orig_area_id], vis_state[orig_area_id] = True, True
                        snap_img[orig_area_id] = bpy.data.images.load(filepath)
                        snap_tex[orig_area_id] = gpu.texture.from_image(snap_img[orig_area_id])
                        context.scene['snapshot_filepath'] = filepath
                        if not draw_hdl.get(orig_area_id):
                            region = next(region for region in context.area.regions if region.type == 'WINDOW')
                            region_width, region_height = region.width, region.height
                            draw_hdl[orig_area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snap, (orig_area_id, region_width, region_height), 'WINDOW', 'POST_PIXEL')
                        self.report({'INFO'}, f"Snapshot displayed from {filepath} in its original area")
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()
                        break
        else:
            self.report({'WARNING'}, "Snapshot file not found")
        return {'FINISHED'}

class OpenSnapFolder(bpy.types.Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "打开快照文件夹"
    bl_description = "打开快照文件夹"
    def execute(self, context):
        webbrowser.open(snap_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

class ClearSnapList(bpy.types.Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "清除快照列表"
    bl_description = "清除快照列表（不会清除文件，从头开始覆盖）"
    def execute(self, context):
        context.scene.snapshot_list_index = -1
        context.scene.snapshot_list.clear()
        for area_id in disp_snap.keys():
            disp_snap[area_id], vis_state[area_id] = False, False
            if draw_hdl.get(area_id):
                bpy.types.SpaceView3D.draw_handler_remove(draw_hdl[area_id], 'WINDOW')
            if snap_img.get(area_id):
                bpy.data.images.remove(snap_img[area_id])
            snap_tex[area_id], snap_img[area_id], draw_hdl[area_id] = None, None, None
        self.report({'INFO'}, "Snapshot list cleared and all snapshots disabled")
        return {'FINISHED'}

def check_snap_files(context):
    for item in list(context.scene.snapshot_list):
        if not os.path.exists(item.filepath):
            context.scene.snapshot_list.remove(item)

def draw_snap(area_id, region_width, region_height):
    global snap_tex, vis_state
    cur_area = bpy.context.area
    if cur_area and str(hash(cur_area.as_pointer()) % 10000).zfill(4) == area_id:
        check_snap_files(bpy.context)
        if vis_state.get(area_id) and snap_tex.get(area_id):
            filepath = bpy.context.scene['snapshot_filepath']
            if not os.path.exists(filepath):
                disp_snap[area_id], vis_state[area_id] = False, False
                if draw_hdl.get(area_id):
                    bpy.types.SpaceView3D.draw_handler_remove(draw_hdl[area_id], 'WINDOW')
                return
            region = next(region for region in cur_area.regions if region.type == 'WINDOW')
            cur_width, cur_height = region.width, region.height
            scale_x = cur_width / region_width
            scale_y = cur_height / region_height
            scale = scale_x  # 保证快照宽度与窗口宽度相等
            draw_width = region_width * scale
            draw_height = region_height * scale
            draw_x = 0
            draw_y = (cur_height - draw_height) / 2
            opacity = bpy.context.scene.snapshot_opacity / 100.0
            pos = bpy.context.scene.slider_position
            batch = batch_for_shader(shader, 'TRI_FAN', {"pos": ((draw_x + draw_width * (1 - pos), draw_y), (draw_x + draw_width, draw_y), (draw_x + draw_width, draw_y + draw_height), (draw_x + draw_width * (1 - pos), draw_y + draw_height)), "texCoord": ((1 - pos, 0), (1, 0), (1, 1), (1 - pos, 1))})
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("opacity", opacity)
            shader.uniform_sampler("image", snap_tex[area_id])
            batch.draw(shader)
            gpu.state.blend_set('NONE')
            line_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            vertices = [(draw_x + draw_width * (1 - pos), draw_y), (draw_x + draw_width * (1 - pos), draw_y + draw_height)]
            line_batch = batch_for_shader(line_shader, 'LINES', {"pos": vertices})
            gpu.state.blend_set('ALPHA')
            line_shader.bind()
            line_shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))
            line_batch.draw(line_shader)
            gpu.state.blend_set('NONE')

class SnapList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

def update_snap_sel(self, context):
    bpy.ops.object.select_snapshot()

class SnapPanel(bpy.types.Panel):
    bl_label = "快照"
    bl_idname = "VIEW3D_PT_snapshot_panel_Snapshot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    def draw(self, context):
        layout = self.layout
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        is_disp_snap = disp_snap.get(area_id, False)
        layout.label(text="渲染快照")
        layout.operator("object.take_snapshot")
        layout.operator("object.toggle_snapshot_display", icon='HIDE_OFF' if is_disp_snap else 'HIDE_ON')
        layout.label(text=f"快照列表（当前窗口ID: {area_id}）")
        col = layout.column()
        col.template_list("SnapList", "snapshot_list", context.scene, "snapshot_list", context.scene, "snapshot_list_index")
        layout.prop(context.scene, "snapshot_opacity")
        layout.operator("object.open_snapshots_folder")
        layout.operator("object.clear_snapshot_list")
        layout.operator("object.drag_slider")

class DragSlider(bpy.types.Operator):
    bl_idname = "object.drag_slider"
    bl_label = "拖动"
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

all_cls = [SnapItem, TakeSnap, ToggleSnapDisplay, SelectSnap, OpenSnapFolder, ClearSnapList, SnapList, SnapPanel, DragSlider]

def register():
    for cls in all_cls:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snapshot_opacity = bpy.props.IntProperty(
        name="不透明度",
        description="快照覆盖在画面的不透明度",
        default=100,
        min=0,
        max=100
    )
    bpy.types.Scene.snapshot_list = bpy.props.CollectionProperty(type=SnapItem)
    bpy.types.Scene.snapshot_list_index = bpy.props.IntProperty(name="Index for snapshot_list", default=0, update=update_snap_sel)
    bpy.types.Scene.use_full_render = bpy.props.BoolProperty(name="EEVEE/Cycles模式下完全渲染", description="是否在EEVEE/Cycles模式下进行完全渲染", default=False)
    bpy.types.Scene.render_time_limit = bpy.props.IntProperty(name="渲染时间限制（秒）", description="渲染时间限制（秒）", default=2, min=1, max=100)
    bpy.types.Scene.slider_position = bpy.props.FloatProperty(
        name="滑动杆位置",
        description="滑动杆在3D Viewer中的位置",
        default=0.5,
        min=0.0,
        max=1.0
    )

    # 设置快捷键
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        km.keymap_items.new(DragSlider.bl_idname, 'RIGHTMOUSE', 'PRESS', alt=True)
        km.keymap_items.new(TakeSnap.bl_idname, 'RIGHTMOUSE', 'PRESS', ctrl=True, alt=True)

def unregister():
    del bpy.types.Scene.snapshot_opacity
    del bpy.types.Scene.snapshot_list
    del bpy.types.Scene.snapshot_list_index
    del bpy.types.Scene.use_full_render
    del bpy.types.Scene.render_time_limit
    del bpy.types.Scene.slider_position
    for cls in all_cls:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()