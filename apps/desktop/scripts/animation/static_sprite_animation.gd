extends "res://scripts/animation/pet_animation_player.gd"
## Procedural 2D motions for photo-derived cartoon sprites.

const EYE_BLINK_OVERLAY_SCRIPT = preload("res://scripts/animation/eye_blink_overlay.gd")
const GESTURE_RIG_SCRIPT = preload("res://scripts/animation/gesture_rig.gd")

var current_action: StringName = &"idle"
var _host: Node
var _badge: Label
var _home_position := Vector2.ZERO
var _base_scale := Vector2.ONE
var _motion: Tween
var _rest_blink_wait: Tween
var _rest_blink_motion: Tween
var _resting_action: StringName = &"idle"
var _rest_blink_elapsed := -1.0
var _blink_overlay: Node2D
var _gesture_rig: Node2D
var _frame_action: StringName = &""
var _frame_index := 0
var _frame_count := 0
var _frame_duration := 1.0 / 60.0
var _frame_accumulator := 0.0
var _frame_looping := false

func configure(target: Sprite2D, owner: Node, badge: Label, base_scale: Vector2) -> void:
	sprite = target
	_host = owner
	_badge = badge
	_home_position = target.position
	_base_scale = base_scale
	var rig_settings: Variant = owner.appearance.get("gestureRig", {})
	if rig_settings is Dictionary and bool(rig_settings.get("enabled", false)):
		_gesture_rig = Node2D.new()
		_gesture_rig.set_script(GESTURE_RIG_SCRIPT)
		_gesture_rig.name = "ContinuousGestureRig"
		target.add_child(_gesture_rig)
		_gesture_rig.configure(owner, target, rig_settings)
	var has_authored_blinks := (
		int(owner.call("animation_frame_count", &"blink")) > 0
		and int(owner.call("animation_frame_count", &"blink_waiting")) > 0
	)
	if not has_authored_blinks:
		_blink_overlay = Node2D.new()
		_blink_overlay.name = "EyeBlinkOverlay"
		_blink_overlay.set_script(EYE_BLINK_OVERLAY_SCRIPT)
		target.add_child(_blink_overlay)
		var idle_image: Image = owner.call("animation_frame_image", &"idle", 0)
		var waiting_image: Image = owner.call("animation_frame_image", &"waiting", 0)
		_blink_overlay.call("configure", idle_image, waiting_image)

func play(action: StringName) -> void:
	if _gesture_rig != null:
		_gesture_rig.stop()
	current_action = action
	_frame_action = &""
	_frame_index = 0
	_frame_count = 0
	_frame_accumulator = 0.0
	if _motion != null and _motion.is_running():
		_motion.kill()
	if _rest_blink_wait != null and _rest_blink_wait.is_running():
		_rest_blink_wait.kill()
	if _rest_blink_motion != null and _rest_blink_motion.is_running():
		_rest_blink_motion.kill()
	_rest_blink_elapsed = -1.0
	_set_blink_amount(0.0)
	if action in [&"idle", &"waiting"]:
		_resting_action = action
		_set_waiting_eye_palette(action == &"waiting")
	sprite.position = _home_position
	sprite.rotation = 0.0
	sprite.scale = _base_scale
	if action != &"idle" and int(_host.call("animation_frame_count", &"idle")) > 0 and int(_host.call("animation_frame_count", action)) == 0:
		_host.call("set_animation_frame", &"idle", 0)
	_badge.visible = false
	_badge.text = _badge_for(action)
	_badge.modulate.a = 1.0
	if _gesture_rig != null and _gesture_rig.supports(action):
		_host.call("set_animation_frame", _resting_action, 0)
		_gesture_rig.play(action)
		return
	if _play_frame_animation(action):
		return

	match action:
		&"idle":
			_play_idle()
		&"waiting":
			_play_waiting()
		&"walk":
			_play_walk()
		&"sleep":
			_play_sleep()
		&"jump":
			_play_jump()
		&"wave":
			_play_wave()
		&"happy":
			_play_happy()
		&"peek":
			_play_peek()
		&"shy":
			_play_shy()
		&"spin":
			_play_spin()
		&"stretch":
			_play_stretch()
		&"dance":
			_play_dance()
		&"angry":
			_play_angry()
		&"look":
			_play_look()
		&"drag":
			_play_drag()
		_:
			_play_idle()

