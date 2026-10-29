extends Node2D

const ACTION_ORDER := ["idle", "run_left", "run_right", "wave_smile", "phone_crouch"]
const RIG_SCRIPT := preload("res://scripts/animation/photo_pet_rig_p0.gd")
const MAX_CHARACTER_HEIGHT := 330.0
const WINDOW_SIDE_PADDING := 26.0
const WINDOW_TOP_PADDING := 26.0
const WINDOW_BOTTOM_PADDING := 28.0

var manifest_path := ""
var manifest_data: Dictionary = {}
var actions: Array[Dictionary] = []
var action_index := 0
var action_id := "idle"
var action_elapsed := 0.0
var action_duration := 1.0
var action_manifest_dir := ""
var source_rig: Node2D
var key_pose_rig: Node2D
var fallback_sprite: Sprite2D
var frame_paths: Array[String] = []
var frame_cache: Dictionary = {}
var source_rig_ready := false
var use_frame_fallback := false
var display_scale := 1.0
var status_label: Label
var base_position := Vector2.ZERO


func configure(path: String) -> void:
	manifest_path = path


func _ready() -> void:
	var parsed = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
	if not parsed is Dictionary or int(parsed.get("schema_version", 0)) != 1:
		push_error("Invalid PetForge P0 action manifest")
		return
	manifest_data = parsed
	var canvas = parsed.get("canvas_size", [384, 512])
	if not canvas is Array or canvas.size() != 2:
		push_error("Invalid P0 canvas size")
		return
	action_manifest_dir = manifest_path.get_base_dir()
	for item in parsed.get("actions", []):
		if item is Dictionary and ACTION_ORDER.has(str(item.get("action_id", ""))):
			actions.append(item)
	if actions.is_empty():
		push_error("P0 action manifest contains no preview actions")
		return

	var canvas_size := Vector2i(int(canvas[0]), int(canvas[1]))
	if canvas_size.x <= 0 or canvas_size.y <= 0:
		push_error("P0 canvas dimensions must be positive")
		return
	var max_dimension := maxf(canvas_size.x, canvas_size.y)
	var screen_size: Vector2i = DisplayServer.screen_get_size()
	if screen_size.x <= 0 or screen_size.y <= 0:
		screen_size = Vector2i(1920, 1080)
	display_scale = minf(1.0, minf(MAX_CHARACTER_HEIGHT / max_dimension, minf((screen_size.x - 48.0) / canvas_size.x, (screen_size.y - 96.0) / canvas_size.y)))
	var character_size := Vector2(canvas_size) * display_scale
	var window_size := Vector2i(
		ceili(character_size.x + WINDOW_SIDE_PADDING * 2.0),
		ceili(character_size.y + WINDOW_TOP_PADDING + WINDOW_BOTTOM_PADDING)
	)
	base_position = Vector2(window_size.x * 0.5, WINDOW_TOP_PADDING + character_size.y * 0.5 - 24.0)
	position = base_position
	DisplayServer.window_set_size(window_size)
	DisplayServer.window_set_position(Vector2i(80, 80))
	Engine.max_fps = 60

	source_rig = Node2D.new()
	source_rig.set_script(RIG_SCRIPT)
	add_child(source_rig)
	var source_path := _resolve_asset_path(str(manifest_data.get("rig_manifest", "")))
	source_rig_ready = bool(source_rig.call("configure", source_path, action_manifest_dir))
	if source_rig_ready:
		source_rig.call("set_display_scale", display_scale)
	if not source_rig_ready:
		_ensure_fallback_sprite()
		_mark_all_actions_needs_fix("runtime_rig_unavailable")

	status_label = Label.new()
	status_label.position = Vector2(10, 8)
	status_label.add_theme_color_override("font_color", Color(0.18, 0.16, 0.15, 1.0))
	status_label.add_theme_font_size_override("font_size", 15)
	add_child(status_label)
	_play_index(0)


func _process(delta: float) -> void:
	if action_duration <= 0.0:
		return
	# Godot updates the timeline at 60 Hz; rig motion interpolates continuously over time.
	action_elapsed += minf(delta, 0.1)
	var phase := fposmod(action_elapsed, action_duration) / action_duration
	var pose_strength := _pose_envelope(action_id, phase)
	if source_rig_ready and not use_frame_fallback:
		var source_motion := action_id if action_id.begins_with("run_") else "idle"
		source_rig.call("apply_motion", source_motion, action_elapsed, action_duration, pose_strength)
		source_rig.modulate.a = 1.0 - pose_strength if key_pose_rig != null else 1.0
		if key_pose_rig != null:
			key_pose_rig.modulate.a = pose_strength
			key_pose_rig.call("apply_motion", action_id, action_elapsed, action_duration, pose_strength)
	else:
		_update_fallback_frame()
	position = base_position


func _unhandled_key_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	if event.keycode == KEY_ESCAPE:
		get_tree().quit()
		return
	if event.keycode >= KEY_1 and event.keycode <= KEY_5:
		_play_index(event.keycode - KEY_1)
	elif event.keycode == KEY_A:
		_record_review(true)
	elif event.keycode == KEY_N:
		_record_review(false)


