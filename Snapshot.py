import bpy
import os
import gpu
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader
import webbrowser

# Global variables to store the image, texture, handler, and visibility state for each region
snapshot_image = {}
snapshot_texture = {}
draw_handler = {}
display_snapshot_state = {}  # 使用字典来存储每个窗口的快照开关状态
visibility_state = {}  # 使用字典来控制绘制处理程序的可见性

# Get the directory of the current script (plugin directory)
addon_directory = os.path.dirname(__file__)

# Directory to store snapshots
snapshot_dir = os.path.join(addon_directory, "snapshots")

# Ensure the snapshot directory exists
if not os.path.exists(snapshot_dir):
    os.makedirs(snapshot_dir)

# Custom shader for blending with alpha
vertex_shader = '''
    uniform mat4 ModelViewProjectionMatrix;
    in vec2 pos;
    in vec2 texCoord;
    out vec2 texCoord_interp;

    void main()
    {
        gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0, 1.0);
        texCoord_interp = texCoord;
    }
'''

fragment_shader = '''
    uniform sampler2D image;
    uniform float opacity;
    in vec2 texCoord_interp;
    out vec4 fragColor;

    void main()
    {
        vec4 color = texture(image, texCoord_interp);
        color.rgb /= color.a;
        color.rgb = (color.rgb - 0.5) * 1.008 + 0.5;  // 使用固定的对比度值
        fragColor = vec4(color.r * 1.004, color.g * 1.004, color.b * 1.004, color.a * opacity);  // 使用固定的亮度值
    }
'''

# Pre-compile the shader to avoid compiling it every time we draw
shader = GPUShader(vertex_shader, fragment_shader)

# Define a property group to hold the file path and its corresponding area ID
class SnapshotItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore
    filepath: bpy.props.StringProperty() # type: ignore
    area_id: bpy.props.StringProperty() # type: ignore

# Define the operator for taking a snapshot
class OBJECT_OT_TakeSnapshot(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "拍摄"
    bl_description = "Take a snapshot of the current 3D view"
    
    def execute(self, context):
        global snapshot_texture, snapshot_image, display_snapshot_state

        # 首先关闭快照模式
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        display_snapshot_state[area_id] = False
        visibility_state[area_id] = False
        if draw_handler.get(area_id) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handler[area_id], 'WINDOW')
            draw_handler[area_id] = None
        if snapshot_image.get(area_id):
            bpy.data.images.remove(snapshot_image[area_id])
            snapshot_image[area_id] = None
        snapshot_texture[area_id] = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()

        # 将快照保存到快照目录
        filename = f"snapshot_{area_id}_{len(context.scene.snapshot_list)}.png"
        filepath = os.path.join(snapshot_dir, filename)
        bpy.ops.screen.screenshot_area(filepath=filepath)
        
        # 创建一个新项并将文件路径和区域ID添加到集合中
        item = context.scene.snapshot_list.add()
        item.name = filename
        item.filepath = filepath
        item.area_id = area_id

        # 自动选择列表中的新快照
        context.scene.snapshot_list_index = len(context.scene.snapshot_list) - 1

        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        
        # 拍摄快照后立刻激活该快照并开启快照模式
        display_snapshot_state[area_id] = True
        visibility_state[area_id] = True
        snapshot_image[area_id] = bpy.data.images.load(filepath)
        snapshot_texture[area_id] = gpu.texture.from_image(snapshot_image[area_id])
        context.scene['snapshot_filepath'] = filepath
        if draw_handler.get(area_id) is None:
            draw_handler[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id,), 'WINDOW', 'POST_PIXEL')
        
        # 强制重绘当前3D视图
        for region in context.area.regions:
            if region.type == 'WINDOW':
                region.tag_redraw()

        return {'FINISHED'}

