extends SceneTree
## Captures one complete-body still at a readable moment for every live action.

const SAMPLES := {
	"idle": 0.35, "waiting": 0.35, "blink": 0.10, "sleep": 0.48,
	"run_left": 0.40, "run_right": 0.40,
	"wave": 1.25, "happy": 0.70, "bow": 1.20, "hair_touch": 1.70,
	"mirror": 2.00, "think": 1.80, "yawn": 1.80, "stretch": 2.50,
	"shy": 1.80, "look": 1.25, "heart": 1.80, "phone": 8.00,
}

func _initialize() -> void:
	_capture.call_deferred()

func _arg(name: String, fallback: String = "") -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == name:
			return args[i + 1]
	return fallback

func _capture() -> void:
	var controller: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(controller)
	await process_frame
	controller.set_process(false)
	controller.set_physics_process(false)
	controller.state_machine.process_mode = Node.PROCESS_MODE_DISABLED
	var output_dir := _arg("--stills-output", "user://pet-action-stills")
	DirAccess.make_dir_recursive_absolute(output_dir)
	for action in SAMPLES:
		if action == "blink":
			controller.animation_player.play(&"idle")
			controller.animation_player._play_rest_blink()
		else:
			controller.animation_player.play(StringName(action))
		var frames := ceili(float(SAMPLES[action]) * 60.0)
		for frame in range(frames):
			if frame > 0:
				controller.animation_player.advance(1.0 / 60.0)
			await process_frame
			await RenderingServer.frame_post_draw
		var image: Image = root.get_texture().get_image()
		image.save_png(output_dir.path_join(String(action) + ".png"))
		print("Captured %s at %.2fs" % [action, SAMPLES[action]])
	print("Complete action stills: " + output_dir)
	quit()