func advance(delta: float) -> void:
	if _rest_blink_elapsed >= 0.0:
		_advance_rest_blink(delta)
	if _gesture_rig != null and _gesture_rig.is_playing():
		if _gesture_rig.advance(delta):
			play(_resting_action)
		return
	if _frame_action == &"" or _frame_count <= 0:
		return
	_frame_accumulator += delta
	while _frame_accumulator >= _frame_duration:
		_frame_accumulator -= _frame_duration
		_frame_index += 1
		if _frame_index >= _frame_count:
			if _frame_looping:
				_frame_index = 0
			else:
				var completed_action := _frame_action
				_frame_action = &""
				_frame_accumulator = 0.0
				if completed_action in [&"blink", &"blink_waiting"] and current_action in [&"idle", &"waiting"]:
					_host.call("set_animation_frame", current_action, 0)
					_schedule_rest_event()
				elif current_action == completed_action:
					play(_resting_action)
				return
		_host.call("set_animation_frame", _frame_action, _frame_index)
	if _frame_action in [&"run_left", &"run_right"]:
		_apply_run_secondary_motion()

func _apply_run_secondary_motion() -> void:
	if _frame_count <= 0 or _frame_duration <= 0.0:
		return
	var phase := fposmod(float(_frame_index) + _frame_accumulator / _frame_duration, float(_frame_count)) / float(_frame_count)
	var bounce := sin(phase * TAU * 2.0)
	var lift := maxf(0.0, bounce)
	var landing := maxf(0.0, -bounce)
	sprite.position = Vector2(_home_position.x, _home_position.y - lift * 1.6 + landing * 0.35)
	var squash := landing * 0.004
	sprite.scale = _base_scale * Vector2(1.0 + squash, 1.0 - squash)

func _play_idle() -> void:
	_set_waiting_eye_palette(false)
	if int(_host.call("animation_frame_count", &"idle")) > 0:
		_host.call("set_animation_frame", &"idle", 0)
	_schedule_rest_event()

func _schedule_rest_event(delay: float = -1.0) -> void:
	if current_action not in [&"idle", &"waiting"]:
		return
	_rest_blink_wait = _host.create_tween()
	var default_delay := randf_range(4.5, 7.0) if current_action == &"idle" else randf_range(6.5, 9.0)
	_rest_blink_wait.tween_interval(delay if delay > 0.0 else default_delay)
	_rest_blink_wait.tween_callback(_play_rest_event)

func _play_rest_event() -> void:
	if current_action not in [&"idle", &"waiting"]:
		return
	_play_rest_blink()

func _play_rest_blink() -> void:
	if current_action not in [&"idle", &"waiting"]:
		return
	if _gesture_rig != null and _gesture_rig.available:
		# Close just the eyes through the body shader so the head and body never
		# swap illustrations or shift a pixel during a blink.
		_rest_blink_elapsed = 0.0
		_set_blink_amount(0.0)
		return
	var rest_action := current_action
	var blink_action: StringName = &"blink_waiting" if rest_action == &"waiting" else &"blink"
	var authored_frame_count := int(_host.call("animation_frame_count", blink_action))
	if authored_frame_count > 0:
		var frame_fps := float(_host.call("animation_fps", blink_action))
		_frame_action = blink_action
		_frame_index = 0
		_frame_count = authored_frame_count
		_frame_duration = 1.0 / maxf(1.0, frame_fps)
		_frame_accumulator = 0.0
		_frame_looping = false
		_host.call("set_animation_frame", blink_action, 0)
		return
	if _blink_overlay == null:
		_schedule_rest_event()
		return
	_rest_blink_motion = _host.create_tween()
	_rest_blink_motion.tween_method(Callable(self, "_set_blink_amount"), 0.0, 1.0, 0.08).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	_rest_blink_motion.tween_interval(0.07)
	_rest_blink_motion.tween_method(Callable(self, "_set_blink_amount"), 1.0, 0.0, 0.12).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_rest_blink_motion.tween_callback(func() -> void:
		if current_action in [&"idle", &"waiting"]:
			_set_blink_amount(0.0)
			_schedule_rest_event()
	)

func _set_blink_amount(value: float) -> void:
	if _gesture_rig != null:
		_gesture_rig.set_blink_amount(value)
	if _blink_overlay != null:
		_blink_overlay.call("set_closed_amount", clampf(value, 0.0, 1.0))

func _advance_rest_blink(delta: float) -> void:
	_rest_blink_elapsed += maxf(delta, 0.0)
	if _rest_blink_elapsed < 0.075:
		_set_blink_amount(_smooth_step(_rest_blink_elapsed / 0.075))
	elif _rest_blink_elapsed < 0.11:
		_set_blink_amount(1.0)
	elif _rest_blink_elapsed < 0.23:
		_set_blink_amount(1.0 - _smooth_step((_rest_blink_elapsed - 0.11) / 0.12))
	else:
		_set_blink_amount(0.0)
		_rest_blink_elapsed = -1.0
		if current_action in [&"idle", &"waiting"]:
			_schedule_rest_event()

func _smooth_step(value: float) -> float:
	var t := clampf(value, 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)

func _set_waiting_eye_palette(waiting: bool) -> void:
	if _blink_overlay != null:
		_blink_overlay.call("set_waiting_palette", waiting)

