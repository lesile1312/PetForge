extends Node2D
## Authored bent-knee poses, continuously interpolated on a shared body mesh.
const POSE_SHADER = preload("res://shaders/phone_pose.gdshader")
const FACE_SHADER = preload("res://shaders/gesture_body.gdshader")
const ORIGIN = Vector2(128,122)
const NECK_JOIN_OVERLAP_PX = 8.0
var available := false
var _poses: Array = []
var _textures: Array[Texture2D] = []
var _body := Polygon2D.new()
var _head := Sprite2D.new()
var _body_material := ShaderMaterial.new()
var _face_material := ShaderMaterial.new()
var _grid := PackedVector2Array()
var _outline := PackedVector2Array()
var _head_image: Image
var _neck := Vector2(128,112)
var _rows := 31
var _neck_row := 3
var pose_depth := 0.0
var face_smile := 0.0
var face_blink := 0.0
var right_press := 0.0
var left_press := 0.0
var swipe := 0.0
var neck_join_offset := 0.0

func configure(directory: String, base: Texture2D, smile: Texture2D) -> void:
    var file := FileAccess.open(directory.path_join("rig/phone/manifest.json"),FileAccess.READ)
    if file == null:
        return
    var data: Dictionary = JSON.parse_string(file.get_as_text())
    _poses = data["poses"]
    _rows = int(data["rows"])
    _neck_row = int(data["neck_row"])
    for pose in _poses:
        var image := Image.load_from_file(directory.path_join("rig/phone/"+String(pose["texture"])))
        if image.is_empty():
            return
        _textures.append(ImageTexture.create_from_image(image))
    var triangles: Array = []
    for row in range(_rows-1):
        for col in range(8):
            var a := row*9+col
            triangles.append(PackedInt32Array([a,a+1,a+10]))
            triangles.append(PackedInt32Array([a,a+10,a+9]))
    _body.polygons = triangles
    _body.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
    _body_material.shader = POSE_SHADER
    _body.material = _body_material
    add_child(_body)
    _head.texture = base
    _head_image = base.get_image()
    _face_material.shader = FACE_SHADER
    _face_material.set_shader_parameter("blink_texture",smile)
    _face_material.set_shader_parameter("head_clip_y",114.0)
    _face_material.set_shader_parameter("head_clip_feather_px",2.0)
    _head.material = _face_material
    _head.z_index = 1
    add_child(_head)
    available = true
    update_pose(0.0)
    visible = false

