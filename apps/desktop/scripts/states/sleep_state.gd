extends "res://scripts/pet_state.gd"

var _elapsed := 0.0
var _label_tween: Tween
var _label_home := Vector2.ZERO

func enter() -> void:
	_elapsed = 0.0
	controller.play_action(&"sleep")
	controller.sleep_label.text = "Z  z  z"
	controller.sleep_label.visible = true
	controller.sleep_label.modulate.a = 0.0
	_label_home = controller.sleep_label.position
	_start_drift()

func update(delta: float) -> void:
	_elapsed += delta
	if _elapsed >= float(controller.behavior.get("sleepDuration", 120)):
		controller.state_machine.change_state(&"IDLE")

func exit() -> void:
	if _label_tween != null and _label_tween.is_running():
		_label_tween.kill()
	controller.sleep_label.visible = false
	controller.sleep_label.position = _label_home
	controller.sleep_label.modulate.a = 1.0

func _start_drift() -> void:
	_label_tween = controller.create_tween().set_loops()
	_label_tween.tween_property(controller.sleep_label, "position", _label_home + Vector2(0, -3), 3.2).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_label_tween.parallel().tween_property(controller.sleep_label, "modulate:a", 0.78, 3.2)
	_label_tween.tween_property(controller.sleep_label, "position", _label_home, 3.2).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	_label_tween.parallel().tween_property(controller.sleep_label, "modulate:a", 0.94, 3.2)
