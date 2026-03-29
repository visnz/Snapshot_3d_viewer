from . import PSRtoComp
from . import FastFileViewer
from . import STOOL
from . import Snapshot2
from . import Snapshot1
import bpy  # type: ignore
bl_info = {
    "name": "Snapshot_3d_viewer",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "IPR快照工具、文件快速访问、一些小工具",
    "version": (1, 1, 0)
}
# 定义一个布尔属性，用于控制是否启用STOOL插件


def update_stool_enable(self, context):
    if context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()
    else:
        STOOL.unregister()

def update_snapshot1(self, context):
    if context.preferences.addons[__name__].preferences.enable_snapshot1:
        try:
            Snapshot2.unregister()
        except Exception as e:
            print(f"Error unregistering Snapshot2: {e}")
        Snapshot1.register()
    else:
        Snapshot1.unregister()
        


def update_snapshot2(self, context):
    if context.preferences.addons[__name__].preferences.enable_snapshot2:
        try:
            Snapshot1.unregister()
        except Exception as e:
            print(f"Error unregistering Snapshot1: {e}")
        Snapshot2.register()
    else:
        Snapshot2.unregister()


def update_fastFileViewer_enable(self, context):
    if context.preferences.addons[__name__].preferences.enable_fastFileViewer:
        FastFileViewer.register()
    else:
        FastFileViewer.unregister()


class MyAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enable_stool: bpy.props.BoolProperty(
        name="启用小工具箱",
        description="启用小工具箱（父子级操作、搭建类操作）",
        default=False,
        update=update_stool_enable
    )  # type: ignore
    enable_fastFileViewer: bpy.props.BoolProperty(
        name="启用快速文件夹访问（Windows特供功能）",
        description="启用快速文件夹访问",
        default=False,
        update=update_fastFileViewer_enable
    )  # type: ignore
    enable_snapshot1: bpy.props.BoolProperty(
        name="启用Snapshot（4.5.8及以前OpenGL）",
        description="启用Snapshot（4.5.8及以前OpenGL，Vulkan不支持，5.0以后不支持）",
        default=False,
        update=update_snapshot1
    )  # type: ignore
    enable_snapshot2: bpy.props.BoolProperty(
        name="启用Snapshot（5.0及以后OpenGL）",
        description="启用Snapshot（Vulkan不支持，5.0以后OpenGL支持）",
        default=False,
        update=update_snapshot2
    )  # type: ignore

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_stool")
        layout.prop(self, "enable_fastFileViewer")
        layout.prop(self, "enable_snapshot1")
        layout.prop(self, "enable_snapshot2")


def register():
    bpy.utils.register_class(MyAddonPreferences)
    PSRtoComp.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_snapshot1:
        Snapshot1.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_snapshot2:
        Snapshot2.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_fastFileViewer:
        FastFileViewer.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()


def unregister():
    if bpy.context.preferences.addons[__name__].preferences.enable_fastFileViewer:
        FastFileViewer.unregister()
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.unregister()
    if bpy.context.preferences.addons[__name__].preferences.enable_snapshot1:
        Snapshot1.unregister()
    if bpy.context.preferences.addons[__name__].preferences.enable_snapshot2:
        Snapshot2.unregister()
    PSRtoComp.unregister()
    bpy.utils.unregister_class(MyAddonPreferences)


if __name__ == "__main__":
    register()
