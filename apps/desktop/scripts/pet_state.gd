extends Node
## Shared lifecycle contract for all runtime states.

var controller: Variant

func configure(owner: Variant) -> void:
	controller = owner

func enter() -> void:
	pass

func update(_delta: float) -> void:
	pass

func exit() -> void:
	pass

func handle_input(_event: InputEvent) -> void:
	pass