# Define the operator for toggling the snapshot display state
class OBJECT_OT_ToggleSnapshotDisplay(bpy.types.Operator):
    bl_idname = "object.toggle_snapshot_display"
    bl_label = "Toggle Snapshot Display"
    bl_description = "Toggle the display of the snapshot in the current 3D view"

    def execute(self, context):
        global snapshot_texture, snapshot_image, draw_handler, display_snapshot_state, visibility_state

        # 获取当前3D视图的区域ID，并转换为4位字符串
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        print(f"Toggling snapshot display for area_id: {area_id}")

        # 切换当前区域的显示状态
        display_snapshot_state[area_id] = not display_snapshot_state.get(area_id, False)
        
        if display_snapshot_state[area_id]:
            # 加载快照图像
            selected_index = context.scene.snapshot_list_index
            if selected_index >= 0 and selected_index < len(context.scene.snapshot_list):
                selected_item = context.scene.snapshot_list[selected_index]
                filepath = selected_item.filepath
                if os.path.exists(filepath) and selected_item.area_id == area_id:
                    snapshot_image[area_id] = bpy.data.images.load(filepath)
                    # 从图像创建一个GPU纹理
                    snapshot_texture[area_id] = gpu.texture.from_image(snapshot_image[area_id])
                    context.scene['snapshot_filepath'] = filepath
                    # 添加绘制处理程序
                    if draw_handler.get(area_id) is None:
                        draw_handler[area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (area_id,), 'WINDOW', 'POST_PIXEL')
                    visibility_state[area_id] = True
                    self.report({'INFO'}, f"Snapshot displayed from {filepath}")
                else:
                    self.report({'WARNING'}, "Snapshot file not found or does not belong to this area")
            else:
                self.report({'WARNING'}, "No snapshot selected")
        else:
            # 隐藏绘制处理程序而不是移除它
            visibility_state[area_id] = False
        
        # 强制更新UI状态
        bpy.context.window_manager.update_tag()

        # 强制重绘3D视图
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        
        return {'FINISHED'}

# Define the operator for selecting a snapshot
class OBJECT_OT_SelectSnapshot(bpy.types.Operator):
    bl_idname = "object.select_snapshot"
    bl_label = "Select Snapshot"
    bl_description = "Select a snapshot to display"

    def execute(self, context):
        global snapshot_texture, snapshot_image, draw_handler, display_snapshot_state, visibility_state
        
        # 获取选择的快照
        selected_index = context.scene.snapshot_list_index
        selected_item = context.scene.snapshot_list[selected_index]
        filepath = selected_item.filepath
        original_area_id = selected_item.area_id
        print(f"Selecting snapshot for original_area_id: {original_area_id}")

        if os.path.exists(filepath):
            # 关闭所有区域的快照显示
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if display_snapshot_state.get(area_id, False):
                        display_snapshot_state[area_id] = False
                        visibility_state[area_id] = False
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()

            # 确保快照显示在其原始区域
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area_id = str(hash(area.as_pointer()) % 10000).zfill(4)
                    if area_id == original_area_id:
                        display_snapshot_state[original_area_id] = True
                        visibility_state[original_area_id] = True
                        snapshot_image[original_area_id] = bpy.data.images.load(filepath)
                        snapshot_texture[original_area_id] = gpu.texture.from_image(snapshot_image[original_area_id])
                        context.scene['snapshot_filepath'] = filepath
                        if draw_handler.get(original_area_id) is None:
                            draw_handler[original_area_id] = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (original_area_id,), 'WINDOW', 'POST_PIXEL')
                        self.report({'INFO'}, f"Snapshot displayed from {filepath} in its original area")
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                region.tag_redraw()
                        break
        else:
            self.report({'WARNING'}, "Snapshot file not found")

        return {'FINISHED'}

