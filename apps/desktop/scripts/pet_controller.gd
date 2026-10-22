extends Node2D
## Loads one pet package and owns the runtime services shared by its states.

const PetStateMachine = preload("res://scripts/state_machine.gd")
const BehaviorScheduler = preload("res://scripts/behavior_scheduler.gd")
const AmbientRepertoire = preload("res://scripts/ambient_repertoire.gd")
const ScreenBounds = preload("res://scripts/screen_bounds.gd")
const StaticSpriteAnimation = preload("res://scripts/animation/static_sprite_animation.gd")
const IDLE_STATE = preload("res://scripts/states/idle_state.gd")
const WALK_STATE = preload("res://scripts/states/walk_state.gd")
const SLEEP_STATE = preload("res://scripts/states/sleep_state.gd")
const JUMP_STATE = preload("res://scripts/states/jump_state.gd")
const DRAG_STATE = preload("res://scripts/states/drag_state.gd")
const FALL_STATE = preload("res://scripts/states/fall_state.gd")
const CLICK_STATE = preload("res://scripts/states/click_reaction_state.gd")
const WAITING_STATE = preload("res://scripts/states/waiting_state.gd")

const DEFAULT_PACKAGE_DIR := "res://assets/default-pet"
const MAX_TEXTURE_SIDE := 900
const MAX_CHARACTER_HEIGHT := 330.0
const WINDOW_SIDE_PADDING := 26.0
const WINDOW_TOP_PADDING := 26.0
const WINDOW_BOTTOM_PADDING := 28.0
const CLICK_DISTANCE_PX := 7.0
const ALPHA_HIT_THRESHOLD := 0.12
const HOVER_GREETING_DWELL_MS := 250
const HOVER_GREETING_COOLDOWN_MS := 10000

@onready var character: Sprite2D = $Character
@onready var sleep_label: Label = $SleepLabel

var runtime_window: Window
var config: Dictionary = {}
var appearance: Dictionary = {}
var behavior: Dictionary = {}
var window_options: Dictionary = {}
var sprite_base_scale := Vector2.ONE
var screen_bounds: Variant
var behavior_scheduler: Variant
var ambient_repertoire := AmbientRepertoire.new()
var animation_player: Variant
var state_machine: Variant
var model_pivot: Node3D
var model_float_origin := 0.0
var inactive_seconds := 0.0
var drag_distance := 0.0
var requested_action: StringName = &""
var right_click_action_index := 0
const RIGHT_CLICK_ACTIONS: Array[StringName] = [
	&"heart", &"think", &"stretch", &"yawn", &"shy", &"look",
	&"phone", &"wave", &"happy", &"bow", &"hair_touch", &"mirror", &"sleep",
]
var sprite_animation_frames: Dictionary = {}
var _facing_direction := 1
var _drag_start_mouse := Vector2i.ZERO
var _drag_window_offset := Vector2i.ZERO
var _input_mask_image: Image
var _mouse_passthrough_mask_image: Image
var _mouse_passthrough_base_hull := PackedVector2Array()
var _is_hovering_pet := false
var _hover_greeting_pending := false
var _hover_entered_at_msec := 0
var _next_hover_greeting_at_msec := 0
var _resting_state_id: StringName = &"IDLE"

func _ready() -> void:
	Engine.max_fps = 60
	Engine.physics_ticks_per_second = 60
	runtime_window = get_window()
	screen_bounds = ScreenBounds.new()
	behavior_scheduler = BehaviorScheduler.new()
	config = _load_pet_config()
	appearance = _dictionary_section("appearance")
	behavior = _dictionary_section("behavior")
	window_options = _dictionary_section("window")
	_configure_window()
	_load_character()
	_configure_window_size_and_scale()
	if String(appearance.get("desktopMode", "cartoon")) == "3d":
		_load_3d_model()
	_configure_sleep_label()
	_place_window()
	_refresh_mouse_passthrough()
	_configure_state_machine()
	reset_inactivity()
	state_machine.change_state(&"IDLE")
	var launch_args := OS.get_cmdline_user_args()
	var action_index := launch_args.find("--start-action")
	if action_index >= 0 and action_index + 1 < launch_args.size():
		var startup_action := StringName(launch_args[action_index + 1])
		if startup_action in RIGHT_CLICK_ACTIONS:
			requested_action = startup_action
			state_machine.change_state(&"CLICK_REACTION")

