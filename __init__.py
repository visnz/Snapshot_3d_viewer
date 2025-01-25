bl_info = {
    "name": "Snapshot and STOOL",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "Take a snapshot of the current 3D view and manage parenting operations",
    "version": (1, 0, 0)
}

import bpy, os, gpu, webbrowser
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader

snap_img, snap_tex, draw_hdlr, disp_snap, vis_state = {}, {}, {}, {}, {}
snap_dir = os.path.join(os.path.dirname(__file__), "snapshots")
if not os.path.exists(snap_dir): os.makedirs(snap_dir)

vertex_shader = '''
    uniform mat4 MVP;
    in vec2 pos, texCoord;
    out vec2 texCoord_interp;
    void main() { gl_Position = MVP * vec4(pos, 0.0, 1.0); texCoord_interp = texCoord; }
'''

fragment_shader = '''
    uniform sampler2D img;
    uniform float opacity;
    in vec2 texCoord_interp;
    out vec4 fragColor;
    void main() {
        vec4 color = texture(img, texCoord_interp);
        color.rgb /= color.a;
        color.rgb = (color.rgb - 0.5) * 1.008 + 0.5;
        fragColor = vec4(color.r * 1.004, color.g * 1.004, color.b * 1.004, color.a * opacity);
    }
'''

shader = GPUShader(vertex_shader, fragment_shader)

class SnapshotItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()
    area_id: bpy.props.StringProperty()

class OBJECT_OT_TakeSnapshot(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "拍摄"
    bl_description = "Take a snapshot of the current 3D view"
    
    def execute(self, context):
        global snap_tex, snap_img, disp_snap, vis_state
        
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        disp_snap[area_id], vis_state[area_id] = False, False
        if draw_hdlr.get(area_id):
            bpy.types.SpaceView3D.draw_handler_remove(draw_hdlr[area_id], 'WINDOW')
            draw_hdlr[area_id] = None
        if snap_img.get(area_id):
            bpy.data.images.remove(snap_img[area_id])
            snap_img[area_id] = None
        snap_tex[area_id] = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW': region.tag_redraw()

        filename = f"snapshot_{area_id}_{len(context.scene.snapshot_list)}.png"
        filepath = os.path.join(snap_dir, filename)
        bpy.ops.screen.screenshot_area(filepath=filepath)
        
        item = context.scene.snapshot_list.add()
        item.name, item.filepath, item.area_id = filename, filepath, area_id
        context.scene.snapshot_list_index = len(context.scene.snapshot_list) - 1

        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        
        disp_snap[area_id], vis_state[area_id] = True, True
        snap_img[area_id] = bpy.data.images.load(filepath)
        snap_tex[area_id] = gpu.texture.from_image(snap_img[area_id])
        context.scene['snapshot_filepath'] = filepath
        if draw_hdlr.get(area_id) is None:
            draw_hdlr[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id,), 'WINDOW', 'POST_PIXEL')
        
        for region in context.area.regions:
            if region.type == 'WINDOW': region.tag_redraw()

        return {'FINISHED'}

class OBJECT_OT_ToggleSnapshotDisplay(bpy.types.Operator):
    bl_idname = "object.toggle_snapshot_display"
    bl_label = "Toggle Snapshot Display"
    bl_description = "Toggle the display of the snapshot in the current 3D view"

    def execute(self, context):
        global snap_tex, snap_img, draw_hdlr, disp_snap, vis_state

        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        disp_snap[area_id] = not disp_snap.get(area_id, False)
        
        if disp_snap[area_id]:
            selected_index = context.scene.snapshot_list_index
            if 0 <= selected_index < len(context.scene.snapshot_list):
                selected_item = context.scene.snapshot_list[selected_index]
                filepath = selected_item.filepath
                if os.path.exists(filepath) and selected_item.area_id == area_id:
                    snap_img[area_id] = bpy.data.images.load(filepath)
                    snap_tex[area_id] = gpu.texture.from_image(snap_img[area_id])
                    context.scene['snapshot_filepath'] = filepath
                    if draw_hdlr.get(area_id) is None:
                        draw_hdlr[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id,), 'WINDOW', 'POST_PIXEL')
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
                    if region.type == 'WINDOW': region.tag_redraw()
        
        return {'FINISHED'}

class OBJECT_OT_SelectSnapshot(bpy.types.Operator):
    bl_idname = "object.select_snapshot"
    bl_label = "Select Snapshot"
    bl_description = "Select a snapshot to display"

    def execute(self, context):
        global snap_tex, snap_img, draw_hdlr, disp_snap, vis_state
        
        selected_index = context.scene.snapshot_list_index
        selected_item = context.scene.snapshot_list[selected_index]
        filepath, original_area_id = selected_item.filepath, selected_item.area_id

        if os.path.exists(filepath):
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if disp_snap.get(area_id, False):
                        disp_snap[area_id], vis_state[area_id] = False, False
                        for region in area.regions:
                            if region.type == 'WINDOW': region.tag_redraw()

            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if area_id == original_area_id:
                        disp_snap[original_area_id], vis_state[original_area_id] = True, True
                        snap_img[original_area_id] = bpy.data.images.load(filepath)
                        snap_tex[original_area_id] = gpu.texture.from_image(snap_img[original_area_id])
                        context.scene['snapshot_filepath'] = filepath
                        if draw_hdlr.get(original_area_id) is None:
                            draw_hdlr[original_area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (original_area_id,), 'WINDOW', 'POST_PIXEL')
                        self.report({'INFO'}, f"Snapshot displayed from {filepath} in its original area")
                        for region in area.regions:
                            if region.type == 'WINDOW': region.tag_redraw()
                        break
        else:
            self.report({'WARNING'}, "Snapshot file not found")

        return {'FINISHED'}

