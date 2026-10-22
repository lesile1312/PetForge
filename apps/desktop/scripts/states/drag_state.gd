extends "res://scripts/pet_state.gd"

var _released := false

func enter() -> void:
	_released = false
	controller.begin_drag()
	controller.play_action(&"drag")

func update(_delta: float) -> void:
	if _released:
		return
	if not Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		_finish_drag()
		return
	controller.follow_mouse()

func handle_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
		_finish_drag()

func exit() -> void:
	controller._refresh_mouse_passthrough()

func _finish_drag() -> void:
	if _released:
		return
	_released = true
	controller.finish_drag()
	var drag_distance: float = controller.drag_distance
	if drag_distance <= controller.CLICK_DISTANCE_PX:
		controller.state_machine.change_state(&"CLICK_REACTION")
	else:
		controller.state_machine.change_state(&"FALL")
