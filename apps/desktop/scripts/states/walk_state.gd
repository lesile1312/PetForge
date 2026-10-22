extends "res://scripts/pet_state.gd"

var _direction := 1
var _elapsed := 0.0
var _walk_for := 3.0
var _subpixel := 0.0

func enter() -> void:
	_elapsed = 0.0
	_subpixel = 0.0
	_direction = controller.next_walk_direction()
	_walk_for = controller.behavior_scheduler.random_walk_duration()
	controller.set_facing(_direction)
	controller.play_action(&"walk")

func update(delta: float) -> void:
	_elapsed += delta
	var exact_pixels := float(controller.behavior.get("moveSpeed", 100)) * delta * _direction + _subpixel
	var whole_pixels := roundi(exact_pixels)
	_subpixel = exact_pixels - whole_pixels
	var window_position: Vector2i = controller.runtime_window.position
	var requested := Vector2i(window_position.x + whole_pixels, window_position.y)
	var clamped: Vector2i = controller.screen_bounds.clamp_window_position(requested, controller.runtime_window.size)
	if clamped.x != requested.x:
		_direction = -_direction
		_subpixel = 0.0
		controller.set_facing(_direction)
		controller.play_action(&"walk")
	controller.runtime_window.position = clamped
	if _elapsed >= _walk_for:
		controller.state_machine.change_state(&"IDLE")
