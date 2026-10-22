extends RefCounted
## One repertoire shared by IDLE and WAITING, so changing state cannot reset variety.

const ACTIONS: Array[StringName] = [
	&"think", &"look", &"shy", &"heart", &"stretch", &"yawn",
	&"hair_touch", &"mirror", &"phone", &"wave", &"bow", &"happy", &"walk",
]

var _bag: Array[StringName] = []
var _last: StringName = &""

func next_action(allow_walk: bool) -> StringName:
	if _bag.is_empty():
		_bag.assign(ACTIONS)
		_bag.shuffle()
		# No repeat where two shuffled rounds meet.
		if _bag.back() == _last:
			var swap: StringName = _bag[0]
			_bag[0] = _bag[_bag.size()-1]
			_bag[_bag.size()-1] = swap
	var action: StringName = _bag.pop_back()
	if action == &"walk" and not allow_walk:
		return next_action(allow_walk)
	_last = action
	return action

func rest_seconds(action: StringName, waiting: bool) -> float:
	if action == &"phone":
		return randf_range(2.0,3.0)
	return randf_range(1.5,3.0) if waiting else randf_range(1.0,2.5)
