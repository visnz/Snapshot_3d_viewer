
import bpy

class PSR_TO_COMPOSITE_OT_operator(bpy.types.Operator):
    bl_idname = "node.psr_to_composite"
    bl_label = "Location + Scale to Composite"

    def execute(self, context):
        obj = context.object
        if not obj:
            self.report({'ERROR'}, "No object selected")
            return {'CANCELLED'}

        node_tree = context.scene.node_tree
        if not node_tree:
            self.report({'ERROR'}, "No compositor node tree found")
            return {'CANCELLED'}

        # 创建两个Combine XYZ节点
        loc_node = node_tree.nodes.new(type='CompositorNodeCombineXYZ')
        scale_node = node_tree.nodes.new(type='CompositorNodeCombineXYZ')

        # 设置节点位置
        loc_node.location = (0, 300)
        scale_node.location = (0, 0)

        # 为每个节点的输入添加驱动器
        def add_driver(target, data_path, index):
            # 为每个输入通道（X, Y, Z）分别添加驱动器
            for i in range(3):
                driver = target.inputs[i].driver_add('default_value').driver
                driver.type = 'SCRIPTED'
                var = driver.variables.new()
                var.name = "value"
                var.targets[0].id = obj
                var.targets[0].data_path = f"{data_path}[{i}]"
                driver.expression = var.name

        # 位置
        add_driver(loc_node, 'location', 0)

        # 缩放
        add_driver(scale_node, 'scale', 1)

        self.report({'INFO'}, "Location and Scale data bound to compositor nodes via drivers")
        return {'FINISHED'}

# 在合成器面板中添加按钮
class NODE_PT_psr_to_composite_panel(bpy.types.Panel):
    bl_label = "Location + Scale to Composite"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        layout.operator("node.psr_to_composite", text="Bind Object L+S")

# 注册插件
def register():
    bpy.utils.register_class(PSR_TO_COMPOSITE_OT_operator)
    bpy.utils.register_class(NODE_PT_psr_to_composite_panel)

def unregister():
    bpy.utils.unregister_class(PSR_TO_COMPOSITE_OT_operator)
    bpy.utils.unregister_class(NODE_PT_psr_to_composite_panel)

if __name__ == "__main__":
    register()