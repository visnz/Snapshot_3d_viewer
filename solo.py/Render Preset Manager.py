import os
import re
import bpy
from bpy.props import (StringProperty, IntProperty, BoolProperty)
from bpy.types import Operator, PropertyGroup, Panel

bl_info = {
    "name": "Render Preset Manager",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Render Presets",
    "description": "Manage render presets for quick switching",
    "category": "Render",
}

# --------------------------
# Property Groups
# --------------------------

class RenderPresetSettings(PropertyGroup):
    resolution_x: IntProperty(name="Resolution X", default=1920, min=4)
    resolution_y: IntProperty(name="Resolution Y", default=1080, min=4)
    samples: IntProperty(name="Samples", default=1536, min=1)
    frame_start: IntProperty(name="Frame Start", default=0, min=0)
    frame_end: IntProperty(name="Frame End", default=100, min=0)
    relative_path: StringProperty(name="Relative Path", subtype='DIR_PATH', default="\\__Cache__\\")
    absolute_path: StringProperty(name="Absolute Path", subtype='DIR_PATH', default="F:\\__Cache__\\")
    use_absolute_path: BoolProperty(
        name="Use Absolute Path",
        description="Toggle between absolute and relative paths",
        default=False
    )

# --------------------------
# Operators
# --------------------------

class RENDER_OT_create_presets(Operator):
    """Create preset objects"""
    bl_idname = "render.create_presets"
    bl_label = "Create Presets"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "No active camera found")
            return {'CANCELLED'}

        # Get camera collection
        cam_coll = None
        for collection in bpy.data.collections:
            if cam.name in collection.objects:
                cam_coll = collection
                break
        if not cam_coll:
            cam_coll = context.scene.collection

        # Delete old preset objects
        for child in cam.children:
            if re.match(r'^\d+\..+', child.name) or child.name == "Current":
                for coll in bpy.data.collections:
                    if child.name in coll.objects:
                        coll.objects.unlink(child)
                bpy.data.objects.remove(child, do_unlink=True)

        # Get current settings
        props = context.scene.render_preset_settings
        render = context.scene.render

        # Create preset objects
        presets = [
            ('1. HD    ', f"[xy={props.resolution_x}x{props.resolution_y}, sp={props.samples}, Rng={props.frame_start}-{props.frame_end}]"),
            ('2. Style ', f"[xy=100%, sp=100%, Rng=50]"),
            ('3. prev  ', f"[xy=100%, sp=10%, Rng=0-100]"),
            ('4. demo  ', f"[xy=50%, sp=30%, Rng=100%]"),
            ('5. folder', f"[\"{props.relative_path}\",\"{props.absolute_path}\"]")
        ]

        for preset_name, params in presets:
            empty = bpy.data.objects.new(preset_name, None)
            cam_coll.objects.link(empty)
            if empty != cam:
                empty.parent = cam
            empty.name = f"{preset_name}:{params}"

        # Create current settings display
        current_empty = bpy.data.objects.new("Current", None)
        cam_coll.objects.link(current_empty)
        if current_empty != cam:
            current_empty.parent = cam

        # Apply HD preset by default
        bpy.ops.render.apply_preset(preset_type='HD')
        update_current_settings_display(cam, context.scene)

        self.report({'INFO'}, "Preset objects created")
        return {'FINISHED'}

    def invoke(self, context, event):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "No active camera found")
            return {'CANCELLED'}

        # Initialize settings
        props = context.scene.render_preset_settings
        render = context.scene.render

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

        # Resolution
        col = layout.column(align=True)
        col.label(text="Final Render Settings:")
        row = col.row(align=True)
        row.prop(props, "resolution_x", text="X")
        row.prop(props, "resolution_y", text="Y")

        # Samples
        layout.separator()
        layout.prop(props, "samples", text="Samples")

        # Frame range
        layout.separator()
        col = layout.column(align=True)
        col.label(text="Frame Range:")
        row = col.row(align=True)
        row.prop(props, "frame_start", text="Start")
        row.prop(props, "frame_end", text="End")

        # Paths
        layout.separator()
        layout.prop(props, "absolute_path", text="Absolute Path")
        layout.prop(props, "relative_path", text="Relative Path")

