bl_info = {
    "name": "Snapshot and STOOL",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "Take a snapshot of the current 3D view and manage parenting operations",
    "version": (1, 0, 0)
}

import bpy
import os
import gpu
import subprocess
import platform
from bpy.types import Operator
from gpu.types import GPUShader
from gpu_extras.batch import batch_for_shader
import webbrowser
import json

## =============== Snapshot ===============
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
    name: bpy.props.StringProperty() # type: ignore
    filepath: bpy.props.StringProperty() # type: ignore

# Define the operator for taking a snapshot
class OBJECT_OT_TakeSnapshot(Operator):
    bl_idname = "object.take_snapshot"
    bl_label = "拍摄"
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
class OBJECT_OT_DisplaySnapshot(Operator):
    bl_idname = "object.display_snapshot_state"
    bl_label = "快照开关"
    bl_description = "展示已保存的快照"
    
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
class OBJECT_OT_SelectSnapshot(Operator):
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
class OBJECT_OT_OpenSnapshotsFolder(Operator):
    bl_idname = "object.open_snapshots_folder"
    bl_label = "打开快照文件夹"
    bl_description = "打开快照文件夹"

    def execute(self, context):
        webbrowser.open(snapshot_dir)
        self.report({'INFO'}, "Snapshots folder opened")
        return {'FINISHED'}

# Define the operator for clearing the snapshot list
class OBJECT_OT_ClearSnapshotList(Operator):
    bl_idname = "object.clear_snapshot_list"
    bl_label = "清除快照列表"
    bl_description = "清除快照列表（不会清除文件，从头开始覆盖）"

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
    bl_label = "Snapshot and STOOL Panel"
    bl_idname = "VIEW3D_PT_snapshot_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Snapshot & STOOL'
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="渲染快照")
        layout.operator("object.take_snapshot")
        layout.operator("object.display_snapshot_state")
        layout.prop(context.scene, "snapshot_opacity")
        layout.label(text="快照列表")
        col = layout.column()
        col.template_list("UL_SnapshotList", "snapshot_list", context.scene, "snapshot_list", context.scene, "snapshot_list_index")
        layout.operator("object.open_snapshots_folder")
        layout.operator("object.clear_snapshot_list")
        
        layout.separator()
        layout.label(text="父子级操作")
        layout.operator("object.parent_to_empty_visn")
        layout.operator("object.parent_to_empty_collection_visn")
        layout.operator("object.select_parent_visn")
        layout.operator("object.release_all_children_to_world_visn")
        layout.operator("object.release_all_children_to_subparent_visn")
        layout.operator("object.solo_pick_visn")
        
        layout.separator()
        layout.label(text="搭建类操作")
        layout.operator("object.fast_camera_visn")
        layout.operator("object.add_light_with_constraint")
        layout.operator("wm.open_project_folder_visn")
        layout.operator("object.save_selection_visn")
        layout.operator("object.load_selection_visn")

### STOOL 插件的类和操作 ###
def centro(sel):
    x = sum(obj.location[0] for obj in sel) / len(sel)
    y = sum(obj.location[1] for obj in sel) / len(sel)
    z = sum(obj.location[2] for obj in sel) / len(sel)
    return (x, y, z)

def centro_global(sel):
    x = sum(obj.matrix_world.translation[0] for obj in sel) / len(sel)
    y = sum(obj.matrix_world.translation[1] for obj in sel) / len(sel)
    z = sum(obj.matrix_world.translation[2] for obj in sel) / len(sel)
    return (x, y, z)

def get_children(my_object):
    return [ob for ob in bpy.data.objects if ob.parent == my_object]

