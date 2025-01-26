import bpy
import subprocess
import os
import platform  # 确保导入 platform 模块

current_path_index = 0
explorer_paths = []
feature_enabled = True
initialized = False

def get_explorer_paths():
    paths = set()
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
        paths.update(line.strip().replace('/', '\\') for line in powershell_output.splitlines() if os.path.isdir(line.strip().replace('/', '\\')))
    except subprocess.CalledProcessError:
        raise Exception("PowerShell 脚本执行失败，无法获取 explorer.exe 窗口路径。")
    return list(paths)

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
    bl_label = "切换"
    bl_description = "切换到下一个Explorer窗口路径(快捷键: Ctrl+G)"

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
    bl_label = "刷新文件夹列表"
    bl_description = "使用Powershell获取当前系统中所有的Explorer窗口路径"

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

    path_index: bpy.props.IntProperty()  # type: ignore

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

class FILEBROWSER_OT_open_current_folder(bpy.types.Operator):
    bl_idname = "file_browser.open_current_folder"
    bl_label = "打开当前文件夹"
    bl_description = "在系统文件浏览器中打开当前文件夹"

    def execute(self, context):
        if not context.space_data or not hasattr(context.space_data, 'params'):
            self.report({'ERROR'}, "Context is not a file browser.")
            return {'CANCELLED'}
        current_path = context.space_data.params.directory.decode('utf-8')
        if os.path.isdir(current_path):
            subprocess.Popen(['explorer', current_path])
            self.report({'INFO'}, f"Opened folder: {current_path}")
        else:
            self.report({'WARNING'}, "No valid folder found.")
        return {'FINISHED'}

class FILEBROWSER_UL_explorer_paths(bpy.types.UIList):
    bl_idname = "FASTFILEVIEWER_UL_explorer_paths"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        folder_name = os.path.basename(item.name)
        row = layout.row()
        op = row.operator("file_browser.select_explorer_path", text=folder_name, icon='FILE_FOLDER')
        op.path_index = index

class ExplorerPathsCollection(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()  # type: ignore

class FILEBROWSER_PT_open_explorer_path(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_label = "快速文件访问（Windows特供功能）"
    bl_category = "Tools"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("file_browser.toggle_feature", text="", icon='HIDE_OFF' if feature_enabled else 'HIDE_ON')
        row.operator("file_browser.force_refresh", text="强制刷新文件夹列表")
        row = layout.row()
        row.operator("file_browser.open_explorer_path")
        row = layout.row()
        row.operator("file_browser.open_current_folder", text="打开当前文件夹")
        col = layout.column()
        col.template_list("FASTFILEVIEWER_UL_explorer_paths", "", context.scene, "explorer_paths", context.scene, "explorer_paths_index")

def depsgraph_update_handler(scene):
    global initialized
    for area in bpy.context.screen.areas:
        if area.type == 'FILE_BROWSER':
            initialized = False

addon_keymaps = []

all_classes = [
    FILEBROWSER_OT_open_explorer_path,
    FILEBROWSER_OT_toggle_feature,
    FILEBROWSER_OT_force_refresh,
    FILEBROWSER_OT_select_explorer_path,
    FILEBROWSER_OT_open_current_folder,
    FILEBROWSER_UL_explorer_paths,
    ExplorerPathsCollection,
    FILEBROWSER_PT_open_explorer_path
]

def register():
    for cls in all_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.explorer_paths = bpy.props.CollectionProperty(type=ExplorerPathsCollection)
    bpy.types.Scene.explorer_paths_index = bpy.props.IntProperty()
    bpy.app.handlers.depsgraph_update_pre.append(depsgraph_update_handler)
    wm = bpy.context.window_manager
    km = wm.keyconfigs.addon.keymaps.new(name='File Browser', space_type='FILE_BROWSER')
    kmi = km.keymap_items.new(FILEBROWSER_OT_open_explorer_path.bl_idname, 'G', 'PRESS', ctrl=True)
    addon_keymaps.append((km, kmi))

def unregister():
    for cls in reversed(all_classes):
        bpy.utils.unregister_class(cls)
    bpy.app.handlers.depsgraph_update_pre.remove(depsgraph_update_handler)
    del bpy.types.Scene.explorer_paths
    del bpy.types.Scene.explorer_paths_index
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()

if __name__ == "__main__":
    register()