func _play_waiting() -> void:
	_set_waiting_eye_palette(true)
	if int(_host.call("animation_frame_count", &"waiting")) > 0:
		_host.call("set_animation_frame", &"waiting", 0)
	_schedule_rest_event()

func _play_walk() -> void:
	_motion = _host.create_tween().set_loops()
	_motion.tween_property(sprite, "position", _home_position + Vector2(0, -1.4), 0.32).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_motion.tween_property(sprite, "position", _home_position, 0.32).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)

func _play_sleep() -> void:
	_set_waiting_eye_palette(_resting_action == &"waiting")
	_badge.text = "Z  z  z"
	var blink_action: StringName = &"blink_waiting" if _resting_action == &"waiting" else &"blink"
	if _gesture_rig != null and _gesture_rig.available:
		# Use the same registered eyelids as the short blink, keeping the original
		# resting face and body in place during a sustained closed-eye pose.
		_host.call("set_animation_frame", _resting_action, 0)
		_set_blink_amount(1.0)
	elif int(_host.call("animation_frame_count", blink_action)) > 1:
		_host.call("set_animation_frame", blink_action, 1)
	elif _blink_overlay != null:
		_motion = _host.create_tween()
		_motion.tween_method(Callable(self, "_set_blink_amount"), 0.0, 1.0, 0.24).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)

func _play_jump() -> void:
	_motion = _host.create_tween()
	_motion.tween_property(sprite, "position", _home_position + Vector2(0, -3.0), 0.32).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_motion.tween_property(sprite, "position", _home_position, 0.38).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN)
	_finish_when_done(&"jump")

func _play_wave() -> void:
	_badge.text = "Hi!"
	_motion = _host.create_tween()
	_motion.tween_interval(0.9)
	_finish_when_done(&"wave")

func _play_happy() -> void:
	_badge.text = "♥"
	_motion = _host.create_tween()
	_motion.tween_interval(0.9)
	_finish_when_done(&"happy")

func _play_spin() -> void:
	_badge.text = "♪"
	_motion = _host.create_tween()
	_motion.tween_interval(0.9)
	_finish_when_done(&"spin")

func _play_stretch() -> void:
	_motion = _host.create_tween()
	_badge.text = "…"
	_motion.tween_interval(1.2)
	_finish_when_done(&"stretch")

func _play_dance() -> void:
	_badge.text = "♪"
	_motion = _host.create_tween()
	_motion.tween_interval(1.2)
	_finish_when_done(&"dance")

func _play_angry() -> void:
	_badge.text = "!"
	_motion = _host.create_tween()
	_motion.tween_interval(1.0)
	_finish_when_done(&"angry")

func _play_look() -> void:
	_badge.text = "?"
	_motion = _host.create_tween()
	_motion.tween_interval(1.0)
	_finish_when_done(&"look")

func _play_peek() -> void:
	_badge.text = "…"
	_motion = _host.create_tween()
	_motion.tween_interval(1.0)
	_finish_when_done(&"peek")

func _play_shy() -> void:
	_badge.text = "♥"
	_motion = _host.create_tween()
	_motion.tween_interval(1.0)
	_finish_when_done(&"shy")

func _play_drag() -> void:
	sprite.position = _home_position

func _play_frame_animation(action: StringName) -> bool:
	if not _host.has_method("animation_frame_count") or not _host.has_method("set_animation_frame"):
		return false
	var frame_count := int(_host.call("animation_frame_count", action))
	if frame_count <= 0:
		return false
	if action in [&"idle", &"waiting"]:
		_host.call("set_animation_frame", action, 0)
		return false
	_frame_looping = action in [&"run_left", &"run_right"]
	var frame_fps := float(_host.call("animation_fps", action)) if _host.has_method("animation_fps") else 60.0
	_frame_action = action
	_frame_index = 0
	_frame_count = frame_count
	_frame_duration = 1.0 / maxf(1.0, frame_fps)
	_frame_accumulator = 0.0
	_host.call("set_animation_frame", action, 0)
	return true

func has_active_frame_animation() -> bool:
	return _frame_action != &"" or (_gesture_rig != null and _gesture_rig.is_playing())

func hit_test_gesture(local_point: Vector2) -> bool:
	return _gesture_rig != null and _gesture_rig.hit_test(local_point)

func _finish_when_done(action: StringName) -> void:
	_motion.tween_callback(func() -> void:
		if current_action == action:
			play(_resting_action)
	)

func _badge_for(action: StringName) -> String:
	match action:
		&"wave": return "Hi!"
		&"happy": return "♥"
		&"jump": return "!"
		&"sleep": return "Z  z  z"
		&"spin": return "↻"
		&"stretch": return "…"
		&"dance": return "♪"
		&"angry": return "!"
		&"look": return "?"
		&"peek": return "?"
		&"shy": return "♥"
		&"hair_touch": return "♡"
		&"mirror": return "✦"
		&"bow": return "☺"
		_: return ""