class FastCentreCamera(Operator):
    bl_idname = "object.fast_camera_visn"
    bl_label = "中心约束摄像机"
    bl_description = "创建一个以选择物体为目标点的，中心点+PSR锁定的的摄像机"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 获取创建点
        objs = context.selected_objects
        loc = centro_global(objs) if objs else (0, 0, 0)

        # 创建摄像机
        bpy.ops.object.camera_add(enter_editmode=False, align='VIEW', location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1))
        bpy.context.active_object.name = 'NewCamera'
        cams = context.selected_objects
        bpy.context.space_data.camera = cams[0]
        bpy.ops.view3d.camera_to_view()
        bpy.ops.object.add(type='EMPTY', location=cams[0].location, rotation=cams[0].rotation_euler)
        bpy.context.active_object.name = 'CameraProtection'
        bpy.ops.object.constraint_add(type='DAMPED_TRACK')
        camP = context.selected_objects
        cams[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        cams[0].lock_location[:] = [True, True, True]
        cams[0].lock_rotation[:] = [True, True, True]

        # 创建原点的空物体
        bpy.ops.object.add(type='EMPTY', location=loc)
        bpy.context.active_object.name = 'CameraCentre'
        camC = context.selected_objects
        camP[0].select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        camP[0].select_set(False)
        cams[0].select_set(False)
        camP[0].constraints["Damped Track"].target = bpy.data.objects[camC[0].name]
        camP[0].constraints["Damped Track"].track_axis = 'TRACK_NEGATIVE_Z'

        return {'FINISHED'}

class SoloPick(Operator):
    # 断开所选物体的所有父子级关系，捡出来放在世界层级，子级归更上一层父级管。
    bl_idname = "object.solo_pick_visn"
    bl_label = "拎出（断开父子级）"
    bl_description = "断开所有选择物体的父子级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass

        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if not obj.parent:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    children.select_set(False)
            else:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    bpy.context.view_layer.objects.active = obj.parent
                    bpy.ops.object.parent_no_inverse_set(keep_transform=True)
                    children.select_set(False)
        for obj in objs:
            obj.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            obj.select_set(False)
        for obj in objs:
            obj.select_set(True)
        return {'FINISHED'}

class SelectParent(Operator):
    bl_idname = "object.select_parent_visn"
    bl_label = "选择所有父级"
    bl_description = "选择被选中对象的所有父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if obj.parent:
                obj.parent.select_set(True)
        return {'FINISHED'}

class RAQ(Operator):
    bl_idname = "object.release_all_children_to_world_visn"
    bl_label = "释放子对象（到世界）"
    bl_description = "释放子对象（到世界）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            for children in get_children(obj):
                children.select_set(True)
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                children.select_set(False)
        return {'FINISHED'}

class RAQtoSubparent(Operator):
    bl_idname = "object.release_all_children_to_subparent_visn"
    bl_label = "释放子对象（到上级）"
    bl_description = "释放子对象（到上级）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set()
        except:
            pass
        NOParent = False
        for obj in objs:
            obj.select_set(False)
        for obj in objs:
            if not obj.parent:
                NOParent = True
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    children.select_set(False)
            else:
                for children in get_children(obj):
                    children.select_set(True)
                    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
                    bpy.context.view_layer.objects.active = obj.parent
                    bpy.ops.object.parent_no_inverse_set(keep_transform=True)
                    children.select_set(False)
        if not NOParent:
            for obj in objs:
                bpy.context.view_layer.objects.active = obj.parent
                obj.parent.select_set(True)
        return {'FINISHED'}

class P2E_Collection(Operator):
    bl_idname = "object.parent_to_empty_collection_visn"
    bl_label = "所选物体 到新集合"
    bl_description = "所有选择的物体到新父级，并送入新集合"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        def move_to_collection(obj, collection):
            # 递归地将对象及其所有子对象移动到指定集合中
            # 首先将对象从其所有集合中移除
            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            # 将对象添加到新集合中
            collection.objects.link(obj)
            # 递归地处理子对象
            for child in obj.children:
                move_to_collection(child, collection)

        objs = context.selected_objects
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        # 获取所有选中对象的中心位置
        loc = centro(objs)
        same_parent = all(o.parent == objs[0].parent for o in objs)

        # 创建一个新的集合
        new_collection = bpy.data.collections.new(name="New Collection")
        context.scene.collection.children.link(new_collection)

        # 将新集合设置为活跃集合
        layer_collection = context.view_layer.layer_collection
        for layer in layer_collection.children:
            if layer.collection == new_collection:
                context.view_layer.active_layer_collection = layer

        # 创建一个新的空对象并设置位置
        bpy.ops.object.select_all(action='DESELECT')
        if len(objs) == 1:
            bpy.ops.object.add(type='EMPTY', location=loc, rotation=objs[0].rotation_euler)
        else:
            bpy.ops.object.add(type='EMPTY', location=loc)

        new_empty = context.object

        # 如果所有选中对象有相同的父级，则将新空对象设置为该父级的子级
        if same_parent:
            new_empty.parent = objs[0].parent

        # 将新空对象添加到新集合中
        try:
            new_collection.objects.link(new_empty)
        except:
            pass

        # 确保新空对象在当前视图层中
        context.view_layer.objects.active = new_empty

        # 遍历所有选中对象并递归地将它们及其子对象移动到新集合中
        for o in objs:
            move_to_collection(o, new_collection)
            # 设置父级
            o.select_set(True)
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            o.select_set(False)

        return {'FINISHED'}

class P2E(Operator):
    bl_idname = "object.parent_to_empty_visn"
    bl_label = "所选物体 到父级"
    bl_description = "所有所选物体到父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        last_active_obj = context.view_layer.objects.active  # 获取最后一次选中的活跃对象

        try:
            bpy.ops.object.mode_set()
        except:
            pass

        loc = centro(objs)
        same_parent = all(o.parent == objs[0].parent for o in objs)

        if len(objs) == 1:
            bpy.ops.object.add(type='EMPTY', location=loc, rotation=objs[0].rotation_euler)
        else:
            bpy.ops.object.add(type='EMPTY', location=loc)
        
        new_empty = context.object  # 获取新创建的空物体
        
        # 获取最后一次选中的活跃对象的集合
        if last_active_obj is not None:
            last_active_collections = last_active_obj.users_collection

            # 将新创建的空物体添加到活跃对象的集合中
            try:
                for collection in last_active_collections:
                    collection.objects.link(new_empty)

                # 从当前活跃集合中移除新创建的空物体
                context.collection.objects.unlink(new_empty)
            except:
                pass
            # 将子对象从原来的集合中移除，并添加到新的集合中
            for o in objs:
                for collection in o.users_collection:
                    collection.objects.unlink(o)
                for collection in last_active_collections:
                    collection.objects.link(o)

        if same_parent:
            new_empty.parent = objs[0].parent

        for o in objs:
            o.select_set(True)
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            o.select_set(False)

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

##### ======= 选择组的效果 =====================
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
        group_name_parts = [obj.name if len(obj.name) <= 8 else obj.name[:8] + "..." for obj in selected_objs]
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
##### ======= 选择组的效果 =====================

### 注册类函数 ###
allClass = [
    SnapshotItem, 
    OBJECT_OT_TakeSnapshot, 
    OBJECT_OT_DisplaySnapshot, 
    OBJECT_OT_SelectSnapshot, 
    OBJECT_OT_OpenSnapshotsFolder, 
    OBJECT_OT_ClearSnapshotList, 
    UL_SnapshotList, 
    VIEW3D_PT_SnapshotPanel,
    FastCentreCamera,
    SoloPick,
    SelectParent,
    RAQ,
    RAQtoSubparent,
    P2E_Collection,
    OpenProjectFolderOperator,
    AddLightWithConstraint,
    SaveSelection,
    LoadSelection,
    P2E
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

def unregister():
    del bpy.types.Scene.snapshot_opacity
    del bpy.types.Scene.snapshot_list
    del bpy.types.Scene.snapshot_list_index
    for cls in allClass:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()