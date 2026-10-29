extends Node2D
## Continuous, fixed-proportion gestures over the original resting illustration.

const BODY_SHADER = preload("res://shaders/gesture_body.gdshader")
const PHONE_ACTION = preload("res://scripts/animation/phone_action.gd")
const ORIGIN := Vector2(128.0, 122.0)
const RAISED_FOREARM_LENGTH := 17.0
const MAX_WRIST_BEND := PI / 9.0
const DURATIONS := {&"wave": 2.65, &"hair_touch": 3.25, &"mirror": 3.65, &"happy": 1.45, &"bow": 2.05, &"phone": 16.0,
	&"think": 4.2, &"yawn": 4.5, &"stretch": 4.8, &"shy": 3.8, &"look": 4.6, &"heart": 3.8}

class HeartLayer extends Node2D:
	var amount := 0.0
	var progress := 0.0

	func _draw() -> void:
		if amount <= 0.001:
			return
		# A small floating gift above the open palm, separate from the character.
		var center := Vector2(0.0, -13.0 - progress * 9.0)
		var shape := PackedVector2Array()
		for i in range(64):
			var a := TAU * float(i) / 64.0
			var x := 16.0 * pow(sin(a), 3.0)
			var y := -(13.0 * cos(a) - 5.0 * cos(2.0*a) - 2.0 * cos(3.0*a) - cos(4.0*a))
			shape.append(center + Vector2(x, y) * 0.37)
		draw_colored_polygon(shape, Color(0.94, 0.49, 0.57, amount))
		draw_circle(center + Vector2(-2.3, -2.1), 1.1, Color(1.0, 0.88, 0.87, amount * 0.85), true, -1.0, true)

class ArmLayer extends Node2D:
	var shoulder := Vector2.ZERO
	var elbow := Vector2.ZERO
	var wrist := Vector2.ZERO
	var amount := 0.0
	var draw_upper := true
	var draw_lower := true
	var skin := Color("f6d5c5")
	var shadow := Color("efc2a7")
	var outline := Color("9b6957")
	var highlight := Color("fcddc6")

	func _draw() -> void:
		if amount <= 0.001:
			return
		var spine := PackedVector2Array()
		var widths := PackedFloat32Array()
		var enter := elbow.lerp(shoulder, .22)
		var leave := elbow.lerp(wrist, .22)
		if draw_upper:
			var end := enter if draw_lower else elbow
			for i in range(5):
				var u := float(i) / 4.0
				spine.append(shoulder.lerp(end, u))
				widths.append(lerpf(7.0, 6.2, u))
		if draw_lower:
			# A single rounded contour joins the upper arm and forearm, without
			# stacked segment caps or a hard rectangular elbow corner.
			for i in range(9):
				var u := float(i) / 8.0
				spine.append(enter * (1.0-u)*(1.0-u) + elbow * 2.0*u*(1.0-u) + leave * u*u)
				widths.append(6.2)
			for i in range(1, 6):
				var u := float(i) / 5.0
				spine.append(leave.lerp(wrist, u))
				widths.append(lerpf(6.2, 5.5, u))
		_draw_ribbon(spine, widths)
		if draw_lower:
			var side := (wrist - elbow).normalized().orthogonal() * 3.0
			draw_line(wrist - side, wrist + side, Color(0.47, 0.56, 0.69, amount), 2.4, true)
			draw_line(wrist - side + Vector2(0.0, -0.5), wrist + side + Vector2(0.0, -0.5), Color(0.77, 0.83, 0.91, amount), 0.9, true)

	func _draw_ribbon(spine: PackedVector2Array, widths: PackedFloat32Array) -> void:
		if spine.size() < 2:
			return
		var left := PackedVector2Array()
		var right := PackedVector2Array()
		for i in range(spine.size()):
			var before := spine[maxi(0, i-1)]
			var after := spine[mini(spine.size()-1, i+1)]
			var normal := (after-before).normalized().orthogonal() * widths[i] * .5
			left.append(spine[i]-normal)
			right.append(spine[i]+normal)
		var shape := left.duplicate()
		var colors := PackedColorArray()
		for i in range(left.size()):
			colors.append(Color(highlight.lerp(skin, .45), amount))
		for i in range(right.size()-1, -1, -1):
			shape.append(right[i])
			colors.append(Color(skin.lerp(shadow, .40), amount))
		draw_circle(spine[0], widths[0]*.5, Color(skin, amount), true, -1.0, true)
		draw_circle(spine[-1], widths[-1]*.5, Color(skin, amount), true, -1.0, true)
		draw_polygon(shape, colors)
		var closed := shape.duplicate()
		closed.append(shape[0])
		draw_polyline(closed, Color(outline, amount*.60), .65, true)

