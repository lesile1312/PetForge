extends SceneTree

const PLAYER_SCRIPT := preload("res://scripts/animation/photo_pet_action_p0.gd")


func _initialize() -> void:
	call_deferred("_start_preview")


func _start_preview() -> void:
	var args := OS.get_cmdline_user_args()
	var manifest_path := ""
	var first_action := "idle"
	var index := 0
	while index < args.size():
		if args[index] == "--manifest" and index + 1 < args.size():
			manifest_path = args[index + 1]
			index += 2
		elif args[index] == "--action" and index + 1 < args.size():
			first_action = args[index + 1]
			index += 2
		else:
			index += 1
	if manifest_path.is_empty() or not FileAccess.file_exists(manifest_path):
		push_error("Pass --manifest <local p0-actions/manifest.json>")
		quit(2)
		return
	var player := Node2D.new()
	player.set_script(PLAYER_SCRIPT)
	player.call("configure", manifest_path)
	get_root().add_child(player)
	var action_index := maxi(0, ["idle", "run_left", "run_right", "wave_smile", "phone_crouch"].find(first_action))
	player.call_deferred("_play_index", action_index)
	print("PetForge local P0 preview: ", manifest_path)
