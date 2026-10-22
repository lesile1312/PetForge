extends RefCounted
## Reads the active monitor each time so movement adapts to display changes.

const FLOOR_MARGIN_PX := 42
const EDGE_MARGIN_PX := 0

func active_screen_rect() -> Rect2i:
	var screen_index := DisplayServer.get_primary_screen()
	return Rect2i(DisplayServer.screen_get_position(screen_index), DisplayServer.screen_get_size(screen_index))

func clamp_window_position(position: Vector2i, window_size: Vector2i) -> Vector2i:
	var screen := active_screen_rect()
	var min_x := screen.position.x + EDGE_MARGIN_PX
	var max_x := maxi(min_x, screen.position.x + screen.size.x - window_size.x - EDGE_MARGIN_PX)
	var min_y := screen.position.y
	var max_y := maxi(min_y, screen.position.y + screen.size.y - window_size.y - FLOOR_MARGIN_PX)
	return Vector2i(clampi(position.x, min_x, max_x), clampi(position.y, min_y, max_y))

func floor_y(window_size: Vector2i) -> int:
	var screen := active_screen_rect()
	return maxi(screen.position.y, screen.position.y + screen.size.y - window_size.y - FLOOR_MARGIN_PX)

func initial_position(window_size: Vector2i, placement: String) -> Vector2i:
	var screen := active_screen_rect()
	var x := screen.position.x + 24
	if placement == "right" or (placement == "random" and randf() >= 0.5):
		x = screen.position.x + screen.size.x - window_size.x - 24
	var y := floor_y(window_size)
	return clamp_window_position(Vector2i(x, y), window_size)
