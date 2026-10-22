extends Node2D
## Draws softly feathered lids in the character's local sprite coordinates.

const LEFT_EYE_CENTER := Vector2(-20.0, -45.0)
const RIGHT_EYE_CENTER := Vector2(21.0, -45.0)
const EYE_RADIUS := Vector2(12.5, 8.5)

var _closed_amount := 0.0
var _use_waiting_palette := false
var _idle_left_skin := Color(0.96, 0.72, 0.66)
var _idle_right_skin := Color(0.96, 0.72, 0.66)
var _waiting_left_skin := Color(0.96, 0.72, 0.66)
var _waiting_right_skin := Color(0.96, 0.72, 0.66)

func configure(idle_image: Image, waiting_image: Image) -> void:
	_idle_left_skin = _sample_cheek(idle_image, Rect2i(101, 86, 10, 5))
	_idle_right_skin = _sample_cheek(idle_image, Rect2i(145, 86, 10, 5))
	_waiting_left_skin = _sample_cheek(waiting_image, Rect2i(101, 86, 10, 5))
	_waiting_right_skin = _sample_cheek(waiting_image, Rect2i(145, 86, 10, 5))
	z_index = 1

func set_waiting_palette(value: bool) -> void:
	_use_waiting_palette = value
	queue_redraw()

func set_closed_amount(value: float) -> void:
	_closed_amount = clampf(value, 0.0, 1.0)
	queue_redraw()

func _draw() -> void:
	if _closed_amount <= 0.001:
		return
	var left_skin := _waiting_left_skin if _use_waiting_palette else _idle_left_skin
	var right_skin := _waiting_right_skin if _use_waiting_palette else _idle_right_skin
	var eye_offset := Vector2(0.0, 4.0) if _use_waiting_palette else Vector2.ZERO
	_draw_eye(LEFT_EYE_CENTER + eye_offset, left_skin)
	_draw_eye(RIGHT_EYE_CENTER + eye_offset, right_skin)

func _draw_eye(center: Vector2, skin: Color) -> void:
	# Overlapping translucent ellipses feather the patch into the cheek while
	# the opaque inner lid removes the original pupil cleanly.
	var rings := [
		Vector2(1.10, 0.04),
		Vector2(1.02, 0.05),
		Vector2(0.94, 0.07),
		Vector2(0.86, 0.10),
		Vector2(0.78, 0.15),
		Vector2(0.70, 0.22),
	]
	for ring in rings:
		var points := _ellipse_points(center, EYE_RADIUS * ring.x, 32)
		var fill := skin
		fill.a = ring.y * _closed_amount
		draw_colored_polygon(points, fill)
	var core_points := _ellipse_points(center, EYE_RADIUS * Vector2(0.98, 1.03), 32)
	var core_fill := skin
	core_fill.a = _closed_amount
	draw_colored_polygon(core_points, core_fill)

	var lid_points := PackedVector2Array()
	for index in range(17):
		var t := float(index) / 16.0
		var x := lerpf(-10.8, 10.8, t)
		var normalized_x := x / 10.8
		var y := -1.5 + 2.7 * normalized_x * normalized_x
		lid_points.append(center + Vector2(x, y))
	draw_polyline(lid_points, Color(0.30, 0.15, 0.13, _closed_amount), 1.8, true)

	var left_lash := PackedVector2Array([
		center + Vector2(-10.0, 0.9),
		center + Vector2(-12.0, 2.3),
	])
	var right_lash := PackedVector2Array([
		center + Vector2(10.0, 0.9),
		center + Vector2(12.0, 2.3),
	])
	draw_polyline(left_lash, Color(0.30, 0.15, 0.13, _closed_amount * 0.82), 1.35, true)
	draw_polyline(right_lash, Color(0.30, 0.15, 0.13, _closed_amount * 0.82), 1.35, true)

func _ellipse_points(center: Vector2, radius: Vector2, segments: int) -> PackedVector2Array:
	var points := PackedVector2Array()
	for index in range(segments):
		var angle := TAU * float(index) / float(segments)
		points.append(center + Vector2(cos(angle) * radius.x, sin(angle) * radius.y))
	return points

func _sample_cheek(image: Image, area: Rect2i) -> Color:
	if image == null or image.is_empty():
		return Color(0.96, 0.72, 0.66)
	var total := Color(0.0, 0.0, 0.0, 0.0)
	var count := 0
	for y in range(area.position.y, mini(area.end.y, image.get_height())):
		for x in range(area.position.x, mini(area.end.x, image.get_width())):
			var pixel := image.get_pixel(x, y)
			if pixel.a >= 0.5:
				total += Color(pixel.r, pixel.g, pixel.b, 1.0)
				count += 1
	if count == 0:
		return Color(0.96, 0.72, 0.66)
	total /= float(count)
	return total
