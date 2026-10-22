extends Node
## Queues transitions made during update so state lifecycle calls never recurse.

var controller: Variant
var states: Dictionary = {}
var current_state: Node
var current_id: StringName = &""
var _pending_id: StringName = &""
var _is_updating := false
var _is_transitioning := false

func configure(owner: Variant) -> void:
	controller = owner

func register_state(state_id: StringName, state_script: Script) -> void:
	var state: Node = state_script.new()
	state.name = String(state_id)
	state.call("configure", controller)
	add_child(state)
	states[state_id] = state

func change_state(state_id: StringName) -> void:
	if not states.has(state_id) or state_id == current_id:
		return
	_pending_id = state_id
	if not _is_updating and not _is_transitioning:
		_apply_pending()

func tick(delta: float) -> void:
	if current_state == null:
		return
	_is_updating = true
	current_state.call("update", delta)
	_is_updating = false
	_apply_pending()

func handle_input(event: InputEvent) -> void:
	if current_state != null:
		current_state.call("handle_input", event)
	_apply_pending()

func is_in_state(state_id: StringName) -> bool:
	return current_id == state_id

func _apply_pending() -> void:
	var transitions := 0
	while _pending_id != &"" and transitions < 8:
		transitions += 1
		var next_id := _pending_id
		_pending_id = &""
		_is_transitioning = true
		if current_state != null:
			current_state.call("exit")
		current_id = next_id
		current_state = states[next_id]
		current_state.call("enter")
		_is_transitioning = false
	if transitions == 8 and _pending_id != &"":
		push_error("Pet state transition loop detected; clearing pending transition.")
		_pending_id = &""
