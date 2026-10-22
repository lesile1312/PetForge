extends "res://scripts/pet_state.gd"
## Guarantees visible, varied gestures while the pet is idle.

var _elapsed := 0.0
var _next_action_at := 1.5
var _has_started := false
var _last_action_was_walk := false

func enter() -> void:
	_elapsed = 0.0
	if not _has_started:
		_next_action_at = randf_range(1.2, 2.2)
	elif _last_action_was_walk:
		_next_action_at = controller.ambient_repertoire.rest_seconds(&"walk",false)
	else:
		_next_action_at = controller.ambient_repertoire.rest_seconds(&"",false)
	_has_started = true
	_last_action_was_walk = false
	controller.play_action(&"idle")

func update(delta: float) -> void:
	if controller.animation_player.has_active_frame_animation():
		return
	_elapsed += delta
	if controller.inactive_seconds >= float(controller.behavior.get("waitAfter", 30.0)):
		controller.state_machine.change_state(&"WAITING")
		return
	if _elapsed < _next_action_at:
		return

	var action: StringName = controller.ambient_repertoire.next_action(bool(controller.behavior.get("randomWalk", true)))
	if action == &"walk":
		_last_action_was_walk = true
		controller.state_machine.change_state(&"WALK")
		return

	_last_action_was_walk = false
	controller.play_action(action)
	_elapsed = 0.0
	_next_action_at = controller.ambient_repertoire.rest_seconds(action,false)

func exit() -> void:
	pass
