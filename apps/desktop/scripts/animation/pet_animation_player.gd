extends RefCounted
## Interface for static, sprite-sheet, and future generated animation players.

var sprite: Sprite2D

func configure(target: Sprite2D, _owner: Node, _badge: Label, _base_scale: Vector2) -> void:
	sprite = target

func play(_action: StringName) -> void:
	pass