class OBJECT_OT_OpenSnapshotsFolder(bpy.types.Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "打开快照文件夹"
    bl_description = "打开快照文件夹"

    def execute(self, context):
        webbrowser.open(snap_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

class OBJECT_OT_ClearSnapshotList(bpy.types.Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "清除快照列表"
    bl_description = "清除快照列表（不会清除文件，从头开始覆盖）"

    def execute(self, context):
        context.scene.snapshot_list_index = -1
        context.scene.snapshot_list.clear()

        for area_id in list(disp_snap.keys()):
            if disp_snap[area_id]:
                disp_snap[area_id], vis_state[area_id] = False, False
                if draw_hdlr.get(area_id):
                    bpy.types.SpaceView3D.draw_handler_remove(draw_hdlr[area_id], 'WINDOW')
                    draw_hdlr[area_id] = None
                if snap_img.get(area_id):
                    bpy.data.images.remove(snap_img[area_id])
                    snap_img[area_id] = None
                snap_tex[area_id] = None

        self.report({'INFO'}, "Snapshot list cleared and all snapshots disabled")
        return {'FINISHED'}

def draw_snapshot(area_id):
    global snap_tex, vis_state
    current_area = bpy.context.area
    if current_area and str(hash(current_area.as_pointer()) % 10000).zfill(4) == area_id:
        if vis_state.get(area_id) and snap_tex.get(area_id):
            region = bpy.context.region
            width, height = region.width, region.height

            img_width, img_height = snap_img[area_id].size
            img_aspect, region_aspect = img_width / img_height, width / height

            if region_aspect > img_aspect:
                draw_height, draw_width = height, height * img_aspect
                draw_x, draw_y = (width - draw_width) / 2, 0
            else:
                draw_width, draw_height = width, width / img_aspect
                draw_x, draw_y = 0, (height - draw_height) / 2

            opacity = bpy.context.scene.snapshot_opacity / 100.0
            slider_pos = bpy.context.scene.slider_position

            batch = batch_for_shader(
                shader, 'TRI_FAN',
                {
                    "pos": ((draw_x + draw_width * (1 - slider_pos), draw_y), (draw_x + draw_width, draw_y), (draw_x + draw_width, draw_y + draw_height), (draw_x + draw_width * (1 - slider_pos), draw_y + draw_height)),
                    "texCoord": ((1 - slider_pos, 0), (1, 0), (1, 1), (1 - slider_pos, 1)),
                },
            )
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("opacity", opacity)
            shader.uniform_sampler("image", snap_tex[area_id])
            batch.draw(shader)
            gpu.state.blend_set('NONE')

            line_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            vertices = [(width * (1 - slider_pos), 0), (width * (1 - slider_pos), height)]
            line_batch = batch_for_shader(
                line_shader, 'LINES',
                {"pos": vertices}
            )
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
    bl_label = "Snapshot"
    bl_idname = "VIEW3D_PT_snapshot_panel_Snapshot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        is_displaying_snapshot = disp_snap.get(area_id, False)

        layout.label(text="渲染快照")
        layout.operator("object.take_snapshot")
        layout.operator("object.toggle_snapshot_display", icon='HIDE_OFF' if is_displaying_snapshot else 'HIDE_ON')
        layout.prop(context.scene, "snapshot_opacity")
        layout.label(text=f"当前3D Viewer ID: {area_id}")
        layout.label(text="快照列表")
        col = layout.column()
        col.template_list("UL_SnapshotList", "snapshot_list", context.scene, "snapshot_list", context.scene, "snapshot_list_index")
        layout.operator("object.open_snapshots_folder")
        layout.operator("object.clear_snapshot_list")
        layout.operator("object.drag_slider", text="拖动滑动杆")

class OBJECT_OT_DragSlider(bpy.types.Operator):
    bl_idname = "object.drag_slider"
    bl_label = "Drag Slider"
    bl_description = "拖动滑动杆以比较快照和当前3D视图"
    
    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            region = context.region
            mouse_x = event.mouse_region_x
            context.scene.slider_position = 1 - (mouse_x / region.width)
            context.area.tag_redraw()
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return {'CANCELLED'}

allClass = [
    SnapshotItem, 
    OBJECT_OT_TakeSnapshot, 
    OBJECT_OT_ToggleSnapshotDisplay, 
    OBJECT_OT_SelectSnapshot, 
    OBJECT_OT_OpenSnapshotsFolder, 
    OBJECT_OT_ClearSnapshotList, 
    UL_SnapshotList, 
    VIEW3D_PT_SnapshotPanel,
    OBJECT_OT_DragSlider,
]

def register():
    for cls in allClass: bpy.utils.register_class(cls)
    bpy.types.Scene.snapshot_opacity = bpy.props.IntProperty(name="快照不透明度", default=100, min=0, max=100)
    bpy.types.Scene.snapshot_list = bpy.props.CollectionProperty(type=SnapshotItem)
    bpy.types.Scene.snapshot_list_index = bpy.props.IntProperty(name="Index for snapshot_list", default=0, update=update_snapshot_selection)
    bpy.types.Scene.slider_position = bpy.props.FloatProperty(name="滑动杆位置", default=0.5, min=0.0, max=1.0)

def unregister():
    del bpy.types.Scene.snapshot_opacity
    del bpy.types.Scene.snapshot_list
    del bpy.types.Scene.snapshot_list_index
    del bpy.types.Scene.slider_position
    for cls in allClass: bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()