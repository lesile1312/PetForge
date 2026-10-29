extends Node2D

var canvas_size := Vector2i.ZERO
var joints_norm: Dictionary = {}
var limb_nodes: Dictionary = {}
var eye_sprite: Sprite2D
var body_sprite: Sprite2D
var display_scale := 1.0
var rig_ready := false


func configure(rig_manifest_path: String, asset_root: String = "") -> bool:
	var manifest_file := FileAccess.open(rig_manifest_path, FileAccess.READ)
	if manifest_file == null:
		return false
	var data = JSON.parse_string(manifest_file.get_as_text())
	manifest_file.close()
	if not data is Dictionary or int(data.get("schema_version", 0)) != 1:
		return false
	var size_data = data.get("canvas_size", [])
	if not size_data is Array or size_data.size() != 2:
		return false
	canvas_size = Vector2i(int(size_data[0]), int(size_data[1]))
	joints_norm = data.get("joints_norm", {})
	if canvas_size.x <= 0 or canvas_size.y <= 0:
		return false

	var root_dir := rig_manifest_path.get_base_dir() if asset_root.is_empty() else asset_root
	var body_path := _resolve_path(root_dir, str(data.get("base_body", "")))
	body_sprite = _make_sprite(body_path, 0)
	if body_sprite == null:
		return false
	add_child(body_sprite)
	var layer_data = data.get("layers", {})
	if not layer_data is Dictionary:
		return false
	for layer_name in ["left_leg", "right_leg", "left_arm", "right_arm"]:
		var details = layer_data.get(layer_name, {})
		if not details is Dictionary:
			return false
		var joint_name := str(details.get("pivot", ""))
		if not joints_norm.has(joint_name):
			return false
		var layer_path := _resolve_path(root_dir, str(details.get("path", "")))
		var pivot := _joint_position(joint_name)
		var part := Node2D.new()
		part.position = pivot
		part.z_index = -2 if layer_name.ends_with("leg") else 2
		var sprite := _make_sprite(layer_path, 0)
		if sprite == null:
			part.free()
			return false
		sprite.position = -pivot
		part.add_child(sprite)
		add_child(part)
		limb_nodes[layer_name] = part
	if limb_nodes.size() != 4:
		return false

	var eye_details = layer_data.get("eyes", {})
	if eye_details is Dictionary and eye_details.has("path"):
		var eye_path := _resolve_path(root_dir, str(eye_details.get("path", "")))
		eye_sprite = _make_sprite(eye_path, 5)
		if eye_sprite != null:
			var eye_offset = eye_details.get("offset_norm", [0.5, 0.3])
			if eye_offset is Array and eye_offset.size() == 2:
				eye_sprite.position = Vector2(float(eye_offset[0]) * canvas_size.x, float(eye_offset[1]) * canvas_size.y) - Vector2(canvas_size) * 0.5
			add_child(eye_sprite)
	rig_ready = true
	return true


func set_display_scale(value: float) -> void:
	display_scale = maxf(value, 0.01)
	scale = Vector2.ONE * display_scale


func apply_motion(action_id: String, elapsed: float, duration: float, pose_strength: float = 0.0) -> void:
	if not rig_ready:
		return
	position.y = 0.0
	scale = Vector2(-display_scale if action_id == "run_left" else display_scale, display_scale)
	for layer_name in limb_nodes:
		var part: Node2D = limb_nodes[layer_name]
		var joint_name := _pivot_name(layer_name)
		part.position = _joint_position(joint_name)
		part.rotation = 0.0
	if eye_sprite != null:
		eye_sprite.scale = Vector2.ONE

	var idle_cycle := sin(elapsed * TAU / 3.6)
	position.y = -idle_cycle * 0.8
	if action_id == "run_left" or action_id == "run_right":
		var direction := -1.0 if action_id == "run_left" else 1.0
		var cycle := sin(elapsed * TAU * 1.8) * direction
		_set_rotation("left_leg", cycle * 24.0)
		_set_rotation("right_leg", -cycle * 24.0)
		_set_rotation("left_arm", -cycle * 16.0)
		_set_rotation("right_arm", cycle * 16.0)
		position.y = -absf(cycle) * 1.8
	else:
		_set_rotation("left_arm", sin(elapsed * TAU / 2.8) * 1.1)
		_set_rotation("right_arm", -sin(elapsed * TAU / 2.8) * 1.1)
		if action_id == "wave_smile" and pose_strength > 0.0:
			var side := _raised_arm()
			_set_rotation(side, sin(elapsed * TAU * 1.7) * 2.2 * pose_strength)
		elif action_id == "phone_crouch" and pose_strength > 0.0:
			var tap := _tap_pulse(elapsed)
			_set_rotation("right_arm", -tap * 1.3 * pose_strength)
			_set_rotation("left_arm", tap * 0.8 * pose_strength)
			position.y += sin(elapsed * TAU * 0.7) * 0.35 * pose_strength
		_update_blink(elapsed)


func _update_blink(elapsed: float) -> void:
	if eye_sprite == null:
		return
	var blink_time := fposmod(elapsed, 3.7)
	var blink := maxf(0.0, 1.0 - absf(blink_time - 2.0) / 0.075)
	eye_sprite.scale.y = lerpf(1.0, 0.08, blink)


func _tap_pulse(elapsed: float) -> float:
	var pulse := 0.0
	for tap_time in [1.15, 2.65, 3.85]:
		pulse = maxf(pulse, exp(-pow((elapsed - tap_time) / 0.16, 2.0)))
	return pulse


func _raised_arm() -> String:
	for side in ["left", "right"]:
		var shoulder = joints_norm.get(side + "_shoulder", [])
		var wrist = joints_norm.get(side + "_wrist", [])
		if shoulder is Array and wrist is Array and shoulder.size() >= 2 and wrist.size() >= 2 and float(wrist[1]) < float(shoulder[1]):
			return side + "_arm"
	return "left_arm"


func _pivot_name(layer_name: String) -> String:
	var prefix := "left" if layer_name.begins_with("left") else "right"
	if layer_name.ends_with("arm"):
		return prefix + "_shoulder"
	return prefix + "_hip"


func _joint_position(joint_name: String) -> Vector2:
	var joint = joints_norm.get(joint_name, [0.5, 0.5, 0.0])
	return Vector2(float(joint[0]) * canvas_size.x, float(joint[1]) * canvas_size.y) - Vector2(canvas_size) * 0.5


func _set_rotation(layer_name: String, degrees: float) -> void:
	if limb_nodes.has(layer_name):
		(limb_nodes[layer_name] as Node2D).rotation = deg_to_rad(degrees)


func _resolve_path(root_dir: String, asset_path: String) -> String:
	if asset_path.is_empty():
		return ""
	if asset_path.is_absolute_path():
		return asset_path
	return root_dir.path_join(asset_path).simplify_path()


func _make_sprite(path: String, layer_z: int) -> Sprite2D:
	if path.is_empty():
		return null
	var image := Image.new()
	if image.load(path) != OK:
		return null
	var sprite := Sprite2D.new()
	sprite.texture = ImageTexture.create_from_image(image)
	sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	sprite.z_index = layer_z
	return sprite