class TexturedHand extends Node2D:
	var sprite := Sprite2D.new()
	var hit_shape := PackedVector2Array()
	var source_forward_axis := 0.0
	var palm_center := Vector2.ZERO

	func _init() -> void:
		sprite.centered = true
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		add_child(sprite)

	func set_source(source: Dictionary) -> void:
		sprite.texture = source["texture"] as Texture2D
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS if bool(source.get("mipmaps", false)) else CanvasItem.TEXTURE_FILTER_LINEAR
		sprite.scale = Vector2.ONE * float(source["scale"])
		sprite.position = source["sprite_offset"] as Vector2
		hit_shape = source["polygon"] as PackedVector2Array
		source_forward_axis = float(source["source_forward_axis"])
		palm_center = source.get("palm_center", Vector2.ZERO)

	func contains(point: Vector2) -> bool:
		return Geometry2D.is_point_in_polygon(point, hit_shape)

class MirrorLayer extends Node2D:
	func _draw() -> void:
		# A small oval hand mirror, anchored to the same wrist as the grip.
		draw_line(Vector2(0.0, -1.0), Vector2(0.0, -17.0), Color("947151"), 3.7, true)
		draw_line(Vector2(-0.3, -1.0), Vector2(-0.3, -17.0), Color("d9c4a1"), 2.1, true)
		var center := Vector2(0.0, -26.0)
		draw_colored_polygon(_oval(center, Vector2(9.0, 12.1)), Color("927654"))
		draw_colored_polygon(_oval(center, Vector2(8.0, 11.1)), Color("e9dbc0"))
		draw_colored_polygon(_oval(center, Vector2(6.7, 9.7)), Color("bdcfd8"))
		draw_colored_polygon(_oval(center + Vector2(-0.8, -0.6), Vector2(6.0, 9.0)), Color("dce7e9"))
		draw_line(center + Vector2(-3.4, -4.2), center + Vector2(0.2, -7.2), Color(1.0, 1.0, 1.0, 0.86), 1.4, true)
		draw_line(center + Vector2(-2.5, 0.2), center + Vector2(3.1, -4.9), Color(1.0, 1.0, 1.0, 0.43), 2.0, true)

	func _oval(center: Vector2, radius: Vector2) -> PackedVector2Array:
		var points := PackedVector2Array()
		for i in range(48):
			var angle := TAU * float(i) / 48.0
			points.append(center + Vector2(cos(angle), sin(angle)) * radius)
		return points

var _host: Node
var _sprite: Sprite2D
var _material: ShaderMaterial
var _arm: ArmLayer
var _front_arm: ArmLayer
var _mirror: MirrorLayer
var _heart: HeartLayer
var _hand: TexturedHand
var _hand_sources: Dictionary = {}
var _durations: Dictionary = DURATIONS.duplicate()
var _base_texture: Texture2D
var _smile_texture: Texture2D
var _blank_texture: Texture2D
var _phone: Node2D
var _action: StringName = &""
var _elapsed := 0.0
var _shoulder := Vector2(102.3, 117.9)
var _rest_wrist := Vector2(101.1, 146.4)
var _rest_elbow := Vector2(99.2, 134.8)
var _wrist := Vector2.ZERO
var _elbow := Vector2.ZERO
var available := false

