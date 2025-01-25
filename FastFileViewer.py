import bpy
import subprocess
import os

current_path_index = 0
explorer_paths = []
feature_enabled = True
initialized = False

def get_explorer_paths():
    paths = []
    try:
        powershell_script = '''
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $folders = @()
        $shell = New-Object -ComObject shell.application
        $shell.Windows() | ForEach-Object {
            if ($_.FullName -like "*explorer.exe") {
                $path = $_.document.folder.Self.Path
                if ($path -and (Test-Path $path)) {
                    $folders += $path
                }
            }
        }
        $folders | Out-String -Stream
        '''
        powershell_command = ["powershell", "-Command", powershell_script]
        powershell_output = subprocess.check_output(powershell_command, text=True, encoding='utf-8', errors='ignore')
        paths = [line.strip().replace('/', '\\') for line in powershell_output.splitlines() if os.path.isdir(line.strip().replace('/', '\\'))]
    except subprocess.CalledProcessError:
        raise Exception("PowerShell 脚本执行失败，无法获取 explorer.exe 窗口路径。")
    return paths

def update_explorer_paths():
    global explorer_paths, current_path_index
    explorer_paths = get_explorer_paths()
    current_path_index = 0
    bpy.context.scene.explorer_paths.clear()
    for path in explorer_paths:
        item = bpy.context.scene.explorer_paths.add()
        item.name = path

class FILEBROWSER_OT_open_explorer_path(bpy.types.Operator):
    bl_idname = "file_browser.open_explorer_path"
    bl_label = "切换文件夹"

    def execute(self, context):
        global current_path_index, explorer_paths, feature_enabled, initialized
        if not feature_enabled:
            return {'CANCELLED'}
        if not initialized:
            update_explorer_paths()
            initialized = True
        if not explorer_paths:
            self.report({'WARNING'}, "No valid Explorer window found.")
            return {'CANCELLED'}
        if not context.space_data or not hasattr(context.space_data, 'params'):
            self.report({'ERROR'}, "Context is not a file browser.")
            return {'CANCELLED'}
        if current_path_index >= len(explorer_paths):
            current_path_index = 0
        path = explorer_paths[current_path_index]
        current_path_index += 1
        if path and os.path.isdir(path):
            context.space_data.params.directory = path.encode('utf-8')
            self.report({'INFO'}, f"Opened path: {path}")
        else:
            self.report({'WARNING'}, "No valid Explorer window found.")
        return {'FINISHED'}

class FILEBROWSER_OT_toggle_feature(bpy.types.Operator):
    bl_idname = "file_browser.toggle_feature"
    bl_label = "Toggle Feature"

    def execute(self, context):
        global feature_enabled, initialized
        feature_enabled = not feature_enabled
        if not feature_enabled:
            initialized = False
        self.report({'INFO'}, f"Feature {'enabled' if feature_enabled else 'disabled'}")
        return {'FINISHED'}

class FILEBROWSER_OT_force_refresh(bpy.types.Operator):
    bl_idname = "file_browser.force_refresh"
    bl_label = "强制刷新文件夹列表"

    def execute(self, context):
        global initialized, feature_enabled
        if not feature_enabled:
            return {'CANCELLED'}
        update_explorer_paths()
        initialized = True
        self.report({'INFO'}, "Explorer paths refreshed.")
        bpy.ops.file_browser.open_explorer_path()
        return {'FINISHED'}

class FILEBROWSER_OT_select_explorer_path(bpy.types.Operator):
    bl_idname = "file_browser.select_explorer_path"
    bl_label = "Select Explorer Path"

    path_index: bpy.props.IntProperty()

    def execute(self, context):
        global explorer_paths, feature_enabled
        if not feature_enabled:
            return {'CANCELLED'}
        path = explorer_paths[self.path_index]
        if path and os.path.isdir(path):
            context.space_data.params.directory = path.encode('utf-8')
            self.report({'INFO'}, f"Opened path: {path}")
        else:
            self.report({'WARNING'}, "No valid Explorer window found.")
        return {'FINISHED'}

class FILEBROWSER_UL_explorer_paths(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        folder_name = os.path.basename(item.name)
        row = layout.row()
        row.label(text=folder_name, icon='FILE_FOLDER')
        op = row.operator("file_browser.select_explorer_path", text="", icon='FILEBROWSER')
        op.path_index = index

class ExplorerPathsCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()

class FILEBROWSER_PT_open_explorer_path(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_label = "Fast File Viewer"
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("file_browser.toggle_feature", text="", icon='HIDE_OFF' if feature_enabled else 'HIDE_ON')
        row.operator("file_browser.force_refresh", text="强制刷新文件夹列表")
        row = layout.row()
        row.operator("file_browser.open_explorer_path")
        col = layout.column()
        col.template_list("FILEBROWSER_UL_explorer_paths", "", context.scene, "explorer_paths", context.scene, "explorer_paths_index")

def depsgraph_update_handler(scene):
    global initialized
    for area in bpy.context.screen.areas:
        if area.type == 'FILE_BROWSER':
            initialized = False

addon_keymaps = []

def register():
    bpy.utils.register_class(FILEBROWSER_OT_open_explorer_path)
    bpy.utils.register_class(FILEBROWSER_OT_toggle_feature)
    bpy.utils.register_class(FILEBROWSER_OT_force_refresh)
    bpy.utils.register_class(FILEBROWSER_OT_select_explorer_path)
    bpy.utils.register_class(FILEBROWSER_UL_explorer_paths)
    bpy.utils.register_class(ExplorerPathsCollection)
    bpy.utils.register_class(FILEBROWSER_PT_open_explorer_path)
    bpy.types.Scene.explorer_paths = bpy.props.CollectionProperty(type=ExplorerPathsCollection)
    bpy.types.Scene.explorer_paths_index = bpy.props.IntProperty()
    bpy.app.handlers.depsgraph_update_pre.append(depsgraph_update_handler)
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='File Browser', space_type='FILE_BROWSER')
    kmi = km.keymap_items.new(FILEBROWSER_OT_open_explorer_path.bl_idname, 'G', 'PRESS', ctrl=True)
    addon_keymaps.append((km, kmi))

def unregister():
    bpy.utils.unregister_class(FILEBROWSER_OT_open_explorer_path)
    bpy.utils.unregister_class(FILEBROWSER_OT_toggle_feature)
    bpy.utils.unregister_class(FILEBROWSER_OT_force_refresh)
    bpy.utils.unregister_class(FILEBROWSER_OT_select_explorer_path)
    bpy.utils.unregister_class(FILEBROWSER_UL_explorer_paths)
    bpy.utils.unregister_class(ExplorerPathsCollection)
    bpy.utils.unregister_class(FILEBROWSER_PT_open_explorer_path)
    bpy.app.handlers.depsgraph_update_pre.remove(depsgraph_update_handler)
    del bpy.types.Scene.explorer_paths
    del bpy.types.Scene.explorer_paths_index
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

if __name__ == "__main__":
    register()