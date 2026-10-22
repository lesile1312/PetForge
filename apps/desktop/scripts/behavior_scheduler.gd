extends RefCounted
## Makes one weighted decision every few seconds while the pet is idle.

const CHECK_MIN_SECONDS := 2.5
const CHECK_MAX_SECONDS := 5.5
const JUMP_WEIGHT := 0.10
const SLEEP_WEIGHT := 0.05
const SOCIAL_ACTION_WEIGHT := 0.38
const SOCIAL_ACTIONS: Array[StringName] = [
	&"WAVE", &"HAPPY", &"DANCE", &"STRETCH", &"LOOK_AROUND",
	&"PEEK", &"SHY", &"SPIN", &"JUMP",
]

var _random := RandomNumberGenerator.new()

func _init() -> void:
	_random.randomize()

func next_decision_delay() -> float:
	return _random.randf_range(CHECK_MIN_SECONDS, CHECK_MAX_SECONDS)

func choose_action(behavior: Dictionary, inactive_seconds: float) -> StringName:
	var walk_weight := 0.0
	if bool(behavior.get("randomWalk", true)):
		match String(behavior.get("randomWalkFrequency", "medium")):
			"low": walk_weight = 0.12
			"high": walk_weight = 0.32
			_: walk_weight = 0.22
	var jump_weight := JUMP_WEIGHT if bool(behavior.get("randomJump", true)) else 0.0
	var sleep_ready := bool(behavior.get("autoSleep", true)) and inactive_seconds >= float(behavior.get("idleDuration", 20))
	var sleep_weight := SLEEP_WEIGHT if sleep_ready else 0.0
	var roll := _random.randf()
	if roll < SOCIAL_ACTION_WEIGHT:
		return SOCIAL_ACTIONS[_random.randi_range(0, SOCIAL_ACTIONS.size() - 1)]
	roll -= SOCIAL_ACTION_WEIGHT
	if roll < sleep_weight:
		return &"SLEEP"
	roll -= sleep_weight
	if roll < jump_weight:
		return &"JUMP"
	roll -= jump_weight
	if roll < walk_weight:
		return &"WALK"
	return &"IDLE"

func random_direction() -> int:
	return -1 if _random.randf() < 0.5 else 1

func random_walk_duration() -> float:
	return _random.randf_range(2.8, 3.4)

func should_hop_after_click() -> bool:
	return _random.randf() < 0.18