func _play_index(index: int) -> void:
	if index < 0 or index >= actions.size():
		return
	action_index = index
	var action: Dictionary = actions[index]
	action_id = str(action.get("action_id", "idle"))
	action_duration = maxf(float(action.get("duration_seconds", 1.0)), 0.1)
	action_elapsed = 0.0
	frame_paths.clear()
	for relative_path in action.get("frame_paths", []):
		frame_paths.append(_resolve_asset_path(str(relative_path)))
	if key_pose_rig != null:
		key_pose_rig.queue_free()
		key_pose_rig = null
	var key_pose_manifest := str(action.get("key_pose_rig_manifest", ""))
	if source_rig_ready and not key_pose_manifest.is_empty():
		key_pose_rig = Node2D.new()
		key_pose_rig.set_script(RIG_SCRIPT)
		add_child(key_pose_rig)
		var key_pose_ready := bool(key_pose_rig.call("configure", _resolve_asset_path(key_pose_manifest), action_manifest_dir))
		if not key_pose_ready:
			key_pose_rig.queue_free()
			key_pose_rig = null
		else:
			key_pose_rig.call("set_display_scale", absf(source_rig.scale.x))
	use_frame_fallback = not source_rig_ready or (_requires_key_pose(action_id) and key_pose_rig == null)
	if use_frame_fallback:
		_ensure_fallback_sprite()
		fallback_sprite.visible = true
		if source_rig != null:
			source_rig.visible = false
		if key_pose_rig != null:
			key_pose_rig.visible = false
	else:
		if fallback_sprite != null:
			fallback_sprite.visible = false
		source_rig.visible = true
		if key_pose_rig != null:
			key_pose_rig.visible = true
	if use_frame_fallback:
		_update_fallback_frame()
		var fallback_issue := "key_pose_rig_unavailable" if source_rig_ready else "runtime_rig_unavailable"
		_mark_action_needs_fix(action, fallback_issue)
	status_label.text = "%s · %s · reviewed=%s | 1-5 action  A accept  N reject  Esc close" % [
		action_id, str(action.get("status", "")), str(action.get("reviewed", false))
	]


func _pose_envelope(next_action: String, phase: float) -> float:
	if next_action == "wave_smile":
		return _smoothstep(phase, 0.12, 0.29) * (1.0 - _smoothstep(phase, 0.77, 0.91))
	if next_action == "phone_crouch":
		return _smoothstep(phase, 0.08, 0.23) * (1.0 - _smoothstep(phase, 0.78, 0.95))
	return 0.0


func _smoothstep(value: float, edge0: float, edge1: float) -> float:
	var t := clampf((value - edge0) / (edge1 - edge0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


func _resolve_asset_path(asset_path: String) -> String:
	if asset_path.is_empty() or asset_path.is_absolute_path():
		return asset_path
	return action_manifest_dir.path_join(asset_path).simplify_path()


func _requires_key_pose(next_action: String) -> bool:
	return next_action == "wave_smile" or next_action == "phone_crouch"


func _ensure_fallback_sprite() -> void:
	if fallback_sprite != null:
		return
	fallback_sprite = Sprite2D.new()
	fallback_sprite.centered = true
	fallback_sprite.scale = Vector2.ONE * display_scale
	add_child(fallback_sprite)


func _update_fallback_frame() -> void:
	if fallback_sprite == null or frame_paths.is_empty():
		return
	var phase := fposmod(action_elapsed, action_duration) / action_duration
	var index := mini(int(floor(phase * frame_paths.size())), frame_paths.size() - 1)
	var path := frame_paths[index]
	if frame_cache.has(path):
		fallback_sprite.texture = frame_cache[path]
		return
	var image := Image.new()
	if image.load(path) != OK:
		push_error("Could not load P0 preview frame: " + path)
		return
	var texture := ImageTexture.create_from_image(image)
	frame_cache[path] = texture
	fallback_sprite.texture = texture


func _record_review(accepted: bool) -> void:
	if action_index < 0 or action_index >= actions.size():
		return
	var action: Dictionary = actions[action_index]
	if accepted and str(action.get("status", "")) != "ready":
		status_label.text = "Cannot accept: preview status is not ready"
		return
	action["reviewed"] = true
	action["defects"] = [] if accepted else ["visual_review_rejected"]
	if not _save_manifest():
		status_label.text = "Could not save local review"
		return
	status_label.text = "%s · review %s saved | 1-5 action  A accept  N reject" % [
		action_id, "accepted" if accepted else "rejected"
	]


func _mark_all_actions_needs_fix(issue: String) -> void:
	for action in actions:
		_mark_action_needs_fix(action, issue, false)
	_save_manifest()


func _mark_action_needs_fix(action: Dictionary, issue: String, save: bool = true) -> void:
	var issues = action.get("issues", [])
	if not issues is Array:
		issues = []
	if not issues.has(issue):
		issues.append(issue)
	action["issues"] = issues
	action["status"] = "needs_fix"
	if action.get("reviewed") is bool and action.get("reviewed"):
		action["reviewed"] = false
	if save:
		_save_manifest()


func _save_manifest() -> bool:
	var file := FileAccess.open(manifest_path, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(manifest_data, "\t") + "\n")
	file.close()
	return true
