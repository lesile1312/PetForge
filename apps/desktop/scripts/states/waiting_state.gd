extends "res://scripts/pet_state.gd"
## Quiet, attentive posture with occasional slow social gestures.

var _elapsed := 0.0
var _next_action := 7.0

func enter() -> void:
	_elapsed = 0.0
	_next_action = controller.ambient_repertoire.rest_seconds(&"",true)
	controller.play_action(&"waiting")

func update(delta: float) -> void:
	if controller.animation_player.has_active_frame_animation():
		return
	_elapsed += delta
	if _elapsed < _next_action:
		return
	var action: StringName = controller.ambient_repertoire.next_action(bool(controller.behavior.get("randomWalk", true)))
	if action == &"walk":
		controller.state_machine.change_state(&"WALK")
		return
	controller.play_action(action)
	_elapsed = 0.0
	_next_action = controller.ambient_repertoire.rest_seconds(action,true)

func exit() -> void:
	pass