func _process(delta: float) -> void:
	if state_machine == null:
		return
	if animation_player != null:
		animation_player.advance(delta)
	_update_hover_state()
	if is_instance_valid(model_pivot):
		model_pivot.position.y = model_float_origin + sin(Time.get_ticks_msec() / 850.0) * 0.018
	if not state_machine.is_in_state(&"DRAG") and not state_machine.is_in_state(&"CLICK_REACTION"):
		inactive_seconds += delta

func _physics_process(delta: float) -> void:
	if state_machine != null:
		state_machine.tick(delta)

func _input(event: InputEvent) -> void:
	if state_machine == null:
		return
	if state_machine.is_in_state(&"DRAG"):
		state_machine.handle_input(event)
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
		if not _event_hits_visible_pixels(event.position):
			return
		reset_inactivity()
		if state_machine.is_in_state(&"CLICK_REACTION"):
			state_machine.change_state(&"IDLE")
		requested_action = RIGHT_CLICK_ACTIONS[right_click_action_index]
		right_click_action_index = (right_click_action_index + 1) % RIGHT_CLICK_ACTIONS.size()
		state_machine.change_state(&"CLICK_REACTION")
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		if not _event_hits_visible_pixels(event.position):
			return
		reset_inactivity()
		if bool(behavior.get("draggable", true)):
			state_machine.change_state(&"DRAG")
		else:
			state_machine.change_state(&"CLICK_REACTION")

func _configure_window() -> void:
	runtime_window.transparent = true
	runtime_window.transparent_bg = true
	runtime_window.borderless = true
	runtime_window.unresizable = true
	runtime_window.always_on_top = bool(window_options.get("alwaysOnTop", true))
	runtime_window.title = String(config.get("name", "PetForge Pet"))
	get_viewport().transparent_bg = true
	RenderingServer.set_default_clear_color(Color(0, 0, 0, 0))

func _load_pet_config() -> Dictionary:
	var package_directory := _package_directory_from_args()
	var config_path := package_directory.path_join("pet.json")
	if not FileAccess.file_exists(config_path):
		push_warning("PetForge package config was not found; using the included example pet.")
		package_directory = ProjectSettings.globalize_path(DEFAULT_PACKAGE_DIR)
		config_path = package_directory.path_join("pet.json")
	var file := FileAccess.open(config_path, FileAccess.READ)
	if file == null:
		push_error("Unable to open PetForge pet.json; default settings will be used.")
		return _fallback_config()
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary or String(parsed.get("version", "")) != "1.0":
		push_error("Unsupported or invalid pet package version. Expected version 1.0.")
		return _fallback_config()
	config = parsed
	config["_package_directory"] = package_directory
	if not config.has("appearance") or not config["appearance"] is Dictionary:
		config["appearance"] = {"sprite": "character.png", "scale": 1.0}
	if not config.has("behavior") or not config["behavior"] is Dictionary:
		config["behavior"] = _fallback_config()["behavior"]
	if not config.has("window") or not config["window"] is Dictionary:
		config["window"] = {"alwaysOnTop": true, "mousePassthrough": true}
	return config

func _package_directory_from_args() -> String:
	var arguments := OS.get_cmdline_user_args()
	for index in range(arguments.size() - 1):
		if arguments[index] == "--pet-project":
			var requested_path := arguments[index + 1].strip_edges().strip_edges().trim_prefix("\"").trim_suffix("\"")
			if DirAccess.dir_exists_absolute(requested_path):
				return requested_path
			push_error("The selected pet package folder does not exist: %s" % requested_path)
	return ProjectSettings.globalize_path(DEFAULT_PACKAGE_DIR)

func _fallback_config() -> Dictionary:
	return {
		"version": "1.0",
		"id": "pet_00000000000000000000000000000000",
		"name": "Momo",
		"appearance": {"sprite": "character.png", "scale": 1.0},
		"behavior": {
			"moveSpeed": 100,
			"idleDuration": 20,
			"sleepDuration": 120,
			"randomWalk": true,
			"randomJump": true,
			"autoSleep": true,
			"draggable": true,
			"initialPosition": "right",
			"randomWalkFrequency": "medium"
		},
		"window": {"alwaysOnTop": true, "mousePassthrough": true}
	}

