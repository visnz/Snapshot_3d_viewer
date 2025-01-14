bl_info = {
    "name": "Snapshot",
    "category": "3D View",
    "author": "Github copilot",
    "blender": (3, 0, 0),
    "location": "UI",
    "description": "Take a snapshot of the current 3D view",
    "version": (1, 0)
}
import bpy
import os
import gpu
from gpu_extras.batch import batch_for_shader

# Global variables to store the image, texture, and handler
snapshot_image = None
snapshot_texture = None
display_snapshot = False
draw_handler = None

# Define the operator for taking a snapshot
class OBJECT_OT_TakeSnapshot(bpy.types.Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "Take Snapshot"
    bl_description = "Take a snapshot of the current 3D view"
    
    def execute(self, context):
        global snapshot_texture
        # Save the snapshot to a directory with write permissions
        user_home_dir = os.path.expanduser("~")
        filepath = os.path.join(user_home_dir, "snapshot.png")
        bpy.ops.screen.screenshot_area(filepath=filepath)
        context.scene['snapshot_filepath'] = filepath
        self.report({'INFO'}, f"Snapshot saved to {filepath}")
        snapshot_texture = None  # Reset the texture
        return {'FINISHED'}

# Define the operator for displaying the snapshot
class OBJECT_OT_DisplaySnapshot(bpy.types.Operator):
    bl_idname = "object.display_snapshot"
    bl_label = "Display Snapshot"
    bl_description = "Display the saved snapshot over the 3D view"
    
    def execute(self, context):
        global snapshot_texture, display_snapshot, draw_handler

        # Toggle the display state
        display_snapshot = not display_snapshot
        
        if display_snapshot:
            # Load the snapshot image
            if 'snapshot_filepath' in context.scene:
                filepath = context.scene['snapshot_filepath']
                if os.path.exists(filepath):
                    snapshot_image = bpy.data.images.load(filepath)
                    # Create a GPUTexture from the image
                    snapshot_texture = gpu.texture.from_image(snapshot_image)
                    # Add the draw handler
                    if draw_handler is None:
                        draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_snapshot, (context,), 'WINDOW', 'POST_PIXEL')
                    self.report({'INFO'}, f"Snapshot displayed from {filepath}")
                else:
                    self.report({'WARNING'}, "Snapshot file not found")
            else:
                self.report({'WARNING'}, "No snapshot found")
        else:
            # Remove the draw handler if not displaying
            if draw_handler is not None:
                bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
                draw_handler = None
        
        # Force a redraw of the 3D view
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        region.tag_redraw()
        
        return {'FINISHED'}

# Define the draw function
def draw_snapshot(context):
    global snapshot_texture
    if snapshot_texture:
        # Get the dimensions of the 3D view
        region = context.region
        width = region.width
        height = region.height
        
        # Draw the image using GPU module
        shader = gpu.shader.from_builtin('IMAGE')
        batch = batch_for_shader(
            shader, 'TRI_FAN',
            {
                "pos": ((0, 0), (width, 0), (width, height), (0, height)),
                "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
            },
        )
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_sampler("image", snapshot_texture)
        batch.draw(shader)
        gpu.state.blend_set('NONE')

# Define the panel
class VIEW3D_PT_SnapshotPanel(bpy.types.Panel):
    bl_label = "Snapshot Panel"
    bl_idname = "VIEW3D_PT_snapshot_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Snapshot'
    
    def draw(self, context):
        layout = self.layout
        layout.operator("object.take_snapshot", text="Take Snapshot")
        layout.operator("object.display_snapshot", text="Display Snapshot")

# Register the classes
def register():
    bpy.utils.register_class(OBJECT_OT_TakeSnapshot)
    bpy.utils.register_class(OBJECT_OT_DisplaySnapshot)
    bpy.utils.register_class(VIEW3D_PT_SnapshotPanel)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_TakeSnapshot)
    bpy.utils.unregister_class(OBJECT_OT_DisplaySnapshot)
    bpy.utils.unregister_class(VIEW3D_PT_SnapshotPanel)

if __name__ == "__main__":
    register()