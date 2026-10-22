extends SceneTree
func _initialize() -> void:
    run.call_deferred()
func run() -> void:
    var controller: Node = load("res://scenes/main.tscn").instantiate()
    root.add_child(controller)
    await process_frame
    controller.set_process(false)
    controller.set_physics_process(false)
    controller.state_machine.process_mode=Node.PROCESS_MODE_DISABLED
    controller.animation_player.play(&"phone")
    controller.animation_player.advance(3.2)
    var phone: Variant=controller.animation_player._gesture_rig._phone
    var folder: String=controller.config["_package_directory"]+"/../source/phone_v28/uv_diagnostics"
    DirAccess.make_dir_recursive_absolute(folder)
    for amount in [0.0,.5,1.0]:
        phone._body_material.set_shader_parameter("pose_mix",amount)
        await process_frame
        await RenderingServer.frame_post_draw
        root.get_texture().get_image().save_png(folder+"/uv_%s.png"%str(amount))
    print(folder)
    quit()
