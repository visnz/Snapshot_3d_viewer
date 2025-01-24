bl_info = {
    "name": "Snapshot & SomeTools",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "快照工具，附赠一些小工具箱",
    "version": (1, 0, 0)
}
import bpy
from . import Snapshot
from . import STOOL

# 定义一个布尔属性，用于控制是否启用STOOL插件
def update_stool_enable(self, context):
    if context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()
    else:
        STOOL.unregister()

class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enable_stool: bpy.props.BoolProperty(
        name="启用小工具箱",
        description="Enable or disable the STOOL part of the addon",
        default=False,
        update=update_stool_enable
    ) # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_stool")
        

def register():
    bpy.utils.register_class(MyAddonPreferences)
    Snapshot.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()

def unregister():
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.unregister()
    Snapshot.unregister()
    bpy.utils.unregister_class(MyAddonPreferences)

if __name__ == "__main__":
    register()