func _dictionary_section(section_name: String) -> Dictionary:
	var section: Variant = config.get(section_name, {})
	return section if section is Dictionary else {}

func _load_character() -> void:
	var relative_path := String(appearance.get("sprite", "character.png"))
	if relative_path.begins_with("/") or relative_path.contains("..") or not relative_path.to_lower().ends_with(".png"):
		push_error("The pet package sprite path is invalid. Loading the included example image.")
		relative_path = "character.png"
	var package_directory := String(config.get("_package_directory", ProjectSettings.globalize_path(DEFAULT_PACKAGE_DIR)))
	var image_path := package_directory.path_join(relative_path)
	if not FileAccess.file_exists(image_path):
		push_error("The pet package image is missing: %s" % image_path)
		package_directory = ProjectSettings.globalize_path(DEFAULT_PACKAGE_DIR)
		image_path = package_directory.path_join("character.png")
	var image_bytes := FileAccess.get_file_as_bytes(image_path)
	_input_mask_image = Image.new()
	var load_error := _input_mask_image.load_png_from_buffer(image_bytes)
	if load_error != OK:
		push_error("Unable to decode character.png (error %s)." % load_error)
		_input_mask_image = Image.create(1, 1, false, Image.FORMAT_RGBA8)
		_input_mask_image.fill(Color(1, 1, 1, 1))
	if maxf(_input_mask_image.get_width(), _input_mask_image.get_height()) > MAX_TEXTURE_SIDE:
		var ratio := MAX_TEXTURE_SIDE / maxf(_input_mask_image.get_width(), _input_mask_image.get_height())
		_input_mask_image.resize(roundi(_input_mask_image.get_width() * ratio), roundi(_input_mask_image.get_height() * ratio), Image.INTERPOLATE_LANCZOS)
	character.texture = ImageTexture.create_from_image(_input_mask_image)
	character.centered = true
	character.flip_h = false
	character.visible = true
	_load_animation_frames(package_directory)

func _load_animation_frames(package_directory: String) -> void:
	var frame_map: Variant = appearance.get("animationFrames", {})
	if not frame_map is Dictionary:
		return
	for raw_action in frame_map.keys():
		var entries: Variant = frame_map[raw_action]
		if not entries is Array:
			continue
		var action := StringName(String(raw_action))
		var loaded_frames: Array[Dictionary] = []
		for raw_path in entries:
			if not raw_path is String:
				continue
			var relative_path := String(raw_path)
			if relative_path.begins_with("/") or relative_path.contains("..") or not relative_path.to_lower().ends_with(".png"):
				push_warning("Ignoring an invalid animation frame path: %s" % relative_path)
				continue
			var frame_path := package_directory.path_join(relative_path)
			var frame_image := Image.new()
			var load_error := frame_image.load(frame_path)
			if load_error != OK:
				push_warning("Unable to load animation frame %s (error %s)." % [frame_path, load_error])
				continue
			if not loaded_frames.is_empty():
				var first_image: Image = loaded_frames[0]["image"]
				if frame_image.get_size() != first_image.get_size():
					frame_image.resize(first_image.get_width(), first_image.get_height(), Image.INTERPOLATE_LANCZOS)
			loaded_frames.append({
				"image": frame_image,
				"texture": null,
			})
		if not loaded_frames.is_empty():
			var atlas_texture := _create_action_atlas(loaded_frames)
			var frame_width := int(loaded_frames[0]["image"].get_width())
			var frame_height := int(loaded_frames[0]["image"].get_height())
			var columns := mini(8, loaded_frames.size())
			for frame_index in range(loaded_frames.size()):
				var atlas_frame := AtlasTexture.new()
				atlas_frame.atlas = atlas_texture
				atlas_frame.region = Rect2(
					Vector2((frame_index % columns) * frame_width, floori(float(frame_index) / float(columns)) * frame_height),
					Vector2(frame_width, frame_height)
				)
				atlas_frame.filter_clip = true
				loaded_frames[frame_index]["texture"] = atlas_frame
			sprite_animation_frames[action] = loaded_frames
	if sprite_animation_frames.has(&"idle"):
		_apply_animation_frame(&"idle", 0)
	_rebuild_mouse_passthrough_mask()

