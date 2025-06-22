from . import PSRtoComp
from . import FastFileViewer
from . import STOOL
from . import Snapshot
import bpy  # type: ignore
bl_info = {
    "name": "Snapshot & SomeTools",
    "category": "3D View",
    "author": "GitHub Copilot & visnz",
    "blender": (4, 0, 0),
    "location": "UI",
    "description": "快照工具，附赠一些小工具箱",
    "version": (1, 1, 0)
}
# 定义一个布尔属性，用于控制是否启用STOOL插件


def update_stool_enable(self, context):
    if context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()
    else:
        STOOL.unregister()


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

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_stool")
        layout.prop(self, "enable_fastFileViewer")


def register():
    bpy.utils.register_class(MyAddonPreferences)
    PSRtoComp.register()
    Snapshot.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_fastFileViewer:
        FastFileViewer.register()
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.register()


def unregister():
    if bpy.context.preferences.addons[__name__].preferences.enable_fastFileViewer:
        FastFileViewer.unregister()
    if bpy.context.preferences.addons[__name__].preferences.enable_stool:
        STOOL.unregister()
    Snapshot.unregister()
    PSRtoComp.unregister()
    bpy.utils.unregister_class(MyAddonPreferences)


if __name__ == "__main__":
    register()
