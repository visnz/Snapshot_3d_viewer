import bpy  # type: ignore


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


class CAMERA_OT_create_focus_object(bpy.types.Operator):
    """创建对焦对象+黑框"""
    bl_idname = "camera.create_focus_object"
    bl_label = "创建对焦对象"
    bl_description = "为当前摄像机生成一个子空物体作为景深对焦对象，并启用外围遮黑"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        camera_obj = context.scene.camera
        if not camera_obj:
            self.report({"ERROR"}, "当前场景没有设置活跃摄像机。请先设置一个摄像机为场景相机。")
            return {"CANCELLED"}
        if camera_obj.type != 'CAMERA':
            self.report({"ERROR"}, f"当前活跃物体 '{camera_obj.name}' 不是摄像机类型。")
            return {"CANCELLED"}
        focus_empty = bpy.data.objects.new("Focus_Object", None)
        focus_empty.parent = camera_obj
        focus_empty.location = (0, 0, -5)
        context.collection.objects.link(focus_empty)
        camera_data = camera_obj.data
        camera_data.dof.focus_object = focus_empty
        camera_data.show_passepartout = True
        camera_data.passepartout_alpha = 1.0
        focus_empty.select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)
        focus_empty.select_set(False)
        self.report(
            {"INFO"}, f"已为摄像机 '{camera_obj.name}' 创建对焦空物体 '{focus_empty.name}'，并开启外围遮黑。")
        return {"FINISHED"}


class SoloPick(bpy.types.Operator):
    # 断开所选物体的所有父子级关系，捡出来放在世界层级，子级归更上一层父级管。
    bl_idname = "object.solo_pick_visn"
    bl_label = "拎出"
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


class SelectParent(bpy.types.Operator):
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


class SoloPick_delete(bpy.types.Operator):
    bl_idname = "object.solo_pick_delete_visn"
    bl_label = "拎出并删除"
    bl_description = "删除选中物体（不含父子级）"
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
        bpy.ops.object.delete(use_global=False)
        return {'FINISHED'}


class RAQtoSubparent(bpy.types.Operator):
    bl_idname = "object.release_all_children_to_subparent_visn"
    bl_label = "释放到上级"
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


class P2E_individual(bpy.types.Operator):
    bl_idname = "object.parent_to_empty_visn_individual"
    bl_label = "所选物体 单独每个到父级"
    bl_description = "所有所选物体，每个对象都创建一个保护父级"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = context.selected_objects
        last_active_obj = context.view_layer.objects.active  # 获取最后一次选中的活跃对象

        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass

        # 为每个选中的物体创建一个独立的父级空物体
        for obj in objs:
            # 计算当前物体的位置
            loc = obj.location.copy()

            # 创建空物体
            bpy.ops.object.add(type='EMPTY', location=loc,
                               rotation=obj.rotation_euler)
            new_empty = context.object  # 获取新创建的空物体

            # 获取当前物体的集合
            obj_collections = obj.users_collection

            # 将新创建的空物体添加到当前物体的集合中
            try:
                for collection in obj_collections:
                    collection.objects.link(new_empty)
                # 从当前活跃集合中移除新创建的空物体
                context.collection.objects.unlink(new_empty)
            except:
                pass

            # 设置父级关系
            new_empty.parent = obj.parent  # 继承原始物体的父级

            # 设置当前物体为新空物体的子物体
            obj.select_set(True)
            context.view_layer.objects.active = new_empty
            bpy.ops.object.parent_no_inverse_set(keep_transform=True)
            obj.select_set(False)

        # 恢复原始选择状态
        for obj in objs:
            obj.select_set(True)
        if last_active_obj:
            context.view_layer.objects.active = last_active_obj

        return {'FINISHED'}


class P2E(bpy.types.Operator):
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
            bpy.ops.object.add(type='EMPTY', location=loc,
                               rotation=objs[0].rotation_euler)
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
