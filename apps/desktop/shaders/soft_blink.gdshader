shader_type canvas_item;

uniform float blink_amount : hint_range(0.0, 1.0) = 0.0;

const vec2 SPRITE_SIZE = vec2(256.0, 244.0);
const vec2 LEFT_EYE_CENTER = vec2(108.0, 77.0);
const vec2 RIGHT_EYE_CENTER = vec2(149.0, 77.0);
const vec2 EYE_RADIUS = vec2(12.5, 9.0);

float eye_patch(vec2 pixel_position, vec2 center) {
	vec2 q = (pixel_position - center) / EYE_RADIUS;
	return 1.0 - smoothstep(0.82, 1.04, length(q));
}

float eyelid_line(vec2 pixel_position, vec2 center) {
	vec2 q = (pixel_position - center) / EYE_RADIUS;
	float curve_y = -0.04 + 0.20 * q.x * q.x;
	float distance_to_curve = abs(q.y - curve_y);
	float line = 1.0 - smoothstep(0.055, 0.15, distance_to_curve);
	float span = 1.0 - smoothstep(0.74, 1.0, abs(q.x));
	return line * span;
}

void fragment() {
	vec4 base = texture(TEXTURE, UV) * COLOR;
	vec2 pixel_position = UV * SPRITE_SIZE;
	float left_patch = eye_patch(pixel_position, LEFT_EYE_CENTER);
	float right_patch = eye_patch(pixel_position, RIGHT_EYE_CENTER);
	float closed_amount = smoothstep(0.0, 0.16, blink_amount);
	float patch = max(left_patch, right_patch) * closed_amount;
	vec2 cheek_uv = vec2(UV.x, 90.0 / SPRITE_SIZE.y);
	vec4 cheek = texture(TEXTURE, cheek_uv) * COLOR;
	vec4 result = mix(base, cheek, patch);

	float line = max(
		eyelid_line(pixel_position, LEFT_EYE_CENTER),
		eyelid_line(pixel_position, RIGHT_EYE_CENTER)
	) * closed_amount;
	result.rgb = mix(result.rgb, vec3(0.27, 0.14, 0.12), line * 0.96);
	COLOR = result;
}