func update_pose(t: float) -> void:
    var a := 0
    var b := 1
    var u := 0.0
    if t < .65:
        u = _ease(t/.65)
    elif t < 1.10:
        a=1; b=1
    elif t < 1.95:
        a=1; b=2; u=_ease((t-1.10)/.85)
    elif t < 2.80:
        a=2; b=3; u=_ease((t-1.95)/.85)
    elif t < 13.10:
        a=3; b=3
    elif t < 13.95:
        a=3; b=2; u=_ease((t-13.10)/.85)
    elif t < 14.80:
        a=2; b=1; u=_ease((t-13.95)/.85)
    elif t < 15.25:
        a=1; b=1
    elif t < 15.90:
        a=1; b=0; u=_ease((t-15.25)/.65)
    else:
        a=0; b=0
    var ga: Array = _poses[a]["grid"]
    var gb: Array = _poses[b]["grid"]
    _grid = PackedVector2Array()
    var uvs := PackedVector2Array()
    var colors := PackedColorArray()
    for i in range(ga.size()):
        var va := _v(ga[i])
        var vb := _v(gb[i])
        _grid.append(va.lerp(vb,u)-ORIGIN)
        uvs.append(va)
        colors.append(Color(vb.x/256.0,vb.y/244.0,1,1))
    _body.polygon = _grid
    _body.uv = uvs
    _body.vertex_colors = colors
    _body.texture = _textures[a]
    _body_material.set_shader_parameter("next_texture",_textures[b])
    _body_material.set_shader_parameter("pose_mix",u)
    # Distinct finger gestures after settling: a pair of taps, read, swipe, read.
    # Only the hands deform; the phone, wrists, face and body remain steady.
    right_press = 0.0
    left_press = 0.0
    for tap_start in [3.35,4.15,9.0,11.65]:
        right_press = maxf(right_press,_finger_press(t,float(tap_start),.68))
    for tap_start in [5.10,9.95]:
        left_press = maxf(left_press,_finger_press(t,float(tap_start),.72))
    swipe = _ease((t-6.45)/.85)*(1.0-_ease((t-7.40)/.55))
    _body_material.set_shader_parameter("right_press",right_press)
    _body_material.set_shader_parameter("left_press",left_press)
    _body_material.set_shader_parameter("swipe_amount",swipe)
    _body_material.set_shader_parameter("phone_a",_v(_poses[a]["phone_center"]))
    _body_material.set_shader_parameter("phone_b",_v(_poses[b]["phone_center"]))
    _neck = _v(_poses[a]["neck"]).lerp(_v(_poses[b]["neck"]),u)
    # The generated body begins just below its chin, whereas the original head
    # includes a complete neck down to its collar. Overlap these neck regions
    # instead of stacking them. Use the same pose blend during entry and exit.
    neck_join_offset = NECK_JOIN_OVERLAP_PX * lerpf(0.0 if a == 0 else 1.0, 0.0 if b == 0 else 1.0, u)
    _head.position = _neck-Vector2(128,112)+Vector2(0.0,neck_join_offset)
    pose_depth = (_neck.y-112.0)/43.08
    var engaged := _ease((t-.45)/.65)*(1.0-_ease((t-14.8)/.6))
    face_smile = .30*_ease((t-4.3)/.55)*(1.0-_ease((t-5.6)/.65))
    face_smile += .22*_ease((t-9.5)/.65)*(1.0-_ease((t-10.8)/.7))
    face_blink = 0.0
    for blink_start in [1.0,3.45,6.8,9.0,12.2,14.8]:
        face_blink = maxf(face_blink,_pulse(t,float(blink_start),.20))
    # Preserve the original face and mouth; no closed-smile face crossfade.
    _face_material.set_shader_parameter("gaze_offset_px",Vector2(-.15,.65)*engaged)
    _face_material.set_shader_parameter("head_drop",0.0)
    _face_material.set_shader_parameter("greeting_smile",0.0)
    _face_material.set_shader_parameter("gesture_blink",face_blink)
    _face_material.set_shader_parameter("mouth_smile",0.0)
    _face_material.set_shader_parameter("soft_smile",face_smile)
    _outline = PackedVector2Array()
    for row in range(_neck_row,_rows-1):
        _outline.append(_grid[row*9+2])
    for row in range(_rows-2,_neck_row-1,-1):
        _outline.append(_grid[row*9+6])

func input_points() -> PackedVector2Array:
    var result := _outline.duplicate()
    for p in [Vector2(81,17),Vector2(175,17),Vector2(81,113),Vector2(175,113)]:
        result.append(p-ORIGIN+_head.position)
    return result

func contains(point: Vector2) -> bool:
    var hp := point-_head.position+ORIGIN
    if hp.x>=0 and hp.x<256 and hp.y>=0 and hp.y<113:
        if _head_image.get_pixel(floori(hp.x),floori(hp.y)).a>.15:
            return true
    return Geometry2D.is_point_in_polygon(point,_outline)

func _v(value: Array) -> Vector2:
    return Vector2(float(value[0]),float(value[1]))

func _ease(value: float) -> float:
    var x := clampf(value,0,1)
    return x*x*x*(10+x*(-15+6*x))

func _pulse(t: float, start: float, duration: float) -> float:
    var x := (t-start)/duration
    return sin(PI*x) if x>0 and x<1 else 0.0

func _finger_press(t: float, start: float, duration: float) -> float:
    var x := (t-start)/duration
    return _ease(x/.30)*(1.0-_ease((x-.48)/.52))
