extends SceneTree
## Deterministic rendered preview of the same player used by the desktop pet.

func _initialize() -> void:
	_run.call_deferred()

func _argument(key: String, fallback: String = "") -> String:
	var arguments := OS.get_cmdline_user_args()
	for i in range(arguments.size() - 1):
		if arguments[i] == key:
			return arguments[i + 1]
	return fallback

func _run() -> void:
	var controller: Node = load("res://scenes/main.tscn").instantiate()
	root.add_child(controller)
	await process_frame
	controller.set_process(false)
	controller.set_physics_process(false)
	controller.set_process_input(false)
	controller.set_process_unhandled_input(false)
	controller.state_machine.process_mode = Node.PROCESS_MODE_DISABLED
	var directory := _argument("--preview-output", "user://gesture-preview")
	DirAccess.make_dir_recursive_absolute(directory)
	var actions := _argument("--preview-actions", "wave,hair_touch,mirror,happy,bow").split(",")
	var stride := maxi(1, int(_argument("--preview-stride", "3")))
	var durations := {"wave": 2.65, "hair_touch": 3.25, "mirror": 3.65, "happy": 1.45, "bow": 2.05, "blink": 0.23, "phone": 16.0,
		"think": 4.2, "yawn": 4.5, "stretch": 4.8, "shy": 3.8, "look": 4.6, "heart": 3.8}
	var report: Dictionary = {}
	var blink_values: Array[float] = []
	for action_text in actions:
		var action := StringName(action_text)
		var duration := float(durations.get(action_text, 1.5))
		var action_directory := directory.path_join(action_text)
		DirAccess.make_dir_recursive_absolute(action_directory)
		controller.animation_player.play(&"idle" if action == &"blink" else action)
		if action == &"blink":
			controller.animation_player._play_rest_blink()
		var started_at := Time.get_ticks_usec()
		var count := ceili(duration * 60.0) + 1
		var poses: Array = []
		for frame in range(count):
			if frame > 0:
				controller.animation_player.advance(1.0 / 60.0)
			await process_frame
			await RenderingServer.frame_post_draw
			if frame % stride == 0 or frame == count - 1:
				root.get_texture().get_image().save_png(action_directory.path_join("%s_%03d.png" % [action_text, frame]))
			var rig: Variant = controller.animation_player._gesture_rig
			if rig != null:
				var gaze: Vector2 = rig._material.get_shader_parameter("gaze_offset_px")
				var head_angle: float = rig._material.get_shader_parameter("head_angle")
				var pose_data := {"t": float(frame) / 60.0, "wrist": [rig._wrist.x, rig._wrist.y], "elbow": [rig._elbow.x, rig._elbow.y], "gaze": [gaze.x, gaze.y], "head_angle": head_angle, "busy": controller.animation_player.has_active_frame_animation(), "smile":float(rig._material.get_shader_parameter("greeting_smile")), "mouth_smile":float(rig._material.get_shader_parameter("mouth_smile")), "gesture_blink":float(rig._material.get_shader_parameter("gesture_blink"))}
				if rig._hand.visible:
					var hand_axis: float = rig._hand.rotation + rig._hand.source_forward_axis
					pose_data["shoulder"] = [rig._shoulder.x, rig._shoulder.y]
					pose_data["upper_length"] = rig._shoulder.distance_to(rig._elbow)
					pose_data["forearm_length"] = rig._elbow.distance_to(rig._wrist)
					pose_data["wrist_bend_degrees"] = rad_to_deg(angle_difference((rig._wrist-rig._elbow).angle(), hand_axis))
					pose_data["sprite_scale"] = [controller.character.scale.x, controller.character.scale.y]
				if action == &"phone":
					pose_data["depth"] = rig._phone.pose_depth
					pose_data["head_scale"] = [rig._phone._head.scale.x,rig._phone._head.scale.y]
					pose_data["floor_y"] = rig._phone._grid[(rig._phone._rows-4)*9+4].y+122.0
					pose_data["smile"] = rig._phone.face_smile
					pose_data["gesture_blink"] = rig._phone.face_blink
					pose_data["right_press"] = rig._phone.right_press
					pose_data["left_press"] = rig._phone.left_press
					pose_data["swipe"] = rig._phone.swipe
					pose_data["neck_join_offset"] = rig._phone.neck_join_offset
					pose_data["head_position"] = [rig._phone._head.position.x, rig._phone._head.position.y]
				poses.append(pose_data)
				if action == &"blink":
					blink_values.append(float(rig._material.get_shader_parameter("blink_amount")))
		var wall_seconds := float(Time.get_ticks_usec() - started_at) / 1000000.0
		report[action_text] = {"duration": duration, "rendered_frames": count, "wall_seconds": wall_seconds, "observed_render_fps": float(count) / wall_seconds, "poses": poses}
		print("Rendered %s: %d frames at 60 Hz" % [action_text, count])
	if OS.get_cmdline_user_args().has("--render-only"):
		var render_report := FileAccess.open(directory.path_join("motion_report.json"), FileAccess.WRITE)
		render_report.store_string(JSON.stringify(report,"\t"))
		print("Gesture render: " + directory)
		quit()
		return
	# Check completion and state boundaries using the actual controller/player.
	controller.play_action(&"idle")
	controller.play_action(&"hair_touch")
	controller.inactive_seconds = 10000.0
	controller.state_machine.tick(1.0 / 60.0)
	var deferred_wait: bool = controller.state_machine.current_id == &"IDLE" and controller.animation_player.current_action == &"hair_touch"
	controller.animation_player.advance(1.1)
	var active_rig: Variant = controller.animation_player._gesture_rig
	var hand_center: Vector2 = active_rig._hand.position + Vector2(0.525, -7.575).rotated(active_rig._hand.rotation)
	var hand_hit: bool = controller._event_hits_visible_pixels(controller.character.to_global(hand_center), true)
	controller.animation_player.advance(100.0)
	controller.state_machine.tick(1.0 / 60.0)
	var waited_after_completion: bool = controller.state_machine.current_id == &"WAITING"
	controller.play_action(&"mirror")
	controller.animation_player.advance(100.0)
	var returned_to_wait: bool = controller.animation_player.current_action == &"waiting"
	var blink_peak := 0.0
	for amount in blink_values:
		blink_peak = maxf(blink_peak, amount)
	var blink_returns_open: bool = blink_values.size() > 0 and float(blink_values[blink_values.size() - 1]) < 0.02
	var mirror_gaze_tracks_prop := not actions.has("mirror")
	var mirror_head_tilts_to_prop := not actions.has("mirror")
	if report.has("mirror"):
		for pose in report["mirror"]["poses"]:
			if float(pose["gaze"][0]) <= -1.25 and float(pose["gaze"][1]) >= .7:
				mirror_gaze_tracks_prop = true
			if float(pose["head_angle"]) <= -0.11:
				mirror_head_tilts_to_prop = true
	report["checks"] = {"waiting_deferred_during_gesture": deferred_wait, "raised_hand_hit_test": hand_hit, "waiting_after_completion": waited_after_completion, "gesture_returns_to_waiting": returned_to_wait, "blink_closes_and_returns_open": not actions.has("blink") or (blink_peak >= 0.9 and blink_returns_open), "mirror_gaze_tracks_prop": mirror_gaze_tracks_prop, "mirror_head_tilts_to_prop": mirror_head_tilts_to_prop}
	if report.has("phone"):
		var depth_peak := 0.0
		var head_scale_fixed := true
		var feet_fixed := true
		for pose in report["phone"]["poses"]:
			depth_peak = maxf(depth_peak,float(pose["depth"]))
			head_scale_fixed = head_scale_fixed and absf(float(pose["head_scale"][0])-1.0)<.0001 and absf(float(pose["head_scale"][1])-1.0)<.0001
			feet_fixed = feet_fixed and absf(float(pose["floor_y"])-235.0)<.001
		controller.play_action(&"phone")
		controller.animation_player.advance(4.0)
		var phone: Variant=active_rig._phone
		var head_point: Vector2=phone._head.position+Vector2(0,-47)
		var phone_hit: bool=controller._event_hits_visible_pixels(controller.character.to_global(head_point),true)
		var empty_top_passes: bool=not controller._event_hits_visible_pixels(controller.character.to_global(Vector2(0,-92)),true)
		controller.animation_player.advance(100.0)
		var phone_finishes: bool=controller.animation_player.current_action==&"waiting" and not phone.visible
		controller.play_action(&"phone")
		controller.animation_player.advance(4.0)
		controller.play_action(&"run_right")
		var phone_clears: bool=not phone.visible and controller.animation_player.current_action==&"run_right"
		report["checks"].merge({"phone_reaches_squat":depth_peak>.98,"phone_head_keeps_scale":head_scale_fixed,"phone_feet_stay_grounded":feet_fixed,"phone_actual_shape_hit_test":phone_hit and empty_top_passes,"phone_returns_to_waiting":phone_finishes,"phone_clears_when_interrupted":phone_clears})
	for key in report["checks"]:
		if not bool(report["checks"][key]):
			push_error("Gesture runtime check failed: " + key)
	var file := FileAccess.open(directory.path_join("motion_report.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t"))
	print("Gesture previews: " + directory)
	quit()
