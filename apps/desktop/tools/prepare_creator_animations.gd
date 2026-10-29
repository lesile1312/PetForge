extends SceneTree
## Normalizes the preserved 60 FPS creator sequences into a portable pet package.

const ACTIONS := ["hair_touch", "heart", "mirror", "shy", "stretch", "think", "wave", "yawn", "run_left", "run_right"]
const RUN_ACTIONS := ["run_left", "run_right"]
const ACTION_FPS := 60.0
const RUN_FPS := 12.0

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var arguments := OS.get_cmdline_user_args()
	if arguments.size() < 3:
		push_error("Usage: -- gesture-sequence-folder pet-package-folder run-sequence-folder")
		quit(2)
		return
	var source_root := arguments[0]
	var package_root := arguments[1]
	var run_source_root := arguments[2]
	var base_path := package_root.path_join("character.png")
	var base_image := Image.new()
	if base_image.load(base_path) != OK:
		push_error("Cannot load the pet's character.png: %s" % base_path)
		quit(3)
		return
	var base_bounds := base_image.get_used_rect()
	if base_bounds.size.y <= 0:
		push_error("The pet sprite has no visible alpha pixels.")
		quit(3)
		return

	var sequences: Dictionary = {}
	var canvas_width := base_image.get_width()
	for action in ACTIONS:
		var action_source := run_source_root.path_join(action) if RUN_ACTIONS.has(action) else source_root.path_join(action)
		var filenames := DirAccess.get_files_at(action_source)
		filenames.sort()
		var png_names: Array[String] = []
		var run_frame_pattern := RegEx.new()
		if RUN_ACTIONS.has(action):
			run_frame_pattern.compile("^%s_00[0-7]\\.png$" % action)
		var union_bounds := Rect2i()
		var has_bounds := false
		for filename in filenames:
			if not filename.to_lower().ends_with(".png"):
				continue
			if RUN_ACTIONS.has(action) and run_frame_pattern.search(filename) == null:
				continue
			var source_image := Image.new()
			var source_path := action_source.path_join(filename)
			if source_image.load(source_path) != OK:
				push_error("Cannot read animation frame: %s" % source_path)
				quit(4)
				return
			var used_bounds := source_image.get_used_rect()
			if used_bounds.size.x <= 0 or used_bounds.size.y <= 0:
				continue
			union_bounds = used_bounds if not has_bounds else union_bounds.merge(used_bounds)
			has_bounds = true
			png_names.append(filename)
		if png_names.is_empty() or not has_bounds:
			push_error("No visible PNG frames found for action: %s" % action)
			quit(4)
			return
		var target_height := base_bounds.size.y
		var target_width := ceili(float(union_bounds.size.x) * float(target_height) / float(union_bounds.size.y))
		canvas_width = maxi(canvas_width, target_width)
		sequences[action] = {
			"source_directory": action_source,
			"files": png_names,
			"bounds": union_bounds,
			"width": target_width,
			"height": target_height,
		}

	canvas_width = maxi(canvas_width, base_image.get_width()) + 2
	var animations_root := package_root.path_join("animations")
	if DirAccess.make_dir_recursive_absolute(animations_root) != OK:
		push_error("Cannot create the package animations folder.")
		quit(5)
		return
	var padded_sprite := Image.create(canvas_width, base_image.get_height(), false, Image.FORMAT_RGBA8)
	padded_sprite.fill(Color(0.0, 0.0, 0.0, 0.0))
	padded_sprite.blit_rect(
		base_image,
		Rect2i(Vector2i.ZERO, base_image.get_size()),
		Vector2i((canvas_width - base_image.get_width()) / 2, 0)
	)
	var runtime_sprite_path := animations_root.path_join("runtime_sprite.png")
	if padded_sprite.save_png(runtime_sprite_path) != OK:
		push_error("Cannot save the runtime sprite canvas.")
		quit(5)
		return

	var animation_manifest: Dictionary = {}
	for action in ACTIONS:
		var sequence: Dictionary = sequences[action]
		var action_directory := animations_root.path_join(action)
		if DirAccess.make_dir_recursive_absolute(action_directory) != OK:
			push_error("Cannot create animation folder: %s" % action_directory)
			quit(5)
			return
		var frame_paths: Array[String] = []
		for frame_index in range(sequence["files"].size()):
			var filename: String = sequence["files"][frame_index]
			var source_image := Image.new()
			var source_path: String = sequence["source_directory"].path_join(filename)
			if source_image.load(source_path) != OK:
				push_error("Cannot reload animation frame: %s" % source_path)
				quit(4)
				return
			var frame := source_image.get_region(sequence["bounds"])
			frame.resize(sequence["width"], sequence["height"], Image.INTERPOLATE_LANCZOS)
			var output := Image.create(canvas_width, base_image.get_height(), false, Image.FORMAT_RGBA8)
			output.fill(Color(0.0, 0.0, 0.0, 0.0))
			var destination := Vector2i(
				(canvas_width - sequence["width"]) / 2,
				(base_image.get_height() - sequence["height"]) / 2
			)
			output.blit_rect(frame, Rect2i(Vector2i.ZERO, frame.get_size()), destination)
			var numbered_name := "%s_%03d.png" % [action, frame_index]
			var output_path := action_directory.path_join(numbered_name)
			if output.save_png(output_path) != OK:
				push_error("Cannot save normalized animation frame: %s" % output_path)
				quit(5)
				return
			frame_paths.append("animations/%s/%s" % [action, numbered_name])
		animation_manifest[action] = {
			"frames": frame_paths,
			"fps": RUN_FPS if RUN_ACTIONS.has(action) else ACTION_FPS,
			"loop": RUN_ACTIONS.has(action),
		}

	var config_path := package_root.path_join("pet.json")
	var config_file := FileAccess.open(config_path, FileAccess.READ)
	if config_file == null:
		push_error("Cannot read pet.json: %s" % config_path)
		quit(6)
		return
	var pet_config: Variant = JSON.parse_string(config_file.get_as_text())
	config_file.close()
	if not pet_config is Dictionary or not pet_config.get("appearance", {}) is Dictionary:
		push_error("The pet package config is invalid.")
		quit(6)
		return
	pet_config["appearance"]["sprite"] = "animations/runtime_sprite.png"
	pet_config["animations"] = animation_manifest
	var config_backup_path := package_root.path_join("pet.before-actions.json")
	if not FileAccess.file_exists(config_backup_path):
		if DirAccess.copy_absolute(config_path, config_backup_path) != OK:
			push_error("Cannot preserve the original pet.json before adding actions.")
			quit(6)
			return
	var config_output := FileAccess.open(config_path, FileAccess.WRITE)
	if config_output == null:
		push_error("Cannot write package animation config.")
		quit(6)
		return
	config_output.store_string(JSON.stringify(pet_config, "  "))
	config_output.close()
	print("Prepared %d actions at %.0f FPS; canvas %dx%d." % [animation_manifest.size(), ACTION_FPS, canvas_width, base_image.get_height()])
	quit(0)