func _create_action_atlas(frames: Array[Dictionary]) -> Texture2D:
	var frame_width := int(frames[0]["image"].get_width())
	var frame_height := int(frames[0]["image"].get_height())
	var columns := mini(8, frames.size())
	var rows := ceili(float(frames.size()) / float(columns))
	var atlas_image := Image.create(columns * frame_width, rows * frame_height, false, Image.FORMAT_RGBA8)
	atlas_image.fill(Color(0.0, 0.0, 0.0, 0.0))
	for frame_index in range(frames.size()):
		var frame_image: Image = frames[frame_index]["image"]
		var destination := Vector2i((frame_index % columns) * frame_width, floori(float(frame_index) / float(columns)) * frame_height)
		atlas_image.blit_rect(frame_image, Rect2i(Vector2i.ZERO, frame_image.get_size()), destination)
	return ImageTexture.create_from_image(atlas_image)

func _rebuild_mouse_passthrough_mask() -> void:
	_mouse_passthrough_mask_image = Image.create(
		_input_mask_image.get_width(),
		_input_mask_image.get_height(),
		false,
		Image.FORMAT_RGBA8
	)
	_mouse_passthrough_mask_image.fill(Color(1.0, 1.0, 1.0, 0.0))
	for action in sprite_animation_frames:
		var frames: Array = sprite_animation_frames[action]
		for frame_data in frames:
			var frame_image: Image = frame_data["image"]
			_mouse_passthrough_mask_image.blend_rect(
				frame_image,
				Rect2i(Vector2i.ZERO, frame_image.get_size()),
				Vector2i.ZERO
			)

func animation_frame_count(action: StringName) -> int:
	var frames: Variant = sprite_animation_frames.get(action, [])
	return frames.size() if frames is Array else 0

func animation_frame_image(action: StringName, frame_index: int) -> Image:
	var frames: Variant = sprite_animation_frames.get(action, [])
	if not frames is Array or frames.is_empty():
		return null
	var selected: Dictionary = frames[posmod(frame_index, frames.size())]
	var frame_image: Variant = selected.get("image")
	return frame_image if frame_image is Image else null

func animation_fps(action: StringName) -> float:
	var per_action: Variant = appearance.get("animationFpsByAction", {})
	if per_action is Dictionary and per_action.has(String(action)):
		return maxf(1.0, float(per_action[String(action)]))
	return maxf(1.0, float(appearance.get("animationFps", 60.0)))

func set_animation_frame(action: StringName, frame_index: int) -> void:
	_apply_animation_frame(action, frame_index)

func _apply_animation_frame(action: StringName, frame_index: int) -> void:
	var frames: Variant = sprite_animation_frames.get(action, [])
	if not frames is Array or frames.is_empty():
		return
	var selected: Dictionary = frames[posmod(frame_index, frames.size())]
	character.texture = selected["texture"]
	_input_mask_image = selected["image"]

func _load_3d_model() -> void:
	if String(appearance.get("model", "")) != "model.glb":
		return
	var package_directory := String(config.get("_package_directory", ProjectSettings.globalize_path(DEFAULT_PACKAGE_DIR)))
	var model_path := package_directory.path_join("model.glb")
	if not FileAccess.file_exists(model_path):
		push_warning("The package refers to model.glb, but the 3D model file is missing. Using the transparent PNG instead.")
		return

	var document := GLTFDocument.new()
	var gltf_state := GLTFState.new()
	var load_error := document.append_from_file(model_path, gltf_state)
	if load_error != OK:
		push_error("Unable to load model.glb (error %s). Using the transparent PNG instead." % load_error)
		return
	var imported_scene := document.generate_scene(gltf_state)
	if imported_scene == null:
		push_error("Godot could not create a scene from model.glb. Using the transparent PNG instead.")
		return
	_apply_vertex_colors(imported_scene)

	var container := SubViewportContainer.new()
	container.name = "ModelViewportContainer"
	container.position = Vector2.ZERO
	container.size = Vector2(runtime_window.size)
	container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	container.stretch = true
	container.z_index = 1
	add_child(container)

	var sub_viewport := SubViewport.new()
	sub_viewport.name = "ModelViewport"
	sub_viewport.size = runtime_window.size
	sub_viewport.transparent_bg = true
	sub_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	container.add_child(sub_viewport)

	var world_root := Node3D.new()
	sub_viewport.add_child(world_root)
	var world_environment := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_CLEAR_COLOR
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.76, 0.79, 0.83)
	environment.ambient_light_energy = 0.72
	world_environment.environment = environment
	world_root.add_child(world_environment)

	var key_light := DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-27.0, -32.0, 0.0)
	key_light.light_energy = 1.25
	world_root.add_child(key_light)
	var fill_light := DirectionalLight3D.new()
	fill_light.rotation_degrees = Vector3(-12.0, 146.0, 0.0)
	fill_light.light_energy = 0.42
	world_root.add_child(fill_light)

	model_pivot = Node3D.new()
	model_pivot.name = "PetModelPivot"
	world_root.add_child(model_pivot)
	model_pivot.add_child(imported_scene)
	_fit_model_to_camera(imported_scene, sub_viewport)
	model_float_origin = model_pivot.position.y
	character.visible = false

