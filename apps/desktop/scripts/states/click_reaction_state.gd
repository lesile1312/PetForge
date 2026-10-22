extends "res://scripts/pet_state.gd"

var _elapsed := 0.0
var _requested := false
var _action: StringName = &""
var _return_state: StringName = &"IDLE"

func enter() -> void:
	_elapsed = 0.0
	_action = controller.take_requested_action()
	_requested = _action != &""
	_return_state = controller.resting_state_id()
	controller.reset_inactivity()
	controller.play_action(_action if _requested else &"wave")

func update(delta: float) -> void:
	_elapsed += delta
	if _elapsed < 1.4:
		return
	if _requested and _action == &"sleep":
		controller.state_machine.change_state(&"SLEEP")
		return
	if controller.animation_player.has_active_frame_animation():
		return
	if not _requested and bool(controller.behavior.get("randomJump", true)) and controller.behavior_scheduler.should_hop_after_click():
		controller.state_machine.change_state(&"JUMP")
	else:
		controller.state_machine.change_state(_return_state)