func configure(host: Node, target: Sprite2D, settings: Dictionary) -> void:
	_host = host
	_sprite = target
	var configured_durations: Dictionary = settings.get("durations", {})
	for action in DURATIONS:
		_durations[action] = maxf(0.5, float(configured_durations.get(String(action), DURATIONS[action])))
	var directory := String(host.config.get("_package_directory", ""))
	var config_path := directory.path_join(String(settings.get("sources", "rig/limb_sources.json")))
	var file := FileAccess.open(config_path, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		return
	var data: Dictionary = parsed
	var hand_data: Dictionary = data.get("hands", {})
	for action in hand_data:
		var source: Dictionary = hand_data[action]
		var image_path := directory.path_join(String(source["texture_path"]))
		var hand_image := Image.load_from_file(image_path)
		if hand_image.is_empty():
			push_warning("Could not load hand texture: " + image_path)
			continue
		var source_polygon := _points(source["polygon_uv_px"])
		var min_uv := Vector2(INF, INF)
		var max_uv := Vector2(-INF, -INF)
		for point in source_polygon:
			min_uv = min_uv.min(point)
			max_uv = max_uv.max(point)
		var crop_left := maxi(0, floori(min_uv.x))
		var crop_top := maxi(0, floori(min_uv.y))
		var crop_right := mini(hand_image.get_width(), ceili(max_uv.x) + 1)
		var crop_bottom := mini(hand_image.get_height(), ceili(max_uv.y) + 1)
		for y in range(crop_top, crop_bottom):
			for x in range(crop_left, crop_right):
				if not Geometry2D.is_point_in_polygon(Vector2(x + 0.5, y + 0.5), source_polygon):
					hand_image.set_pixel(x, y, Color.TRANSPARENT)
		var crop_rect := Rect2i(crop_left, crop_top, crop_right - crop_left, crop_bottom - crop_top)
		var hand_region := hand_image.get_region(crop_rect)
		hand_region.fix_alpha_edges()
		if bool(source.get("mipmaps", false)):
			hand_region.generate_mipmaps()
		var wrist_data: Array = source["wrist_pivot_px"]
		var wrist_pivot := Vector2(float(wrist_data[0]), float(wrist_data[1]))
		var palm_data: Array = source.get("palm_center_px", wrist_data)
		var uniform_scale := float(source["uniform_scale"])
		var crop_center := Vector2(crop_rect.size) * 0.5
		_hand_sources[StringName(action)] = {
			"texture": ImageTexture.create_from_image(hand_region),
			"polygon": _points(source["local_vertices_px"]),
			"scale": uniform_scale,
			"mipmaps": bool(source.get("mipmaps", false)),
			"palm_center": (Vector2(float(palm_data[0]), float(palm_data[1])) - wrist_pivot) * uniform_scale,
			"sprite_offset": (crop_center - wrist_pivot + Vector2(crop_rect.position)) * uniform_scale,
			"source_forward_axis": deg_to_rad(float(source["source_forward_axis_degrees"]))
		}
	_base_texture = ImageTexture.create_from_image(host.animation_frame_image(&"idle", 0))
	_smile_texture = ImageTexture.create_from_image(host.animation_frame_image(&"blink", 1))
	var blank := Image.create(256,244,false,Image.FORMAT_RGBA8)
	blank.fill(Color.TRANSPARENT)
	_blank_texture = ImageTexture.create_from_image(blank)
	_phone = PHONE_ACTION.new()
	add_child(_phone)
	_phone.configure(directory,_base_texture,_smile_texture)
	_material = ShaderMaterial.new()
	_material.shader = BODY_SHADER
	_material.set_shader_parameter("blink_texture", _smile_texture)
	var baseline: Dictionary = data["baselines"]["idle"]
	var shoulder_data: Array = baseline["shoulder_px"]
	var wrist_data: Array = baseline["rest_wrist_px"]
	var elbow_data: Array = baseline["rest_elbow_px"]
	_shoulder = Vector2(float(shoulder_data[0]), float(shoulder_data[1]))
	_rest_wrist = Vector2(float(wrist_data[0]), float(wrist_data[1]))
	_rest_elbow = Vector2(float(elbow_data[0]), float(elbow_data[1]))
	var mask_points := _points(baseline["original_arm_mask_polygons_px"][0])
	_material.set_shader_parameter("arm_polygon_count", mask_points.size())
	while mask_points.size() < 24:
		mask_points.append(Vector2.ZERO)
	_material.set_shader_parameter("arm_polygon", mask_points)
	_sprite.material = _material
	z_index = 1
	_arm = ArmLayer.new()
	_arm.z_index = -2
	add_child(_arm)
	_front_arm = ArmLayer.new()
	_front_arm.draw_upper = false
	_front_arm.z_index = 0
	add_child(_front_arm)
	_mirror = MirrorLayer.new()
	add_child(_mirror)
	_heart = HeartLayer.new()
	add_child(_heart)
	_hand = TexturedHand.new()
	_hand.z_index = 1
	add_child(_hand)
	available = true
	stop()

func supports(action: StringName) -> bool:
	return available and DURATIONS.has(action) and (action != &"phone" or _phone.available)

func play(action: StringName) -> void:
	_action = action
	_elapsed = 0.0
	_sprite.texture = _base_texture
	var source_action: StringName = {
		&"wave": &"open_greeting",
		&"hair_touch": &"hair_touch",
		&"mirror": &"mirror_grip",
		&"think": &"hair_touch", &"yawn": &"mouth_cover",
		&"stretch": &"open_greeting", &"shy": &"hair_touch", &"heart": &"open_greeting"
	}.get(action, action)
	var hand_source: Dictionary = _hand_sources.get(source_action, {})
	if not hand_source.is_empty():
		_hand.set_source(hand_source)
	_update_pose()

func stop() -> void:
	_action = &""
	if not available:
		return
	_arm.visible = false
	_front_arm.visible = false
	_phone.visible = false
	_sprite.texture = _base_texture
	_hand.visible = false
	_mirror.visible = false
	_heart.visible = false
	_material.set_shader_parameter("arm_amount", 0.0)
	_material.set_shader_parameter("head_angle", 0.0)
	_material.set_shader_parameter("head_drop", 0.0)
	_material.set_shader_parameter("gaze_offset_px", Vector2.ZERO)
	_material.set_shader_parameter("greeting_smile", 0.0)
	_material.set_shader_parameter("mouth_smile", 0.0)
	_material.set_shader_parameter("soft_smile", 0.0)
	_material.set_shader_parameter("gesture_blink", 0.0)
	_host.update_gesture_passthrough(PackedVector2Array())

func is_playing() -> bool:
	return _action != &""

func set_blink_amount(value: float) -> void:
	if _material != null:
		_material.set_shader_parameter("blink_amount", clampf(value, 0.0, 1.0))

func advance(delta: float) -> bool:
	if not is_playing():
		return false
	_elapsed = minf(_elapsed + delta, float(_durations[_action]))
	_update_pose()
	return _elapsed >= float(_durations[_action])

func _update_pose() -> void:
	var t := _elapsed * float(DURATIONS[_action]) / float(_durations[_action])
	if _action == &"phone":
		_arm.visible = false
		_front_arm.visible = false
		_hand.visible = false
		_mirror.visible = false
		_heart.visible = false
		_sprite.texture = _blank_texture
		_phone.visible = true
		_phone.update_pose(t)
		_host.update_gesture_passthrough(_phone.input_points(),true)
		return
	var arm_action := _action in [&"wave", &"hair_touch", &"mirror", &"think", &"yawn", &"stretch", &"shy", &"heart"]
	_arm.visible = arm_action
	# Bring only the forearm forward for gestures that touch the face.
	_front_arm.visible = arm_action and _action in [&"shy", &"think", &"yawn", &"hair_touch", &"mirror"]
	var inward_arm := _action in [&"think", &"yawn"]
	# Inward reaches need the upper arm over the torso too, connecting the elbow
	# below the chin to the shoulder rather than emerging from behind the face.
	_front_arm.draw_upper = inward_arm
	_arm.draw_upper = not inward_arm
	_arm.draw_lower = not _front_arm.visible
	_hand.visible = arm_action
	_mirror.visible = _action == &"mirror"
	_heart.visible = _action in [&"heart", &"wave"]
	var head_angle := 0.0
	var head_drop := 0.0
	var gaze_offset := Vector2.ZERO
	var greeting_smile := 0.0
	var mouth_smile := 0.0
	var soft_smile := 0.0
	var gesture_blink := 0.0
	if not arm_action:
		if _action == &"happy":
			greeting_smile = _envelope(t,.28,.88,1.32)
		elif _action == &"bow":
			var nod := _envelope(t, 0.58, 1.03, 1.83)
			head_drop = nod * 3.5
			greeting_smile = _envelope(t-.2,.25,.85,1.22)
		elif _action == &"look":
			# Two deliberate looks with a pause, rather than continuous head wobble.
			var left := _envelope(t, .85, 1.45, 2.15)
			var right := _envelope(t-2.1, .75, 1.20, 2.10)
			head_angle = -.055*left + .045*right
			gaze_offset = Vector2(-1.15*left + 1.1*right, -.25*left)
			gesture_blink = _blink_pulse(t, 2.0, .2)
		_material.set_shader_parameter("arm_amount", 0.0)
	else:
		var target := Vector2.ZERO
		var rise := 0.0
		var hold_until := 0.0
		var lower_until := 0.0
		var lift := 0.0
		var axis := -PI * 0.5
		var offset := Vector2.ZERO
		if _action == &"wave":
			soft_smile = .7*_envelope(t-.25,.4,1.55,2.0)
			gesture_blink = _blink_pulse(t,1.55,.18)
			_heart.amount = _envelope(t-.75,.25,.75,1.35)
			_heart.progress = _ease((t-.8)/1.25)
			target = Vector2(82.0, 103.0)
			rise = 0.95
			hold_until = 1.65
			lower_until = 2.50
			var phase := clampf((t - 1.00) / 0.65, 0.0, 1.0)
			var wave := sin(phase * TAU) * sin(phase * PI)
			axis += wave * 0.17
			offset = Vector2(wave * 0.8, 0.0)
		elif _action == &"hair_touch":
			target = Vector2(85.0, 99.0)
			rise = 1.05
			hold_until = 2.15
			lower_until = 3.08
			var phase := clampf((t - 1.12) / 0.90, 0.0, 1.0)
			var stroke := (1.0 - cos(phase * TAU)) * 0.5
			offset = Vector2(0.9, 2.6) * stroke
			axis = deg_to_rad(-68.0) + 0.025 * sin(phase * TAU)
			var touch_look := _envelope(t,.9,2.0,2.7)
			gaze_offset = Vector2(-1.2,-.8)*touch_look
			mouth_smile = .6*_envelope(t-.8,.4,1.35,1.9)
			gesture_blink = _blink_pulse(t,2.05,.21)
		elif _action == &"mirror":
			target = Vector2(92.0, 117.0)
			rise = 1.00
			hold_until = 2.38
			lower_until = 3.43
			axis = deg_to_rad(-90.0)
			var mirror_look := _envelope(t, 1.08, 2.40, 3.30)
			# Tilt the intact head toward the mirror around the neck; preserve its shape.
			head_angle = -0.12 * mirror_look
			gaze_offset = Vector2(-1.4, .8) * mirror_look
			soft_smile = .35*_envelope(t-1.4,.45,.9,1.35)
			gesture_blink = _blink_pulse(t,.52,.18)
		elif _action == &"think":
			# Fingertips settle below the chin; only the gaze moves once settled.
			target = Vector2(119.5, 115.5)
			rise = 1.05
			hold_until = 3.00
			lower_until = 4.05
			axis = deg_to_rad(-62.0)
			var pondering := _envelope(t-.3,.8,2.6,3.5)
			head_angle = .055*pondering
			gaze_offset = Vector2(.8,-.65)*pondering
			gesture_blink = _blink_pulse(t,2.75,.2)
		elif _action == &"yawn":
			# The dedicated hand rests over the lips with a neutral wrist.
			target = Vector2(123.0, 108.0)
			rise = 1.15
			hold_until = 3.15
			lower_until = 4.32
			var covered_smile := _envelope(t-1.0,.46,1.35,2.10)
			gesture_blink = covered_smile
			soft_smile = .45 * covered_smile
			head_drop = .4 * covered_smile
		elif _action == &"stretch":
			# A relaxed outward arm stretch within the original arm's reach.
			target = Vector2(75.0, 110.0)
			rise = 1.30
			hold_until = 3.20
			lower_until = 4.62
			axis = deg_to_rad(-142.0)
			var loosen := _envelope(t-.2,.95,2.75,4.15)
			head_angle = .045*loosen
			soft_smile = .6*loosen
			gesture_blink = _envelope(t-1.4,.24,.55,.85)
		elif _action == &"shy":
			target = Vector2(96.0, 112.5)
			rise = 1.00
			hold_until = 2.55
			lower_until = 3.63
			axis = deg_to_rad(-38.0)
			var bashful := _envelope(t-.25,.7,2.25,3.35)
			head_angle = .065*bashful
			gaze_offset = Vector2(.65,.65)*bashful
			soft_smile = .8*bashful
			gesture_blink = _blink_pulse(t,2.1,.2)
		elif _action == &"heart":
			target = Vector2(90.0, 120.0)
			rise = 1.05
			hold_until = 2.55
			lower_until = 3.63
			axis = deg_to_rad(-100.0)
			soft_smile = .8*_envelope(t-.25,.55,2.25,3.2)
			head_angle = -.035*_envelope(t-.3,.65,2.15,3.15)
			gesture_blink = _blink_pulse(t,2.35,.18)
			_heart.amount = _envelope(t-1.05,.25,1.0,1.45)
			_heart.progress = _ease((t-1.1)/1.35)
		lift = _envelope(t, rise, hold_until, lower_until)
		var bend_side := 1.0 if inward_arm else -1.0
		var outward_reach := _action in [&"wave", &"stretch", &"heart"]
		var raised_forearm := _pose_arm(target + offset, lift, bend_side, outward_reach)
		var amount := _ease(lift/.22)
		_arm.shoulder = _shoulder - ORIGIN
		_arm.elbow = _elbow - ORIGIN
		_arm.wrist = _wrist - ORIGIN
		_arm.amount = amount
		_arm.queue_redraw()
		_front_arm.shoulder = _arm.shoulder
		_front_arm.elbow = _arm.elbow
		_front_arm.wrist = _arm.wrist
		_front_arm.amount = amount
		_front_arm.queue_redraw()
		_hand.position = _wrist - ORIGIN
		var wrist_bend := clampf(angle_difference(raised_forearm.angle(), axis), -MAX_WRIST_BEND, MAX_WRIST_BEND) * lift
		if _action == &"yawn":
			wrist_bend = deg_to_rad(3.0) * lift
		var hand_direction := (_wrist - _elbow).angle() + wrist_bend
		_hand.rotation = hand_direction - _hand.source_forward_axis
		_hand.modulate.a = amount
		_mirror.position = _wrist - ORIGIN
		_mirror.rotation = _hand.rotation - 0.08 * lift
		_mirror.modulate.a = amount * _ease(t / 0.38) * (1.0 - _ease((t - 3.15) / 0.40))
		_heart.position = _hand.position + _hand.palm_center.rotated(_hand.rotation) + Vector2(0.0,-2.0)
		_heart.queue_redraw()
		_material.set_shader_parameter("arm_amount", amount)
		_host.update_gesture_passthrough(_input_points())
	_material.set_shader_parameter("head_angle", head_angle)
	_material.set_shader_parameter("head_drop", head_drop)
	_material.set_shader_parameter("gaze_offset_px", gaze_offset)
	_material.set_shader_parameter("greeting_smile", greeting_smile)
	_material.set_shader_parameter("mouth_smile", mouth_smile)
	_material.set_shader_parameter("soft_smile", soft_smile)
	_material.set_shader_parameter("gesture_blink", gesture_blink)

func hit_test(local_point: Vector2) -> bool:
	if is_playing() and _action == &"phone":
		return _phone.contains(local_point)
	if not is_playing() or not _hand.visible:
		return false
	var hand_local := (local_point - _hand.position).rotated(-_hand.rotation)
	if _hand.contains(hand_local):
		return true
	if _mirror.visible:
		var prop_local := (local_point - _mirror.position).rotated(-_mirror.rotation) - Vector2(0.0, -26.0)
		if pow(prop_local.x / 10.0, 2.0) + pow(prop_local.y / 13.0, 2.0) <= 1.0:
			return true
	var nearest := Geometry2D.get_closest_point_to_segment(local_point, _arm.elbow, _arm.wrist)
	return nearest.distance_to(local_point) <= 3.5

func _input_points() -> PackedVector2Array:
	var points := PackedVector2Array()
	for point in _hand.hit_shape:
		points.append(point.rotated(_hand.rotation) + _hand.position)
	for center in [_arm.elbow, _arm.wrist]:
		points.append(center + Vector2(-4.0, -4.0))
		points.append(center + Vector2(4.0, 4.0))
	if _mirror.visible:
		for corner in [Vector2(-10.0, -39.0), Vector2(10.0, -39.0), Vector2(-10.0, -13.0), Vector2(10.0, -13.0)]:
			points.append(corner.rotated(_mirror.rotation) + _mirror.position)
	return points

func _pose_arm(target: Vector2, lift: float, bend_side: float, outward: bool) -> Vector2:
	var upper_rest := _rest_elbow - _shoulder
	var forearm_rest := _rest_wrist - _rest_elbow
	var reach := target - _shoulder
	var max_reach := upper_rest.length() + RAISED_FOREARM_LENGTH - 1.0
	var safe_target := _shoulder + reach.normalized() * clampf(reach.length(), 4.0, max_reach)
	var raised_elbow := _solve_elbow(_shoulder, safe_target, bend_side, upper_rest.length(), RAISED_FOREARM_LENGTH)
	var upper_raised := raised_elbow - _shoulder
	var forearm_raised := safe_target - raised_elbow
	var upper_angle := upper_rest.angle() + angle_difference(upper_rest.angle(), upper_raised.angle()) * lift
	# Outward gestures rotate around the outside of the body. Lock this branch
	# so a tiny change near 180 degrees cannot flip the intermediate forearm.
	var forearm_turn := fposmod(forearm_raised.angle() - forearm_rest.angle(), TAU) if outward else -fposmod(forearm_rest.angle() - forearm_raised.angle(), TAU)
	var forearm_angle := forearm_rest.angle() + forearm_turn * lift
	_elbow = _shoulder + Vector2.from_angle(upper_angle) * upper_rest.length()
	_wrist = _elbow + Vector2.from_angle(forearm_angle) * lerpf(forearm_rest.length(), RAISED_FOREARM_LENGTH, lift)
	return forearm_raised

func _solve_elbow(shoulder: Vector2, wrist: Vector2, bend_side: float, upper: float, lower: float) -> Vector2:
	var delta := wrist - shoulder
	var distance := clampf(delta.length(), 1.1, upper + lower - 0.01)
	var direction := delta.normalized()
	var along := (upper * upper - lower * lower + distance * distance) / (2.0 * distance)
	var height := sqrt(maxf(0.0, upper * upper - along * along))
	return shoulder + direction * along + Vector2(-direction.y, direction.x) * height * bend_side

func _envelope(t: float, rise: float, hold_until: float, lower_until: float) -> float:
	return _ease(t / rise) * (1.0 - _ease((t - hold_until) / (lower_until - hold_until)))

func _ease(value: float) -> float:
	var t := clampf(value, 0.0, 1.0)
	return t * t * t * (10.0 + t * (-15.0 + 6.0 * t))

func _points(values: Array) -> PackedVector2Array:
	var points := PackedVector2Array()
	for value in values:
		points.append(Vector2(float(value[0]), float(value[1])))
	return points

func _blink_pulse(t: float, start: float, duration: float) -> float:
	var phase := (t-start)/duration
	return sin(PI*phase) if phase>0.0 and phase<1.0 else 0.0