func _apply_vertex_colors(model_scene: Node) -> void:
	for candidate in model_scene.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := candidate as MeshInstance3D
		if mesh_instance == null or mesh_instance.mesh == null:
			continue
		for surface_index in range(mesh_instance.mesh.get_surface_count()):
			var existing_material: Material = mesh_instance.get_surface_override_material(surface_index)
			if existing_material == null:
				existing_material = mesh_instance.mesh.surface_get_material(surface_index)
			var color_material: StandardMaterial3D
			if existing_material is StandardMaterial3D:
				color_material = existing_material.duplicate() as StandardMaterial3D
			else:
				color_material = StandardMaterial3D.new()
			color_material.albedo_color = Color.WHITE
			color_material.roughness = 0.92
			color_material.metallic = 0.0
			color_material.cull_mode = BaseMaterial3D.CULL_DISABLED
			color_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
			color_material.vertex_color_use_as_albedo = true
			mesh_instance.set_surface_override_material(surface_index, color_material)

func _fit_model_to_camera(model_scene: Node, sub_viewport: SubViewport) -> void:
	var camera := Camera3D.new()
	camera.name = "PetCamera"
	camera.fov = 35.0
	camera.current = true
	sub_viewport.add_child(camera)
	camera.position = Vector3(0.0, 0.82, -3.05)
	camera.look_at_from_position(camera.position, Vector3.ZERO, Vector3.UP)

	var has_bounds := false
	var bounds := AABB()
	var scene_root := model_scene as Node3D
	if scene_root == null:
		push_warning("The generated GLB root is not Node3D; using the default camera framing.")
		return
	var inverse_root := scene_root.global_transform.affine_inverse()
	for candidate in scene_root.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance := candidate as MeshInstance3D
		if mesh_instance == null or mesh_instance.mesh == null:
			continue
		var mesh_bounds := mesh_instance.get_aabb()
		var relative_transform: Transform3D = inverse_root * mesh_instance.global_transform
		for corner_index in range(8):
			var corner := relative_transform * mesh_bounds.get_endpoint(corner_index)
			if not has_bounds:
				bounds = AABB(corner, Vector3.ZERO)
				has_bounds = true
			else:
				bounds = bounds.expand(corner)
	if not has_bounds:
		push_warning("The generated GLB contains no mesh geometry.")
		return

	var center := bounds.position + bounds.size * 0.5
	var largest_dimension := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))
	if largest_dimension <= 0.0001:
		push_warning("The generated GLB mesh has empty bounds.")
		return
	scene_root.position -= center
	var fit_scale := 1.65 / largest_dimension
	model_pivot.scale = Vector3.ONE * fit_scale
	var scaled_height := bounds.size.y * fit_scale
	model_pivot.position.y = -0.82 + scaled_height * 0.5
	var camera_distance := maxf(2.5, scaled_height * 1.8)
	var target_y := model_pivot.position.y
	camera.position = Vector3(0.0, target_y + camera_distance * 0.259, -camera_distance * 0.966)
	camera.look_at_from_position(camera.position, Vector3(0.0, target_y, 0.0), Vector3.UP)

