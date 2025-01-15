bl_info = {
    "name": "Snapshot",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "Take a snapshot of the current 3D view",
    "version": (1, 3)
}

import bpy
import os
import gpu
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader
import webbrowser

# Global variables to store the image, texture, and handler
snapshot_image = None
snapshot_texture = None
display_snapshot_state = False  # 该变量用于判断缓存画面是否打开
draw_handler = None

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
        fragColor = vec4(color.rgb, color.a * opacity);
    }
'''

# Pre-compile the shader to avoid compiling it every time we draw
shader = GPUShader(vertex_shader, fragment_shader)

# Define a property group to hold the file path
class SnapshotItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()

# Define the operator for taking a snapshot
class OBJECT_OT_TakeSnapshot(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "Take Snapshot"
    bl_description = "Take a snapshot of the current 3D view"
    
    def execute(self, context):
        global snapshot_texture, snapshot_image

        # Save the snapshot to the snapshot directory
        filename = f"snapshot_{len(context.scene.snapshot_list)}.png"
        filepath = os.path.join(snapshot_dir, filename)
        bpy.ops.screen.screenshot_area(filepath=filepath)
        
        # Create a new item and add the file path to the collection
        item = context.scene.snapshot_list.add()
        item.name = filename
        item.filepath = filepath

        # Automatically select the new snapshot in the list
        context.scene.snapshot_list_index = len(context.scene.snapshot_list) - 1

        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        snapshot_texture = None  # Reset the texture
        snapshot_image = None  # Reset the image
        return {'FINISHED'}

# Define the operator for displaying the snapshot
class OBJECT_OT_DisplaySnapshot(bpy.types.Operator):
    bl_idname = "object.display_snapshot_state"
    bl_label = "Display Snapshot"
    bl_description = "Display the saved snapshot over the 3D view"
    
    def execute(self, context):
        global snapshot_texture, snapshot_image, display_snapshot_state, draw_handler

        # Toggle the display state 每按一次进行一次反转
        display_snapshot_state = not display_snapshot_state
        
        if display_snapshot_state:
            # Load the snapshot image
            selected_index = context.scene.snapshot_list_index
            if selected_index >= 0 and selected_index < len(context.scene.snapshot_list):
                selected_item = context.scene.snapshot_list[selected_index]
                filepath = selected_item.filepath
                if os.path.exists(filepath):
                    snapshot_image = bpy.data.images.load(filepath)
                    # Create a GPUTexture from the image
                    snapshot_texture = gpu.texture.from_image(snapshot_image)
                    context.scene['snapshot_filepath'] = filepath
                    # Add the draw handler
                    if draw_handler is None:
                        draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (context,), 'WINDOW', 'POST_PIXEL')
                    self.report({'INFO'}, f"Snapshot displayed from {filepath}")
                else:
                    self.report({'WARNING'}, "Snapshot file not found")
            else:
                self.report({'WARNING'}, "No snapshot selected")
        else:
            # Remove the draw handler if not displaying
            if draw_handler is not None:
                bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
                draw_handler = None
            # Clear the image and texture to free up resources
            if snapshot_image:
                bpy.data.images.remove(snapshot_image)
                snapshot_image = None
            snapshot_texture = None
        
        # Force a redraw of the 3D view
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
        global snapshot_texture, snapshot_image, draw_handler
        
        # Get the selected snapshot
        selected_index = context.scene.snapshot_list_index
        selected_item = context.scene.snapshot_list[selected_index]
        filepath = selected_item.filepath

        if os.path.exists(filepath):
            # Load the selected snapshot image
            snapshot_image = bpy.data.images.load(filepath)
            snapshot_texture = gpu.texture.from_image(snapshot_image)
            context.scene['snapshot_filepath'] = filepath

            # If display_snapshot_state is True, display the snapshot
            if display_snapshot_state:
                # Remove the previous draw handler if it exists
                if draw_handler is not None:
                    bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
                    draw_handler = None
                    
                # Add the draw handler
                draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (context,), 'WINDOW', 'POST_PIXEL')
                self.report({'INFO'}, f"Snapshot displayed from {filepath}")

            # Force a redraw of the 3D view
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            region.tag_redraw()
        else:
            self.report({'WARNING'}, "Snapshot file not found")

        return {'FINISHED'}

# Define the operator for opening the snapshots folder
class OBJECT_OT_OpenSnapshotsFolder(bpy.types.Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "Open Snapshots Folder"
    bl_description = "Open the folder where snapshots are stored"

    def execute(self, context):
        webbrowser.open(snapshot_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

# Define the operator for clearing the snapshot list
class OBJECT_OT_ClearSnapshotList(bpy.types.Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "Clear Snapshot List"
    bl_description = "Clear the snapshot list without deleting the files"

    def execute(self, context):
        context.scene.snapshot_list.clear()
        self.report({'INFO'}, "Snapshot list cleared")
        return {'FINISHED'}

# Define the draw function 提供了一个绘制画面的函数
def draw_snapshot(context):
    global snapshot_texture
    if snapshot_texture:
        # Get the dimensions of the 3D view
        region = context.region
        width = region.width
        height = region.height

        # Get the opacity value
        opacity = context.scene.snapshot_opacity / 100.0

        # Draw the image using GPU module with custom shader
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {
                "pos": ((0, 0), (width, 0), (width, height), (0, height)),
                "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
            },
        )
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_float("opacity", opacity)
        shader.uniform_sampler("image", snapshot_texture)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

# Define the UI list class for the snapshot list
class UL_SnapshotList(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.name)

# Property update function
def update_snapshot_selection(self, context):
    if display_snapshot_state:
        bpy.ops.object.select_snapshot()

### 面板类函数 ###
class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "Snapshot Panel"
    bl_idname = "VIEW3D_PT_snapshot_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Snapshot'
    
    def draw(self, context):
        layout = self.layout
        layout.operator("object.take_snapshot", text="Take Snapshot")
        layout.operator("object.display_snapshot_state", text="Display Snapshot")
        layout.prop(context.scene, "snapshot_opacity", text="Snapshot Opacity")
        layout.label(text="Snapshot List:")
        col = layout.column()
        col.template_list("UL_SnapshotList", "snapshot_list", context.scene, "snapshot_list", context.scene, "snapshot_list_index")
        layout.operator("object.open_snapshots_folder", text="Open Snapshots Folder")
        layout.operator("object.clear_snapshot_list", text="Clear Snapshot List")

### 注册类函数 ###
allClass = [
    SnapshotItem, 
    OBJECT_OT_TakeSnapshot, 
    OBJECT_OT_DisplaySnapshot, 
    OBJECT_OT_SelectSnapshot, 
    OBJECT_OT_OpenSnapshotsFolder, 
    OBJECT_OT_ClearSnapshotList, 
    UL_SnapshotList, 
    VIEW3D_PT_SnapshotPanel
]

def register():
    for cls in allClass:
        bpy.utils.register_class(cls)
    bpy.types.Scene.snapshot_opacity = bpy.props.IntProperty(
        name="Snapshot Opacity",
        description="Opacity of the snapshot overlay",
        default=100,
        min=0,
        max=100
    )
    bpy.types.Scene.snapshot_list = bpy.props.CollectionProperty(type=SnapshotItem)
    bpy.types.Scene.snapshot_list_index = bpy.props.IntProperty(name="Index for snapshot_list", default=0, update=update_snapshot_selection)

def unregister():
    del bpy.types.Scene.snapshot_opacity
    del bpy.types.Scene.snapshot_list
    del bpy.types.Scene.snapshot_list_index
    for cls in allClass:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()