# Define the operator for opening the snapshots folder
class OBJECT_OT_OpenSnapshotsFolder(bpy.types.Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "打开快照文件夹"
    bl_description = "打开快照文件夹"

    def execute(self, context):
        webbrowser.open(snapshot_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

# Define the operator for clearing the snapshot list
class OBJECT_OT_ClearSnapshotList(bpy.types.Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "清除快照列表"
    bl_description = "清除快照列表（不会清除文件，从头开始覆盖）"

    def execute(self, context):
        # 将快照列表的选择设置为空
        context.scene.snapshot_list_index = -1
        
        context.scene.snapshot_list.clear()

        # 清除所有快照数据和状态
        for area_id in list(display_snapshot_state.keys()):
            if display_snapshot_state[area_id]:
                display_snapshot_state[area_id] = False
                visibility_state[area_id] = False
                if draw_handler.get(area_id) is not None:
                    bpy.types.SpaceView3D.draw_handler_remove(draw_handler[area_id], 'WINDOW')
                    draw_handler[area_id] = None
                if snapshot_image.get(area_id):
                    bpy.data.images.remove(snapshot_image[area_id])
                    snapshot_image[area_id] = None
                snapshot_texture[area_id] = None

        self.report({'INFO'}, "Snapshot list cleared and all snapshots disabled")
        return {'FINISHED'}

# 提供了一个绘制画面的函数
def draw_snapshot(area_id):
    global snapshot_texture, visibility_state
    # 获取当前绘制的区域
    current_area = bpy.context.area
    if current_area and str(hash(current_area.as_pointer()) % 10000).zfill(4) == area_id:
        if visibility_state.get(area_id, False) and snapshot_texture.get(area_id):
            # 获取3D视图的尺寸
            region = bpy.context.region
            width = region.width
            height = region.height

            # 获取快照的尺寸
            img_width = snapshot_image[area_id].size[0]
            img_height = snapshot_image[area_id].size[1]
            img_aspect = img_width / img_height
            region_aspect = width / height

            # 计算缩放尺寸以保持宽高比
            if region_aspect > img_aspect:
                draw_height = height
                draw_width = height * img_aspect
                draw_x = (width - draw_width) / 2
                draw_y = 0
            else:
                draw_width = width
                draw_height = width / img_aspect
                draw_x = 0
                draw_y = (height - draw_height) / 2

            # 获取不透明度值
            opacity = bpy.context.scene.snapshot_opacity / 100.0
            slider_position = bpy.context.scene.slider_position

            # 使用GPU模块绘制图像和自定义着色器
            batch = batch_for_shader(
                shader, 'TRI_FAN',
                {
                    "pos": ((draw_x + draw_width * (1 - slider_position), draw_y), (draw_x + draw_width, draw_y), (draw_x + draw_width, draw_y + draw_height), (draw_x + draw_width * (1 - slider_position), draw_y + draw_height)),
                    "texCoord": ((1 - slider_position, 0), (1, 0), (1, 1), (1 - slider_position, 1)),
                },
            )
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_float("opacity", opacity)
            shader.uniform_sampler("image", snapshot_texture[area_id])
            batch.draw(shader)
            gpu.state.blend_set('NONE')

            # 绘制滑动杆
            line_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
            vertices = [(width * (1 - slider_position), 0), (width * (1 - slider_position), height)]
            line_batch = batch_for_shader(
                line_shader, 'LINES',
                {"pos": vertices}
            )
            gpu.state.blend_set('ALPHA')
            line_shader.bind()
            line_shader.uniform_float("color", (1.0, 1.0, 1.0, 1.0))  # 白色
            line_batch.draw(line_shader)
            gpu.state.blend_set('NONE')

# 定义快照列表的UI列表类
class UL_SnapshotList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

# 属性更新函数
def update_snapshot_selection(self, context):
    bpy.ops.object.select_snapshot()

### 面板类函数 ###
class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "Snapshot"
    bl_idname = "VIEW3D_PT_snapshot_panel_Snapshot"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    
    def draw(self, context):
        layout = self.layout

        # 获取当前3D视图窗口的ID
        area_id = str(hash(context.area.as_pointer()) % 10000).zfill(4)
        is_displaying_snapshot = display_snapshot_state.get(area_id, False)

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

# 定义滑动杆拖动操作符
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

### 注册类函数 ###
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
    for cls in allClass:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snapshot_opacity = bpy.props.IntProperty(
        name="快照不透明度",
        description="快照覆盖在画面的不透明度",
        default=100,
        min=0,
        max=100
    )
    bpy.types.Scene.snapshot_list = bpy.props.CollectionProperty(type=SnapshotItem)
    bpy.types.Scene.snapshot_list_index = bpy.props.IntProperty(name="Index for snapshot_list", default=0, update=update_snapshot_selection)
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
    del bpy.types.Scene.slider_position
    for cls in allClass:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()