func _configure_window_size_and_scale() -> void:
	var image_size := Vector2(_input_mask_image.get_width(), _input_mask_image.get_height())
	var screen: Rect2i = screen_bounds.active_screen_rect()
	var max_dimension := maxf(image_size.x, image_size.y)
	var screen_fit := minf(1.0, minf(MAX_CHARACTER_HEIGHT / max_dimension, minf((screen.size.x - 48.0) / image_size.x, (screen.size.y - 96.0) / image_size.y)))
	var requested_scale := clampf(float(appearance.get("scale", 1.0)), 0.5, 2.0)
	var effective_scale := maxf(0.05, screen_fit * requested_scale)
	sprite_base_scale = Vector2.ONE * effective_scale
	character.scale = sprite_base_scale
	var character_size := image_size * effective_scale
	var window_size := Vector2i(
		maxi(64, ceili(character_size.x + WINDOW_SIDE_PADDING * 2.0)),
		maxi(64, ceili(character_size.y + WINDOW_TOP_PADDING + WINDOW_BOTTOM_PADDING))
	)
	runtime_window.min_size = Vector2i(64, 64)
	runtime_window.max_size = window_size
	runtime_window.content_scale_size = window_size
	runtime_window.size = window_size
	# Reserve a little extra room below the shoes; transparent windows can be
	# rounded down by Windows DPI scaling, which otherwise clips the last pixels.
	character.position = Vector2(window_size.x * 0.5, WINDOW_TOP_PADDING + character_size.y * 0.5 - 24.0)

func _configure_sleep_label() -> void:
	sleep_label.text = "Z  z  z"
	sleep_label.position = Vector2(runtime_window.size.x * 0.55, 13.0)
	sleep_label.size = Vector2(95.0, 30.0)
	sleep_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sleep_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	sleep_label.visible = false
	sleep_label.z_index = 2

func _place_window() -> void:
	var placement := String(behavior.get("initialPosition", "right"))
	runtime_window.position = screen_bounds.initial_position(runtime_window.size, placement)

func _configure_state_machine() -> void:
	animation_player = StaticSpriteAnimation.new()
	animation_player.configure(character, self, sleep_label, sprite_base_scale)
	state_machine = PetStateMachine.new()
	state_machine.configure(self)
	add_child(state_machine)
	state_machine.register_state(&"IDLE", IDLE_STATE)
	state_machine.register_state(&"WALK", WALK_STATE)
	state_machine.register_state(&"SLEEP", SLEEP_STATE)
	state_machine.register_state(&"JUMP", JUMP_STATE)
	state_machine.register_state(&"DRAG", DRAG_STATE)
	state_machine.register_state(&"FALL", FALL_STATE)
	state_machine.register_state(&"CLICK_REACTION", CLICK_STATE)
	state_machine.register_state(&"WAITING", WAITING_STATE)

func _update_hover_state() -> void:
	if runtime_window == null or _mouse_passthrough_mask_image == null:
		return
	var pointer_in_window := Vector2(DisplayServer.mouse_get_position() - runtime_window.position)
	var over_pet := _event_hits_visible_pixels(pointer_in_window, true)
	var now_msec := Time.get_ticks_msec()
	var can_greet: bool = state_machine.is_in_state(&"IDLE") or state_machine.is_in_state(&"WAITING")
	if over_pet != _is_hovering_pet:
		_is_hovering_pet = over_pet
		_hover_greeting_pending = over_pet and can_greet
		_hover_entered_at_msec = now_msec
	if not over_pet or not can_greet:
		_hover_greeting_pending = false
		return
	if not _hover_greeting_pending:
		return
	if now_msec - _hover_entered_at_msec < HOVER_GREETING_DWELL_MS or now_msec < _next_hover_greeting_at_msec:
		return
	if animation_player.has_active_frame_animation():
		return
	_hover_greeting_pending = false
	_next_hover_greeting_at_msec = now_msec + HOVER_GREETING_COOLDOWN_MS
	reset_inactivity()
	play_action(&"wave")

func _event_hits_visible_pixels(window_point: Vector2, include_animation_frames: bool = false) -> bool:
	var local := character.to_local(window_point)
	if animation_player != null and animation_player.current_action == &"phone":
		return animation_player.hit_test_gesture(local)
	if animation_player != null and animation_player.hit_test_gesture(local):
		return true
	var hit_image := _mouse_passthrough_mask_image if include_animation_frames and _mouse_passthrough_mask_image != null else _input_mask_image
	var image_size := Vector2(hit_image.get_width(), hit_image.get_height())
	var pixel_x := floori(local.x + image_size.x * 0.5)
	var pixel_y := floori(local.y + image_size.y * 0.5)
	if character.flip_h:
		pixel_x = hit_image.get_width() - 1 - pixel_x
	if pixel_x < 0 or pixel_y < 0 or pixel_x >= hit_image.get_width() or pixel_y >= hit_image.get_height():
		return false
	return hit_image.get_pixel(pixel_x, pixel_y).a >= ALPHA_HIT_THRESHOLD