class RENDER_OT_apply_preset(Operator):
    """Apply render preset"""
    bl_idname = "render.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {'REGISTER', 'UNDO'}

    preset_type: StringProperty(
        name="Preset Type",
        description="Type of preset to apply",
        default="Style"
    )

    def execute(self, context):
        cam = context.scene.camera
        if not cam:
            self.report({'ERROR'}, "No active camera found")
            return {'CANCELLED'}

        # Get all presets
        presets = {}
        hd_params = {}
        folder_params = {}

        for child in cam.children:
            if ':' in child.name:
                preset_name = re.sub(r'^\d+\.\s*', '', child.name.split(':', 1)[0].strip().lower())
                params = self.parse_preset_params(child.name.split(':', 1)[1])

                if preset_name == 'folder':
                    folder_params = params
                elif preset_name == 'hd':
                    hd_params = params
                else:
                    presets[preset_name] = params

        if self.preset_type.lower() not in presets and self.preset_type.lower() != 'hd':
            self.report({'ERROR'}, f"Preset {self.preset_type} not found")
            return {'CANCELLED'}

        render = context.scene.render
        cycles = context.scene.cycles if hasattr(context.scene, 'cycles') else None
        eevee = context.scene.eevee if hasattr(context.scene, 'eevee') else None

        # Update output path
        if folder_params:
            self.update_output_path(render, context.scene, folder_params, self.preset_type.lower())

        # Apply settings
        if self.preset_type.lower() == 'hd':
            self.apply_hd_settings(render, context.scene, cycles, eevee, hd_params)
        else:
            self.apply_preset_settings(render, context.scene, cycles, eevee, presets[self.preset_type.lower()], hd_params)

        # Update display
        update_current_settings_display(cam, context.scene, self.preset_type.lower())

        self.report({'INFO'}, f"Applied {self.preset_type} preset")
        return {'FINISHED'}

    def update_output_path(self, render, scene, folder_params, preset_type):
        """Update output path based on settings"""
        props = scene.render_preset_settings
        path_key = "absolute" if props.use_absolute_path else "relative"
        base_path = folder_params.get(path_key, "").strip('"').replace('\\', '/').rstrip('/')

        if not base_path:
            return

        render_dir = f"Render_{preset_type}"
        scene_dir = f"{scene.name}_{preset_type}"
        filename = f"{scene.name}_{preset_type}"

        render.filepath = f"{base_path}/{render_dir}/{scene_dir}/{filename}".replace('//', '/')

    def apply_hd_settings(self, render, scene, cycles, eevee, params):
        """Apply HD preset settings"""
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
        """Apply other preset settings"""
        # Resolution
        if 'xy' in params:
            size = params['xy'].lower()
            if '%' in size:
                try:
                    percent = int(size.replace('%', ''))
                    render.resolution_percentage = percent
                except ValueError:
                    pass

        # Samples
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

        # Frame range
        if 'rng' in params:
            range_val = params['rng']
            if '%' in range_val:  # Use HD range
                if '-' in hd_params.get('rng', '0-100'):
                    start, end = map(int, hd_params['rng'].split('-'))
                    scene.frame_start = start
                    scene.frame_end = end
            elif '-' in range_val:  # Custom range
                try:
                    start, end = map(int, range_val.split('-'))
                    scene.frame_start = start
                    scene.frame_end = end
                except ValueError:
                    pass
            else:  # Single frame
                try:
                    frame = int(range_val)
                    scene.frame_start = frame
                    scene.frame_end = frame
                except ValueError:
                    pass

    def parse_preset_params(self, param_str):
        """Parse preset parameters from string"""
        params = {}
        bracket_content = param_str.split(']')[0].split('[')[-1].strip()

        if '"' in bracket_content:  # Path format
            paths = [p.strip().strip('"') for p in bracket_content.split(',')]
            if len(paths) >= 2:
                params["relative"] = paths[0]
                params["absolute"] = paths[1]
                return params

        # Regular parameters
        for param in bracket_content.split(','):
            param = param.strip()
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip().lower()] = value.strip().strip('"')

        return params

# --------------------------
# Utility Functions
# --------------------------

def update_current_settings_display(cam, scene, preset_name="HD"):
    """Update the current settings display object"""
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

    current_samples = 0
    if cycles:
        current_samples = cycles.samples
    elif eevee:
        current_samples = eevee.taa_render_samples

    props = scene.render_preset_settings
    path_type = "Abs" if props.use_absolute_path else "Rel"

    # Find or create current settings object
    current_obj = None
    for child in cam.children:
        if child.name.startswith("Current"):
            current_obj = child
            break

    if not current_obj:
        current_obj = bpy.data.objects.new("Current", None)
        cam_coll.objects.link(current_obj)
        if current_obj != cam:
            current_obj.parent = cam
    elif sum(1 for child in cam.children if child.name.startswith("Current")) > 1:
        to_delete = [child for child in cam.children if child.name.startswith("Current")][1:]
        for obj in to_delete:
            for coll in bpy.data.collections:
                if obj.name in coll.objects:
                    coll.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)

    # Update display
    current_obj.name = f"Current: {preset_name} [xy={render.resolution_x}x{render.resolution_y}@{render.resolution_percentage}%, sp={current_samples}, Rng={scene.frame_start}-{scene.frame_end}, {path_type}]"

# --------------------------
# UI Panel
# --------------------------

class RENDER_PT_preset_panel(Panel):
    bl_label = "Render Presets"
    bl_idname = "RENDER_PT_preset_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Render Presets'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        
        # Render preset management
        layout.label(text="Render Presets")
        layout.operator("render.create_presets", text="Create Presets", icon='SETTINGS')

        # Path type toggle
        props = scene.render_preset_settings
        row = layout.row()
        row.prop(props, "use_absolute_path", text="Use Absolute Path", toggle=True)

        # Preset buttons
        box = layout.box()
        row = box.row(align=True)
        row.operator("render.apply_preset", text="HD").preset_type = 'HD'
        row.operator("render.apply_preset", text="Style").preset_type = 'Style'

        row = box.row(align=True)
        row.operator("render.apply_preset", text="prev").preset_type = 'prev'
        row.operator("render.apply_preset", text="demo").preset_type = 'demo'

# --------------------------
# Registration
# --------------------------

classes = (
    RenderPresetSettings,
    RENDER_OT_create_presets,
    RENDER_OT_apply_preset,
    RENDER_PT_preset_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.render_preset_settings = bpy.props.PointerProperty(type=RenderPresetSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.render_preset_settings

if __name__ == "__main__":
    register()