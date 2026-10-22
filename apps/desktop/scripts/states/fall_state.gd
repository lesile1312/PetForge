extends "res://scripts/pet_state.gd"

const GRAVITY := 1480.0
var _velocity_y := 0.0

func enter() -> void:
	_velocity_y = 0.0
	controller.play_action(&"fall")

func update(delta: float) -> void:
	_velocity_y += GRAVITY * delta
	var position: Vector2i = controller.runtime_window.position
	var next_y: int = position.y + roundi(_velocity_y * delta)
	var floor: int = controller.screen_bounds.floor_y(controller.runtime_window.size)
	if next_y >= floor:
		controller.set_window_y(floor)
		controller.state_machine.change_state(&"IDLE")
		return
	controller.set_window_y(next_y)