func _refresh_mouse_passthrough() -> void:
	if not bool(window_options.get("mousePassthrough", true)):
		DisplayServer.window_set_mouse_passthrough(PackedVector2Array())
		return
	var mask_source := _mouse_passthrough_mask_image if _mouse_passthrough_mask_image != null else _input_mask_image
	var sample := mask_source.duplicate()
	var sample_size := Vector2i(mini(sample.get_width(), 56), mini(sample.get_height(), 56))
	if sample.get_size() != sample_size:
		sample.resize(sample_size.x, sample_size.y, Image.INTERPOLATE_NEAREST)
	var points := PackedVector2Array()
	var sprite_size := Vector2(_input_mask_image.get_width(), _input_mask_image.get_height()) * sprite_base_scale
	for y in range(sample.get_height()):
		for x in range(sample.get_width()):
			if sample.get_pixel(x, y).a >= ALPHA_HIT_THRESHOLD:
				var horizontal_sample: float = 1.0 - float(x) / sample.get_width() if character.flip_h else float(x) / sample.get_width()
				var local_x: float = (horizontal_sample - 0.5) * sprite_size.x
				var local_y: float = (float(y) / sample.get_height() - 0.5) * sprite_size.y
				points.append(character.position + Vector2(local_x, local_y))
	if points.size() >= 3:
		_mouse_passthrough_base_hull = Geometry2D.convex_hull(points)
		DisplayServer.window_set_mouse_passthrough(_mouse_passthrough_base_hull)
	else:
		_mouse_passthrough_base_hull = PackedVector2Array()
		DisplayServer.window_set_mouse_passthrough(PackedVector2Array())

func update_gesture_passthrough(local_points: PackedVector2Array, replace_base: bool = false) -> void:
	if not bool(window_options.get("mousePassthrough", true)) or _mouse_passthrough_base_hull.size() < 3:
		return
	var points := PackedVector2Array() if replace_base else _mouse_passthrough_base_hull.duplicate()
	for point in local_points:
		points.append(character.to_global(point))
	DisplayServer.window_set_mouse_passthrough(Geometry2D.convex_hull(points) if not local_points.is_empty() else points)

func begin_drag() -> void:
	reset_inactivity()
	_drag_start_mouse = DisplayServer.mouse_get_position()
	_drag_window_offset = _drag_start_mouse - runtime_window.position
	drag_distance = 0.0

func follow_mouse() -> void:
	var mouse_position := DisplayServer.mouse_get_position()
	drag_distance = maxf(drag_distance, Vector2(mouse_position - _drag_start_mouse).length())
	var requested := mouse_position - _drag_window_offset
	runtime_window.position = screen_bounds.clamp_window_position(requested, runtime_window.size)

func finish_drag() -> void:
	follow_mouse()
	reset_inactivity()

func reset_inactivity() -> void:
	inactive_seconds = 0.0

func set_facing(direction: int) -> void:
	_facing_direction = -1 if direction < 0 else 1
	var directional_run := sprite_animation_frames.has(&"run_left") and sprite_animation_frames.has(&"run_right")
	character.flip_h = _facing_direction < 0 and not directional_run
	_refresh_mouse_passthrough()

func next_walk_direction() -> int:
	return -_facing_direction

func play_action(action: StringName) -> void:
	if action in [&"idle", &"waiting"]:
		_resting_state_id = &"WAITING" if action == &"waiting" else &"IDLE"
	var resolved_action := action
	if action == &"walk" and sprite_animation_frames.has(&"run_left") and sprite_animation_frames.has(&"run_right"):
		resolved_action = &"run_left" if _facing_direction < 0 else &"run_right"
	animation_player.play(resolved_action)

func resting_state_id() -> StringName:
	return _resting_state_id

func take_requested_action() -> StringName:
	var action := requested_action
	requested_action = &""
	return action

func set_window_y(value: int) -> void:
	var position := runtime_window.position
	position.y = value
	runtime_window.position = screen_bounds.clamp_window_position(position, runtime_window.size)
